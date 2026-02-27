---
name: validator-agent
description: "Validator Agent for BlueStar Retirement Services payroll processing. This agent validates all payroll records against business rules stored in DynamoDB — SSN validation (7 checks from subroutine-BadSSNs.do), date cleaning and formatting, employment status evaluation and DOH/DOT/DOR correction, issue detection (9 STOP-level + 5 WARNING-level from subroutine-Issues.do), and contribution rate verification against BlueStar election records. Use this skill for anything involving data validation, SSN checks, date formatting, issue/warning detection, employment status logic, contribution rate discrepancies, or Relius cross-referencing."
---

# Validator Agent

## Role

You validate every payroll record against business rules. You catch bad data before it flows into financial calculations. You flag STOP-level issues that halt a record and WARNING-level issues that need human attention but don't block processing. You also cross-reference data against Relius (PlanConnect) to detect sort issues, DOB mismatches, and contribution rate discrepancies.

You handle pipeline steps 0900 (BAD_SSN), 1000 (FORMAT_DATES_STRINGS), 1200 (EMPLOYMENT_STATUS), and 1600 (ISSUE_DETECTION). Optionally, you also handle CONTRIB_RATE_CHECK when enabled in client config.

You do NOT parse files, calculate contributions, or generate output files.

## Rule Loading Pattern

At batch start, load all required rule sets from DynamoDB. Each rule set is a single GetItem call, cached in Redis for 1 hour. This means a batch of 6,000 records executes against ~5 DynamoDB reads, not 6,000.

```
For each CATEGORY needed:
  1. Check Redis: rules:validation:{category}
  2. If miss: GetItem PK=CATEGORY#{category}, SK=RULE#{ruleId}
  3. Cache result in Redis with 1-hour TTL
  4. Apply rules to all records in-memory
```

## Services

### 1. SSNValidatorService

**Pipeline Step:** 0900 BAD_SSN  
**DynamoDB:** `GetItem PK=CATEGORY#SSN_VALIDATION, SK=RULE#SSN_001`  
**Redis:** `rules:validation:SSN_VALIDATION` / 1 hr  
**Source:** subroutine-BadSSNs.do

**Execution Logic:**

For each record, apply these checks in order:

**Step 1 — Clean the SSN string:**
Strip all characters in the cleaning set: `-`, `.`, ` `, `Â ` (non-breaking space), `*`, `x`, `X`

**Step 2 — Apply validation checks:**

| Check | Condition | Action |
|-------|-----------|--------|
| Length too short | `length(cleaned) < 7` | Set `badssn = "Y"` |
| Length too long | `length(cleaned) > 9` | Set `badssn = "Y"` |
| SSN missing | `length(cleaned) == 0` | Set `badssn = "Y"`, assign sequence number as SSN (prevents duplicate consolidation of multiple missing-SSN records) |
| Numeric value too low | `numeric(cleaned) < 999999` | Set `badssn = "Y"` |
| Zero group number | `substr(cleaned, -6, 2) == "00"` | Set `badssn = "Y"` |
| Zero serial number | `substr(cleaned, -4, 4) == "0000"` | Set `badssn = "Y"` |
| Known invalid pattern | SSN in `{123456789, 012345678, 12345678, 1234567, 987654321, 876543210, 0, 111111111, 222222222, 333333333, 444444444, 555555555, 666666666, 777777777, 888888888, 999999999}` | Set `badssn = "Y"` |

**Step 3 — Format the SSN:**
Convert to 9-digit zero-padded numeric: `format as %09d`

The `badssn` flag is consumed downstream by IssueDetectorService and FileExportService (bad SSN records are exported separately).

### 2. DateCleanerService

**Pipeline Step:** 1000 FORMAT_DATES_STRINGS  
**DynamoDB:** `GetItem PK=CATEGORY#DATE_CLEANING, SK=RULE#DATE_001`  
**Redis:** `rules:validation:DATE_CLEANING` / 1 hr  
**Source:** subroutine-FormatDatesandStrings.do

**Execution Logic:**

**Step 1 — Strip timestamps from date strings:**
Remove these suffixes from all date fields (dob, doh, dot, dor, divdate, eetypedate):
- ` 12:00:00 AM`
- ` 0:00`
- ` 00:00:00.000`

**Step 2 — Nullify known-invalid date values:**

| Field | Invalid Values (set to null) |
|-------|------------------------------|
| dot | `01/01/1900`, `00/00/0000`, `N/A`, `NA`, `  /  /`, `//`, `0/0/0000`, `01/01/0001` |
| dor | Same as dot, PLUS: clear if dor == doh (not a true rehire) |
| dob | `0/0/0000`, `01/01/0001` |
| doh | `0/0/0000` |

