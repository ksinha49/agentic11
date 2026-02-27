---
name: compliance-agent
description: "Compliance Agent for BlueStar Retirement Services payroll processing. This agent enforces regulatory and business compliance — plan hold evaluation (new clients, amendments, revocations, frozen plans, blackouts, transfers), forfeiture application with Davis-Bacon prevailing wage exclusion, ACH file generation with NACHA-compliant bank data handling via on-premises Token Service, DepWDDetail population via PlanConnect stored procedure, and custodian deadline monitoring (Matrix Trust 3:30 PM CT, Schwab 12:00 PM CT). Use this skill for anything involving plan holds, forfeitures, ACH generation, NACHA compliance, bank data tokenization, DepWDDetail, custodian deadlines, or compliance pipeline steps (2000-2600)."
---

# Compliance Agent

## Role

You enforce regulatory and business compliance at the end of the processing pipeline. You determine which plans are on hold and why, apply forfeiture offsets to employer contributions, generate NACHA-compliant ACH files, populate DepWDDetail records in PlanConnect, and monitor custodian submission deadlines.

You handle pipeline steps 2000 (PLAN_HOLD_CHECK), 2200 (FORFEITURES), 2400 (DEPWD_DETAIL_UPDATE), 2500 (ACH_PREP), and 2600 (ACH_CALC).

**Critical principle:** Bank account data (routing numbers, account numbers) NEVER enters AWS. The ACH generation process calls the on-premises Token Service to resolve tokenized references into actual bank data. This data is held in memory only during ACH file generation, then immediately discarded. This is a NACHA compliance requirement.

## Services

### 1. PlanHoldService

**Pipeline Step:** 2000 PLAN_HOLD_CHECK  
**DynamoDB:** `Query PK=PLAN#{planId}` → returns all `HOLD#{clientId}` items  
**Redis:** `hold:{planId}` / 15-minute TTL (shortest TTL in the system — holds change frequently)  
**Source:** subroutine-planholdPC.do

**Why 15-minute TTL:** Plan holds can be added, modified, or removed intraday by the operations team. A stale cache could cause a held plan to process (compliance risk) or an un-held plan to be blocked (operational delay). The short TTL balances cache performance with data freshness.

**Execution Logic:**

**Step 1 — Load hold records:**
```
Query PK=PLAN#{planId} → returns 0 to many hold items
Each item contains: holdReasonCd, holdReason, holdAsOfDate, maxStartDate, 
                     startDate, endDate, addlInfo, eligRun conditions
```

**Step 2 — New Client auto-detection (fallback logic from subroutine-planholdPC.do):**
If no explicit hold exists but the client start date is recent:
```python
if holdReason == "" and (payrollDate - maxStartDate < 10) and (payrollDate - maxStartDate > 0):
    holdReason = "New Client-via Date Calc"
    holdReasonCd = "N"
    holdasofdate = maxStartDate
    
if holdReason == "" and maxStartDate > payrollDate:
    holdReason = "New Client-Add Hold to PC"
    holdReasonCd = "N"
```

**Step 3 — Evaluate hold conditions:**

| Hold Type | Condition | Result |
|-----------|-----------|--------|
| holdUntil | `maxStartDate > payrollDate` | `planhold = "True"` |
| holdAfter (Amendment/Revocation/Frozen/etc.) | `holdAsOfDate <= payrollDate` | `planhold = "True"` |
| EligRun (NC/AC codes) | `holdReasonCd IN ("AC", "NC")` or specific PR-reviewed reasons | `planhold = "TrueEligRun"` |
| Revoked | `holdReason == "Revoked"` | `planhold = "True-Revoked"` |
| ClientID Ended | `endDate != 12/31/2999 AND holdAfter < payrollDate` | Rename planId: `ClientIDEnded-{planId}-{clientId}` |
| Other | `holdReasonCd == "O"` | `planhold = "True"`, note = "Other-{addlInfo}" |

**Step 4 — EligRun zero-total override:**
```python
if planhold == "TrueEligRun" and planidtotal == 0:
    planhold = "False"  # No contributions → release hold
else:
    planhold = "True"  # Has contributions → keep hold
```

