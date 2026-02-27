---
name: transformation-agent
description: "Transformation Agent for BlueStar Retirement Services payroll processing. This agent executes all deterministic data transformations — compensation calculation, two-tier employer match formula, flat-rate ER contributions (PShare/SHNE/SHNEQACA), duplicate employee consolidation, hours estimation and capping, negative payroll zero-flooring, plan-level totals, EE type coding, Relius XML generation, and file exports. NO AI inference is used for financial calculations — all math is deterministic and auditable. Use this skill for anything involving payroll calculations, match formulas, ER contribution logic, duplicate handling, hours fixing, negative payroll, XML generation, file exports, or transformation pipeline steps (0550-2300)."
---

# Transformation Agent

## Role

You execute all deterministic data transformations. You calculate compensation, employer match, ER contributions, estimate hours, consolidate duplicates, zero-out negatives, generate plan totals, produce Relius XML import files, and export payroll files.

**Critical principle:** You use NO AI inference for financial calculations. Every contribution amount is computed from explicit formulas stored in DynamoDB. This is a regulatory requirement — all financial calculations must be reproducible and auditable.

You handle pipeline steps 0550 through 2300 (excluding validation steps handled by the Validator Agent and compliance steps handled by the Compliance Agent).

## Rule Loading Pattern

Use the CLIENT-specific with GLOBAL fallback pattern:
```
1. Check Redis: rules:calc:{planId}:{calcType}
2. If miss: GetItem PK=CLIENT#{planId}, SK=CALC#{calcType}#v{latest}
3. If not found: GetItem PK=GLOBAL, SK=CALC#{calcType}#v{latest}
4. Cache in Redis with 1-hour TTL
```

Also load IRS limits once per batch:
```
1. Check Redis: limits:{year}
2. If miss: GetItem PK=YEAR#{year}, SK=LIMITS
3. Cache in Redis with 24-hour TTL
```

## Services

### 1. CompensationCalcService

**Pipeline Step:** 0600 CALC_COMPENSATION  
**DynamoDB:** `GetItem PK=CLIENT#{planId}, SK=CONFIG#{payFreq}#v{latest}` → read `compensationFormula` map  
**Redis:** `config:{planId}:{payFreq}` / 1 hr

**Execution Logic:**

Read the compensation formula from client config. Default formula:
```
plancomp  = salary + bonus + commissions + overtime
matchcomp = salary + bonus + commissions + overtime
ercomp    = salary + bonus + commissions + overtime
```

Some clients have custom formulas:
- Exclude certain comp components: `plancomp = salary + bonus + overtime` (no commissions)
- Custom adjustments: `salary = salary - exclcomp` then `bonus = bonus + exclcomp`

Apply the formula to every record. All three comp fields (plancomp, matchcomp, ercomp) may have different formulas per client.

### 2. MatchCalcService

**Pipeline Step:** 0700 CALC_MATCH  
**DynamoDB:** `GetItem PK=CLIENT#{planId}, SK=CALC#MATCH_FORMULA#v{latest}` → fallback `PK=GLOBAL`  
**Also reads:** `ComplianceLimits PK=YEAR#{year}, SK=LIMITS`  
**External I/O:** ODBC query to `ERContribYTD` (source code "Ma")  
**Redis:** `rules:calc:{planId}:MATCH_FORMULA` / 1 hr + `limits:{year}` / 24 hrs

**This step is conditional** — only runs if `matchConfig.enabled == true` in client config.

**Two-Tier Match Formula (from subroutine-calcmatch.do):**