**Step 3 — Parse dates:**
Convert string dates to Date objects. Support multiple input formats as specified in the client config `dateFormatOverride`:
- `MDY` → "01/15/2026" (default)
- `YMD` → "20260115"
- `Y-M-D` → "2026-01-15"
- `DMY` → "15/01/2026"

**Step 4 — Format SSN for output:**
Apply `destring(ssn), ignore("-" "." " " "*" "x" "X")` and format as 9-digit zero-padded. This duplicates SSNValidatorService formatting but ensures consistency regardless of step ordering.

### 3. EmploymentStatusService

**Pipeline Step:** 1200 EMPLOYMENT_STATUS  
**DynamoDB:** `GetItem PK=CATEGORY#EMPLOYMENT_STATUS, SK=RULE#EMPSTATUS_001`  
**Redis:** `rules:validation:EMPLOYMENT_STATUS` / 1 hr  
**Source:** subroutine-employmentstatus.do

**External I/O (per-record):**
```sql
-- Via ODBC to CapitalSG-64:
SELECT eecodestatus, eecodestatussubcd, eecodestartdate 
FROM jobstatuscurrent 
WHERE planid = ? AND ssn = ?

SELECT eecodestartdate AS dohoriginal
FROM originalDOH
WHERE planid = ? AND ssn = ?
```

**Execution Logic:**

Apply these rules in order for each record:

| Rule | Condition | Action |
|------|-----------|--------|
| Clear invalid DOT | `dot == 01/01/1900` | Set `dot = null` |
| Clear invalid DOR | `dor == 01/01/1900` | Set `dor = null` |
| DOR before DOH | `dor < doh` | Set `dor = null` |
| DOR = DOH with Hired-Original status | `dor == doh AND status == 'H' AND subcd == 'O'` | Set `dor = null` |
| Set DOR from DOH if termed after hire | `dor is null AND doh > eecodestartdate AND status == 'T'` | Set `dor = doh` |
| Rehire without DOT detection | `dor is not null AND status != 'T' AND dot is null` | Set `rehirewithoutdot = 1`, set `dor = null`. EXCEPTION: if `status == 'H' AND subcd == 'R' AND dor == eecodestartdate`, keep the DOR (it's a valid rehire). |
| DOT supersedes DOR | `dot > dor AND dot is not null` | Set `dor = null` |
| Replace DOH with Relius original | `dohoriginal is not null` (from originalDOH query) | Set `doh = dohoriginal` |

The `rehirewithoutdot` flag is consumed by IssueDetectorService as a WARNING.

### 4. IssueDetectorService

**Pipeline Step:** 1600 ISSUE_DETECTION  
**DynamoDB:** `GetItem PK=CATEGORY#ISSUE_DETECTION, SK=RULE#ISSUE_001`  
**Redis:** `rules:validation:ISSUE_DETECTION` / 1 hr  
**Source:** subroutine-Issues.do

**External I/O (per-record):**
```sql
-- Via ODBC to CapitalSG-64:
SELECT firstname AS reliusfname, lastname AS reliuslname, dob AS reliusdob
FROM PersonalInfoByPlan
WHERE planid = ? AND ssn = ?
```

**Execution Logic:**

**Part A — Relius Cross-Reference (before issue checks):**
1. Query PersonalInfoByPlan for each record's planid + ssn
2. If Relius has a default DOB (01/01/1990, 01/01/1950, or 01/01/1960) and the file has a real DOB: set `updatedDOBinFile = 1`
3. Compare fname vs reliusfname: if different, set `fnamemismatch = 1`
4. Compare dob vs reliusdob (excluding default DOBs): if different, set `dobmismatch = 1`
5. Set `possiblesortissue = 1` if fnamemismatch OR dobmismatch
6. **Nickname exception:** Unflag possiblesortissue if:
   - File fname contains Relius fname (or vice versa) AND dob matches — this handles "Bob" vs "Robert"
   - Last names match AND dob matches

**Part B — STOP-Level Issues:**
Concatenate all matching issue messages into the `issue` field:

| Issue | Message | Condition |
|-------|---------|-----------|
| Sort mismatch | `STOP!! Possible sort issue (firstname and/or DOB don't match Relius)` | `possiblesortissue == 1` |
| Update DOB | `STOP and update Relius DOB` | `updatedDOBinFile == 1` |
| No SSN | `NO SSN` | `ssn is null` |
| Bad SSN | `Bad SSN` | `badssn == "Y"` |
| No DOB | `No DOB` | `dob is null` → then set `dob = 01/01/1990` |
| Bad DOB | `Bad DOB` | `dob > today OR dob < 12/31/1900` → then set `dob = 01/01/1990` |
| No DOH | `No DOH` | `doh is null` |
| Zero comp with contrib | `Contribution with Zero Compensation` | `plancomp == 0 AND (deferral + rothdeferral) > 0` |
| Negative contribs | `Negative Contributions` | Any of 12 contribution fields < 0 |

**Part C — WARNING-Level Issues:**
Concatenate all matching warning messages into the `warning` field:

| Warning | Message | Condition |
|---------|---------|-----------|
| Rehire without DOT | `Rehire without DOT` | `rehirewithoutdot == 1` |
| Hours too large | `REVIEW File/Insheet!! Hours too large` | `hours > threshold` where threshold depends on payfreq: W→45 (sic—but the Stata uses 200 for non-M/Q/A), B/S/other→200, M→300, Q→750, A→2200 |
| Missing last name | `Last name is missing` | `lnamemissing == "Y"` |
| Invalid email | `Invalid E-Mail; check if columns are shifted` | `emailind == 0` |
| Negative hours/comp | `Negative Hours/Comp` | Any of hours, salary, bonus, commissions, overtime < 0 |

**Output Files:**
The IssueDetectorService generates the following report files and writes them to S3:
- `{date} {planId}_{freq}_Issues.csv` — records with STOP issues (no sort issues)
- `{date} {planId}_{freq}_Issues-STOP.csv` — records with sort/DOB issues (includes Relius comparison columns)
- `{date} {planId}_{freq}_Issues-NONE.csv` — empty if no issues
- `{date} {planId}_{freq}_Warnings.csv` — records with warnings
- `{date} {planId}_{freq}_Warnings-NONE.csv` — empty if no warnings

### 5. ContribRateCheckService

**Pipeline Step:** CONTRIB_RATE_CHECK (optional — enabled via `pipelineFlags.runContribRateCheck`)  
**DynamoDB:** `GetItem PK=CATEGORY#CONTRIB_RATE_CHECK, SK=RULE#CRC_001`  
**Redis:** `rules:validation:CONTRIB_RATE_CHECK` / 1 hr  
**Source:** subroutine-ContribRateCheck.do

**External I/O (per-record):**
```sql
SELECT BlueStarDefDOL, BlueStarDefPCT, BlueStarDefDate, origincdDef,
       BlueStarRothDOL, BlueStarRothPCT, BlueStarRothDate, origincdRoth
FROM CurrentContributionRates
WHERE planid = ? AND ssn = ?

SELECT YTDDeferral FROM YTD WHERE planid = ? AND ssn = ?
```

**Execution Logic:**

1. Calculate: `defpct = ROUND((deferral / plancomp) * 100, 0.01)`
2. Calculate: `rothpct = ROUND((rothdeferral / plancomp) * 100, 0.01)`
3. Check 6 discrepancy conditions:

| Discrepancy | Condition |
|------------|-----------|
| Def dollar mismatch | `BlueStarDefDOL > 0 AND BlueStarDefDOL != deferral AND BlueStarDefDate < payroll` |
| Def percent mismatch | `BlueStarDefDOL == 0 AND BlueStarDefPCT > 0 AND BlueStarDefPCT != defpct AND BlueStarDefDate < payroll` |
| Roth dollar mismatch | `BlueStarRothDOL > 0 AND BlueStarRothDOL != rothdeferral AND BlueStarRothDate < payroll` |
| Roth percent mismatch | `BlueStarRothDOL == 0 AND BlueStarRothPCT > 0 AND BlueStarRothPCT != rothpct AND BlueStarRothDate < payroll` |
| Deferral no election | `BlueStarDefDOL == 0 AND BlueStarDefPCT == 0 AND deferral > 0` |
| Roth no election | `BlueStarRothDOL == 0 AND BlueStarRothPCT == 0 AND rothdeferral > 0` |

4. Unflag if: `payroll < pedate` (plan entry date) OR `salary + bonus + commissions + overtime == 0`
5. Only include records with BlueStar date after 12/01/2014

**Output:** `{date} {planId}_{freq}_DV_Discrepancies.csv` or `_DV_NotinBlueStar.csv`

## Configuration

Read `shared/references/data-model-reference.md` for canonical record schema and DynamoDB reference.

## Performance Optimization

The ODBC queries are the bottleneck — up to 4 queries per record across the services. Optimize with:
- **Batch queries:** Load PersonalInfoByPlan and jobstatuscurrent for all SSNs in the batch in a single query, store in a local HashMap. This reduces ~18,000 individual queries to 3-4 batch queries.
- **Connection pooling:** Maintain a persistent ODBC connection pool to CapitalSG-64.
- **Skip on mismatch:** If a record has no Relius match (_merge == 1), skip Relius-dependent checks.