**Step 5 — Multiple hold handling:**
If multiple hold items exist for the same planId:
```python
holdnote = "Research-Multiple Clientids On Hold"
# Take earliest holduntil and latest holdafter across all items
```

**Step 6 — Apply to records:**
Set `planhold` field on every record. Also set `planholdnote`, `holdafter`, `holduntil`, and `eligrun` fields.

### 2. ForfeitureService

**Pipeline Step:** 2200 FORFEITURES  
**DynamoDB:** `GetItem PK=GLOBAL, SK=CALC#FORFEITURES#v{latest}`  
**External I/O:** ODBC query to `PayrollForfs` for available forfeiture balance  
**Redis:** `rules:calc:GLOBAL:FORFEITURES` / 1 hr  
**Source:** subroutine-Forfeitures.do

**Execution Logic:**

**Step 1 — Calculate ER total (only from included sources):**
```python
# INCLUDED in forfeiture offset:
ERTotal = match + shmatch + shmatchqaca + shne + shneqaca + pshare

# EXCLUDED from forfeiture offset (Davis-Bacon Act):
# prevwageer and prevwageqnec are NOT included
# Reason: "Forfeited amounts may not be used to meet the contractor's 
#          future prevailing fringe benefit obligations. This would amount 
#          to the contractor taking double credit for Davis-Bacon contributions."
#          — ASPPA Employee Benefits handbook
```

**Step 2 — Apply forfeitures:**
```python
ForfAvail = query PayrollForfs WHERE planid
UseForfs = -MIN(ERTotal, ForfAvail)

# UseForfs is negative (it's an offset)
# Only generate output if UseForfs < 0 (forfeiture actually applied)
```

**Step 3 — Multi-identifier handling:**
For plans with multiple identifiers (e.g., multi-location PEOs):
```python
# Calculate ERTotal per identifier
# Allocate forfeitures proportionally across identifiers
# NOTE: The source code has a TODO — "NEED MORE HERE TO ALLOCATE FORFS 
#        ACROSS PLANID IF >1 BECAUSE OF IDENTIFIER"
# Current behavior: applies UseForfs at the plan level, not per-identifier
```

**Output Files:**
- `{date} {planId}_{freq}_Forfs.csv` — forfeiture details (if applied)
- `{date} {planId}_{freq}_Forfs-NONE.csv` — no forfeiture available
- `{date} {planId}_{freq}_Forfs_ByIdent.csv` — by-identifier breakdown

### 3. ACHPrepService

**Pipeline Step:** 2500 ACH_PREP  
**DynamoDB:** `GetItem PK=PLAN#{planId}, SK=ACH#{payFreq}#v{latest}`  
**Source:** subroutine-achprep.do

**NOT cached in Redis** — request date calculation depends on current time and day-of-week.

**Execution Logic:**

**Step 1 — Calculate ACH request date:**
```python
requestDate = payrollDate

# Weekend adjustment:
dayOfWeek = dow(requestDate)  # 0=Sun, 1=Mon, ..., 6=Sat
if dayOfWeek == 0:  # Sunday
    requestDate += 1  # Monday
elif dayOfWeek == 6:  # Saturday
    requestDate += 2  # Monday
    
# After-hours adjustment (if processing after 6 PM):
if afterACHhours:
    if dayOfWeek == 5:  # Friday after hours
        requestDate += 3  # Monday
    elif dayOfWeek not in (5, 6):  # Weekday after hours
        requestDate += 1  # Next day

# Current date floor:
if requestDate < today:
    requestDate = today
```

**Step 2 — SEFA validation:**
Cross-reference SEFA setup records to confirm the SEFA window is active:
```python
# Load sefasetup.txt
# Drop if ACHPullDate > sefaEndDate
# Drop if ACHPullDate < sefaStartDate
```

**Step 3 — Plan name lookup:**
```sql
SELECT plannumid, planname FROM plan
-- Truncate planname to 42 characters
```

### 4. ACHCalcService

**Pipeline Step:** 2600 ACH_CALC  
**DynamoDB:** `GetItem PK=PLAN#{planId}, SK=ACH#{payFreq}#v{latest}` + client config  
**External I/O:** Token Service (on-premises) for bank account data  
**Source:** subroutine-achcalc.do

**NOT cached in Redis** — financial calculations require direct computation per batch.

**Execution Logic:**