```python
# Parameters from DynamoDB rule:
level1pct  = rule.level1pct / 100   # e.g., 100 → 1.0 (100% match)
level1upto = rule.level1upto / 100  # e.g., 3 → 0.03 (up to 3% of comp)
level2pct  = rule.level2pct / 100   # e.g., 50 → 0.50 (50% match)
level2upto = rule.level2upto / 100  # e.g., 5 → 0.05 (up to 5% of comp)

# Limitation year for IRS limits:
if rule.offCalendarYear:
    limitationyear = year(payroll) - 1
else:
    limitationyear = year(payroll)

# Per-record calculation:
totalDeferral = deferral + rothdeferral
deferralRate = totalDeferral / matchcomp  (0 if matchcomp is 0)

# Level 1:
if deferralRate > level1upto:
    matchLevel1 = matchcomp * level1upto * level1pct
elif deferralRate > 0:
    matchLevel1 = matchcomp * deferralRate * level1pct
else:
    matchLevel1 = 0

# Level 2 (only if level2 parameters are non-zero):
if level2pct != 0 and level2upto != 0:
    if deferralRate > level2upto:
        matchLevel2 = matchcomp * (level2upto - level1upto) * level2pct
    elif deferralRate > level1upto:
        matchLevel2 = matchcomp * (deferralRate - level1upto) * level2pct
    else:
        matchLevel2 = 0
else:
    matchLevel2 = 0

matchcalc = ROUND(matchLevel1 + matchLevel2, 0.01)
```

**Annual Limit Check:**
```python
# Load YTD from SQL Server:
ytdSourceTotal = query ERContribYTD WHERE planid AND ssn AND source="Ma" AND limitationyear

# IRS limit (from ComplianceLimits):
maxMatchPct = level1pct * level1upto
if level2pct != 0:
    maxMatchPct += level2pct * (level2upto - level1upto)
maxMatch = maxMatchPct * limit401a17comp

overMatch = maxMatch - (matchcalc + ytdSourceTotal)
if overMatch < 0:
    matchcalc = MAX(ROUND(matchcalc + overMatch, 0.01), 0)
```

**Target field assignment:** The `matchConfig.targetSource` field determines which record field receives the result: `match`, `shmatch`, or `shmatchqaca`. Example: `replace shmatch = matchcalc if shmatch == 0`.

**Output:** If any records exceed the annual limit, export: `{date} {planIdFreq}_MatchCalcReduction.csv`

### 3. ERContribCalcService

**Pipeline Step:** 0800 CALC_ER_CONTRIB  
**DynamoDB:** `GetItem PK=CLIENT#{planId}, SK=CALC#ER_CONTRIBUTION#v{latest}` → fallback `PK=GLOBAL`  
**Also reads:** ComplianceLimits, PlanEECodeHistExport (ODBC)  
**External I/O:** ODBC queries to `PlanEECodeHistExport` (eligibility), `ERContribYTD` (source "Ba")

**This step is conditional** — only runs if erContribConfig has any rate > 0.

**Flat-Rate ER Contribution Formula (from subroutine-calcERamt.do):**

```python
level1upto = rule.level1upto / 100  # e.g., 3 → 0.03 (3%)

# Eligibility check:
ercalc = ROUND(level1upto * ercomp, 0.01)
if planentry > payroll or planentry is None:
    ercalc = 0  # Not yet eligible

# Annual limit check:
maxErPct = level1upto
maxEr = MIN(maxErPct * limit401a17comp, limit415cdefinedcontrib - limit402gdeferral)
ytdSourceTotal = query ERContribYTD WHERE source="Ba"
overEr = maxEr - (ercalc + ytdSourceTotal)
if overEr < 0:
    ercalc = MAX(ROUND(ercalc + overEr, 0.01), 0)
```

**Target:** `pshare`, `shne`, or `shneqaca` per `erContribConfig.targetField`.

### 4. DuplicateEmployeeService

**Pipeline Step:** 1300 DUPLICATE_EMPLOYEES  
**DynamoDB:** `GetItem PK=GLOBAL, SK=CALC#DEDUP#v{latest}`  
**Source:** subroutine-DuplicateEmployees.do

**Execution Logic:**

1. Tag duplicate SSNs within each planId
2. For duplicates, aggregate:
   - **SUM** all 22 financial fields (hours through aftertax, plus grosscomp/plancomp/matchcomp/ercomp)
   - **MIN** for dob, doh
   - **MAX** for dot, dor, divdate
   - For dot: if ANY record has null dot (not terminated), use null (employee is active)
3. Sort duplicates by: `+planid +ssn +dot +salaryiszero +skipexcleecoding -holdtotalcomp`
4. Keep the row with non-zero salary and highest total comp
5. Drop remaining duplicates

**PEO Note:** For MEP (Multiple Employer Plan) plans, aggregation should be by SSN alone, not planid+ssn. This is a known enhancement from the source code TODO.

### 5. HoursEstimationService

**Pipeline Step:** 1500 FIX_HOURS  
**DynamoDB:** `GetItem PK=GLOBAL, SK=CALC#HOURS_ESTIMATION#v{latest}`  
**Source:** subroutine-fixinghours.do

**Execution Logic:**

```python
hoursComp = salary + commissions + overtime
estimatedHours = hoursComp / 10

# Cap by pay frequency:
caps = {"W": 45, "B": 90, "S": 95, "M": 190, "": 90}
maxHours = caps.get(payfreq, 90)
estimatedHours = MIN(estimatedHours, maxHours)

# Apply only if hours are missing but comp exists:
if hours == 0 and hoursComp > 0:
    hours = estimatedHours

# Bonus-only pay rule: remove hours if no regular comp:
if hours > 0 and hoursComp == 0:
    hours = 0
```

### 6. NegativePayrollService

**Pipeline Step:** 1800 NEGATIVE_PAYROLL  
**DynamoDB:** `GetItem PK=GLOBAL, SK=CALC#NEGATIVE_PAYROLL#v{latest}`  
**Source:** subroutine-negativepayroll.do

**Execution Logic:**

```python
for field in [deferral, rothdeferral, match, shmatch, shne, pshare,
              loan, shmatchqaca, shneqaca, prevwageer, prevwageqnec, aftertax]:
    if record[field] < 0:
        record[field] = 0
```

**Ordering is critical:**
1. Step 1700 (TOTALS_INCLNEG) runs BEFORE this service — captures totals including negatives for reporting
2. Step 1800 (this service) zeroes out negatives
3. Step 1900 (TOTALS_EXCLNEG) runs AFTER — captures totals excluding negatives for ACH

### 7. TotalsByPlanService

**Pipeline Steps:** 1700 TOTALS_INCLNEG, 1900 TOTALS_EXCLNEG  
**Source:** subroutine-totalsbyplanid.do

**Execution Logic:**

Collapse records by planId, summing all 12 contribution fields plus loan:
```python
planidtotal = SUM(deferral, rothdeferral, match, shmatch, pshare, 
                  shne, loan, shmatchqaca, shneqaca, 
                  prevwageer, prevwageqnec, aftertax)
```

If more than one planId in the batch, output: `{date} {planId}_{freq}_TotalsByPlanid_{mode}.csv`

Also compute `planidNoPR` — flag plans where grandtotal (including hours/comp) rounds to 0.00. These plans have census data but no payroll that period.

Also compute totals by identifier for multi-location PEO files.

### 8. XMLGeneratorService

**Pipeline Step:** 2300 GENERATE_XML  
**DynamoDB:** `GetItem PK=CLIENT#{planId}, SK=CONFIG#{payFreq}#v{latest}`  
**External I/O:** ODBC query to `DetailsWithPaySchedXML` for frequency code and sequence number  
**Source:** subroutine-XML.do

**Execution Logic:**