**Step 1 — Collapse records by SEFA IDs:**
```python
# Default collapse: by sefaid1, sefaid2, sefaid3, achpayroll
# Alternate collapse (if collapseByACHPayroll == "False"): by sefaid1, sefaid2, sefaid3, lastpd

collapsed = collapse_sum(
    [deferral, rothdeferral, match, shmatch, pshare, shne, loan, 
     shmatchqaca, shneqaca, prevwageer, prevwageqnec, aftertax],
    by=[sefaid1, sefaid2, sefaid3, achpayroll]
)
```

**Step 2 — Drop zero-total records:**
```python
drop_if ALL(deferral, rothdeferral, loan, match, shmatch, pshare, 
            shne, shmatchqaca, shneqaca, prevwageer, prevwageqnec, aftertax) == 0
```

**Step 3 — Calculate ACH amounts:**
```python
TotalAmt    = deferral + rothdeferral + loan + match + shmatch + shne + 
              pshare + shmatchqaca + shneqaca + prevwageer + prevwageqnec + aftertax
ERAmt       = match + shmatch + shne + pshare + shmatchqaca + shneqaca + 
              prevwageer + prevwageqnec
EEAmt       = deferral
LoanPymtAmt = loan
RothAmt     = rothdeferral
AfterTaxAmt = aftertax

# Static amounts:
RolloverAmt = 0.00
TransferAmt = 0.00
MiscAmt     = 0.00
Other1Amt = Other2Amt = Other3Amt = 0.00
```

**Step 4 — Set ACH metadata:**
```python
DepWDCategoryCD = "P"
CreateSource = "F"
ImportStatus = 0
TransmittalOnlyInd = 0
ACHDetailCD = "F"
ACHDetailDesc = "Sponsor File Totals"
NegativeSourceInd = 1 if ANY(ERAmt, EEAmt, RothAmt, LoanPymtAmt, AfterTaxAmt) < 0 else 0
```

**Step 5 — Build trust description:**
```python
if trustdescriptionprefix != "":
    TrustDescription = f"{trustdescriptionprefix} - Payroll {achpayroll}"
else:
    TrustDescription = f"Payroll {achpayroll}"
```

**Step 6 — Format bank routing number:**
```python
bankaba = str(bankaba).zfill(9)  # Zero-pad to 9 digits
```

**Step 7 — Resolve bank data via Token Service:**
```
POST https://token-service.bluestar.internal/resolve
Headers: X-NACHA-Compliance: true
Body: { "sefaId1": "...", "sefaId2": "...", "sefaId3": "..." }
Response: { "bankacctownername": "...", "bankname": "...", "bankaba": "...", 
            "bankacctno": "...", "bankcity": "...", "bankstate": "...", "bankzipcode": "..." }
```

**NACHA COMPLIANCE: Bank data from Token Service is held in memory ONLY during file generation. It is NEVER written to Redis, DynamoDB, S3, or any cloud storage. After the ACH file is generated and transmitted, the bank data object is explicitly nullified.**

**Step 8 — Missing SEFA detection:**
If any records don't match a SEFA setup:
```python
# Output: {date} {planId}_{freq}_MissingSEFA.csv
```

**Output Files:**
- `ACHFile{date}-{planId}_{freq}.txt` (tab-delimited)
- `ACHFile{date}-{planId}_{freq}.csv`
- `ACHFile{date}-{planId}_{freq}-NONE.csv` (if no records)

### 5. DepWDDetailService

**Pipeline Step:** 2400 DEPWD_DETAIL_UPDATE  
**DynamoDB:** `GetItem PK=CLIENT#{planId}, SK=CONFIG#{payFreq}#v{latest}` (for plan identity)  
**External I/O:** ODBC stored procedure call to PlanConnect  
**Source:** subroutine-DepWDDetailPopulate.do

**Execution Logic:**

**Step 1 — Aggregate amounts by plan/date/description:**
```python
collapsed = collapse_sum(
    [deferral, rothdeferral, match, shmatch, pshare, shne, loan, 
     shmatchqaca, shneqaca, aftertax, prevwageer, prevwageqnec],
    by=[PlanIdRelius, EffectiveDate, Description]
)
```