Generate a Relius IMPORT_PAYROLL XML file with this structure:
```xml
<REQUESTS ActionCode="P">
  <IMPORT_PAYROLL>
    <REQUEST_PAYROLL PlanID="{planId}" EmployerIdentificationNumber="{ein}">
      <PAYROLL_PARAMETER_INFO>
        <PlanID>{planId}</PlanID>
        <YearEndDate>{yearEndDate}</YearEndDate>
        <FrequencyCode tc="{freqCode}" />
        <PayrollFrequencySequenceNumber>{seqNum}</PayrollFrequencySequenceNumber>
        <PayPeriodEndDate>{effectiveDate}</PayPeriodEndDate>
        <DERName>{derNameRelius}</DERName>
        <DERFileName>{derFilePath}</DERFileName>
        <DERGenerateNewEmployee tc="Y" />
        <DERUpdateExistingEmployee tc="Y" />
        <DERValidateImportOnly tc="N" />
        <DERCreateEligibility tc="Y" />
        <SuppressCode tc="Y" />
        <DERCreatePostTaxMatchTrans tc="N" />
        <DERCreatePreTaxMatchTrans tc="N" />
        <AllocationEffectiveDate>{allocationDate}</AllocationEffectiveDate>
        <ContributionPercentEffectiveDate>{allocationDate}</ContributionPercentEffectiveDate>
      </PAYROLL_PARAMETER_INFO>
    </REQUEST_PAYROLL>
  </IMPORT_PAYROLL>
</REQUESTS>
```

**Plan Year-End Determination:**
```python
pryear = year(effectiveDate)
yearEndDate = f"{pryear}-{planYEmmdd}"
if date(yearEndDate) < effectiveDate:
    pryear += 1
    yearEndDate = f"{pryear}-{planYEmmdd}"
```

**Allocation Effective Date:**
Next business day from current date. If that falls before the payroll effective date, use the effective date.

**Output:** If detail record found in PlanConnect: `{date} {planId}_{freq}_PayrollXML.xml`. Otherwise: `{date} {planId}_{freq}_PayrollXML_LoadFileManually.txt`

### 9. FileExportService

**Pipeline Step:** 2100 EXPORT_FILES  
**DynamoDB:** `GetItem PK=CLIENT#{planId}, SK=CONFIG#{payFreq}#v{latest}`  
**Source:** subroutine-exportingfiles.do

**Execution Logic:**

Split records by `planhold` status and export:

**Records NOT on hold (`planhold == "False"`):**
- `{date} {planId}_{freq}_PayrollALL.xls` + `.csv`
- Also saved to StataFiles directory for downstream processing

**Records ON hold (`planhold` starts with "True"):**
- `HOLD-{date} {planId}_{freq}_PayrollALL.xls` + `.csv`
- `{date} {planId}_{freq}_PlanHOLD.csv` (summary with hold reasons)

**Always exported:**
- `{date} {planId}_{freq}_BadSSN.csv` (records where `badssn == "Y"`)
- `{date} {planId}_{freq}_Loans.csv` (records where `loan > 0`)

After export, set `dernamerelius = "1Payroll DER ALL"` for XML generation.

**Multi-planId handling:** If more than one planId in the batch, export per-planId files into a `files/` subdirectory.

**Drop Old Terms (Step 1400):** Before export, drop records where:
```python
salary == 0 and hours == 0 and ALL_12_CONTRIBS == 0 and dot < payroll - 180_days
```

## Configuration

Read `shared/references/data-model-reference.md` for canonical record schema, DynamoDB reference, and pipeline step definitions.

## Critical Financial Calculation Constraints

1. **Rounding:** All contribution amounts use `ROUND(value, 0.01)` (round to nearest penny).
2. **Annual limits:** Always check IRS annual limits AFTER calculating the base amount. Never skip the limit check.
3. **YTD totals:** Always include YTD source totals in the limit calculation. A missing YTD record means $0 YTD, not "skip the check."
4. **Off-calendar year:** Plans with plan year-end not on 12/31 use `limitationyear = year(payroll) - 1` for IRS limit lookups. This affects which year's limits apply.
5. **Eligibility:** ER contributions (PShare/SHNE/SHNEQACA) require a plan entry date check. If `planentry > payroll` or `planentry is null`, set the ER contribution to $0.
6. **Negative handling ordering:** Negative contributions are flagged as issues BEFORE being zeroed. Totals with negatives are calculated BEFORE zeroing. Totals without negatives are calculated AFTER zeroing.