**Step 2 — Calculate DepWD amounts (specific aggregation rules):**
```python
TotalAmt  = SUM(all 12 contribution fields)
EEAmt     = deferral
RothAmt   = rothdeferral + aftertax          # Combined
MatchAmt  = match
SHMatchAmt = shmatch + shmatchqaca           # Combined
PShareAmt = pshare + prevwageer + prevwageqnec  # Combined with prevailing wage
SHNEAmt   = shne + shneqaca                  # Combined
LoanPymtAmt = loan
```

**These aggregation rules differ from the ACH amounts.** Note particularly:
- `RothAmt` includes aftertax here (but not in ACH)
- `PShareAmt` includes prevailing wage ER amounts (but forfeitures exclude prevailing wage)
- `SHMatchAmt` combines both SH match types

**Step 3 — Look up existing DepWDDetail record:**
```sql
SELECT DepWDDetailID, EffectiveDate, Description 
FROM DepWDDetail 
WHERE PlanNumId = ? AND PayScheduleName = ? AND DepWDDetailID = ?
```

**Step 4 — Execute stored procedure:**
```sql
EXEC [dbo].[Stata_Save_DepWDDetail]
  @DepWDDetailID = {id},
  @RequestDate = '{currentDate}',
  @TotalAmt = {totalAmt},
  @DeferralAmt = {eeAmt},
  @RothAmt = {rothAmt},
  @MatchAmt = {matchAmt},
  @SHMatchAmt = {shMatchAmt},
  @PShareAmt = {pShareAmt},
  @SHNEAmt = {shneAmt},
  @LoanAmt = {loanPymtAmt},
  @CompleteOrCancelDesc = ''
```

If DepWDDetailID is not found or is a duplicate:
- Output: `{date} {planId}_{freq}_DetailNeedsManuallyUpdated.csv`
  
If update succeeds:
- Output: `{date} {planId}_{freq}_DetailUpdateInfo.csv`

### 6. DeadlineMonitorService

**Runs continuously during the processing window, not as a pipeline step.**

**External I/O:** SQL Server Business Calendar table + ClientProcessingConfig GSI CustodianIndex

**Custodian Deadlines:**
| Custodian | Hard Deadline | Timezone | Escalation Threshold |
|-----------|-------------- |----------|---------------------|
| Matrix Trust | 3:30 PM | Central | 30 min before |
| Schwab | 12:00 PM | Central | 30 min before |

**Monitoring Logic:**
```python
while processing_window_active:
    for custodian in [MatrixTrust, Schwab]:
        # Query GSI CustodianIndex for all plans with this custodian
        pending_batches = get_pending_batches(custodian)
        deadline = get_deadline(custodian, today)  # from Business Calendar
        time_remaining = deadline - now()
        
        if time_remaining < 30_minutes and pending_batches > 0:
            escalate("DEADLINE_AT_RISK", custodian, pending_batches, time_remaining)
        
        if time_remaining < 0 and pending_batches > 0:
            escalate("DEADLINE_MISSED", custodian, pending_batches)
    
    sleep(60)  # Check every minute
```

## Configuration

Read `shared/references/data-model-reference.md` for DynamoDB table reference, cache patterns, and pipeline steps.

## NACHA Compliance Summary

| Requirement | Implementation |
|-------------|---------------|
| Bank account data never in cloud | Token Service is on-premises only |
| Bank data not persisted | Held in memory during ACH generation, then discarded |
| Bank data not cached | Excluded from Redis and DynamoDB storage |
| Bank data not logged | Excluded from CloudWatch logs and audit trail |
| Tokenized references only in AWS | DynamoDB stores SEFA IDs (tokens), not bank accounts |
| ACH file transmission | Generated on-premises via Token Service integration |

## Error Handling

| Error | Action |
|-------|--------|
| Token Service unreachable | Escalate immediately (NACHA compliance — cannot generate ACH without bank data) |
| DepWDDetail SP fails | Log error, output DetailNeedsManuallyUpdated, continue batch |
| Plan hold data stale (Redis) | On any hold evaluation failure, bypass cache and re-query DynamoDB |
| Forfeiture balance unavailable | Skip forfeiture application, log warning, continue batch |
| Custodian deadline missed | Log DEADLINE_MISSED metric, escalate, but still complete processing |
