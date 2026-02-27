# Shared Reference: Canonical Payroll Record & DynamoDB Access Patterns

## Canonical Payroll Record

Every vendor file, regardless of source format, is parsed into this normalized record structure. All agent services operate on this schema.

### Identity Fields
| Field | Type | Source |
|-------|------|--------|
| planid | String | Client config or file |
| planidfreq | String | Computed: planid + "_" + payFreqDesc |
| clientid | String | File or cross-reference |
| ssn | Numeric(9) | File, cleaned by SSNValidatorService |

### Demographic Fields
| Field | Type | Source |
|-------|------|--------|
| fname / lname / mname | String | File |
| dob | Date | File, validated by IssueDetectorService |
| email | String | File |
| street1 / street2 / city / state / zip | String | File |
| phone | String | File |
| gender | String(1) | File |
| maritalstatus | String | File |

### Employment Fields
| Field | Type | Source |
|-------|------|--------|
| doh | Date | File or Relius override (EmploymentStatusService) |
| dot | Date | File, cleaned by EmploymentStatusService |
| dor | Date | File, cleaned by EmploymentStatusService |
| payfreq | String(1) | W/B/S/M/Q/A |

### Compensation Fields
| Field | Type | Source |
|-------|------|--------|
| hours | Decimal(9,2) | File or estimated by HoursEstimationService |
| salary | Decimal(12,2) | File |
| bonus | Decimal(12,2) | File |
| commissions | Decimal(9,2) | File |
| overtime | Decimal(9,2) | File |
| plancomp | Decimal(12,2) | Computed: CompensationCalcService |
| matchcomp | Decimal(12,2) | Computed: CompensationCalcService |
| ercomp | Decimal(12,2) | Computed: CompensationCalcService |

### Contribution Fields (12 source types)
| Field | Type | Source |
|-------|------|--------|
| deferral | Decimal(9,2) | File or calculated |
| rothdeferral | Decimal(9,2) | File or calculated |
| match | Decimal(9,2) | File or MatchCalcService |
| shmatch | Decimal(9,2) | File or MatchCalcService |
| shmatchqaca | Decimal(9,2) | File or MatchCalcService |
| pshare | Decimal(9,2) | File or ERContribCalcService |
| shne | Decimal(9,2) | File or ERContribCalcService |
| shneqaca | Decimal(9,2) | File or ERContribCalcService |
| loan | Decimal(9,2) | File |
| prevwageer | Decimal(9,2) | File |
| prevwageqnec | Decimal(9,2) | File |
| aftertax | Decimal(9,2) | File |

### Validation & Classification Fields
| Field | Type | Set By |
|-------|------|--------|
| badssn | String(1) | SSNValidatorService |
| issue | String(500) | IssueDetectorService |
| warning | String(500) | IssueDetectorService |
| eetype / eesubtype | String(5) | EEType coding step |
| planhold | String(20) | PlanHoldService |
| rehirewithoutdot | Integer(1) | EmploymentStatusService |

---

## DynamoDB Access Patterns

### Read Pattern: Source-of-Truth → Cache → Agent
```
Agent needs rule → Check Redis (L2 cache)
  → HIT: use cached value
  → MISS: GetItem/Query DynamoDB (L3) → write to Redis → use value
```

### Client-Specific with GLOBAL Fallback
```
Agent needs calculation rule for planId "ExtraSpecial":
  1. GetItem PK=CLIENT#ExtraSpecial, SK=CALC#MATCH_FORMULA#v{latest}
     → If item exists: use client-specific rule
  2. If not found: GetItem PK=GLOBAL, SK=CALC#MATCH_FORMULA#v{latest}
     → Use global default rule
```

### Cache Key Conventions
| Pattern | Example | TTL |
|---------|---------|-----|
| schema:{vendorId}:{fingerprint} | schema:ExtraSpecial:sha256abc | 24 hrs |
| rules:validation:{category} | rules:validation:SSN_VALIDATION | 1 hr |
| rules:calc:{planId}:{calcType} | rules:calc:ExtraSpecial:MATCH_FORMULA | 1 hr |
| config:{planId}:{payFreq} | config:ExtraSpecial:BiWeeklyFri | 1 hr |
| limits:{year} | limits:2026 | 24 hrs |
| hold:{planId} | hold:ExtraSpecial | 15 min |
| pipeline:{planId}:{payFreq} | pipeline:ExtraSpecial:BiWeeklyFri | 1 hr |
| session:{batchId}:state | session:batch-20260224-001:state | 4 hrs |
| session:{batchId}:records | session:batch-20260224-001:records | 4 hrs |

### DynamoDB Table Quick Reference
| Table | PK Pattern | SK Pattern | Primary Consumer |
|-------|-----------|-----------|-----------------|
| bluestar-client-processing-config | CLIENT#{planId} | CONFIG#{payFreq}#{version} | All agents |
| bluestar-vendor-schema-mapping | VENDOR#{vendorId} | SCHEMA#{planId}_{payFreq}#v{ver} | IDP Agent |
| bluestar-validation-rules | CATEGORY#{category} | RULE#{ruleId} | Validator Agent |
| bluestar-business-calculation-rules | CLIENT#{planId} or GLOBAL | CALC#{calcType}#v{ver} | Transform Agent |
| bluestar-compliance-limits | YEAR#{year} | LIMITS | Transform Agent |
| bluestar-plan-hold-rules | PLAN#{planId} | HOLD#{clientId} | Compliance Agent |
| bluestar-processing-pipeline | CLIENT#{planId}_{payFreq} | STEP#{stepOrder} | Orchestrator |
| bluestar-ach-configuration | PLAN#{planId} | ACH#{payFreq}#v{ver} | Compliance Agent |

---

## Pipeline Step Reference

| Step | Subroutine | Agent | Required |
|------|-----------|-------|----------|
| 0100 | FILE_INGEST | IDP | Yes |
| 0200 | FILE_VALIDATION | Validator | Yes |
| 0300 | MERGE_PAYROLL_FIELDS | IDP | Yes |
| 0400 | DROP_V_VARIABLES | IDP | Yes |
| 0500 | DESTRING_NUMBERS | IDP | Yes |
| 0550 | SPLIT_MONTH_PEO | Transform | Yes |
| 0600 | CALC_COMPENSATION | Transform | Yes |
| 0700 | CALC_MATCH | Transform | Conditional |
| 0800 | CALC_ER_CONTRIB | Transform | Conditional |
| 0900 | BAD_SSN | Validator | Yes |
| 1000 | FORMAT_DATES_STRINGS | Validator | Yes |
| 1100 | EETYPE_CODING | Transform | Conditional |
| 1200 | EMPLOYMENT_STATUS | Validator | Yes |
| 1300 | DUPLICATE_EMPLOYEES | Transform | Yes |
| 1400 | DROP_OLD_TERMS | Transform | Yes |
| 1500 | FIX_HOURS | Transform | Yes |
| 1600 | ISSUE_DETECTION | Validator | Yes |
| 1700 | TOTALS_INCLNEG | Transform | Yes |
| 1800 | NEGATIVE_PAYROLL | Transform | Yes |
| 1900 | TOTALS_EXCLNEG | Transform | Yes |
| 2000 | PLAN_HOLD_CHECK | Compliance | Yes |
| 2100 | EXPORT_FILES | Transform | Yes |
| 2200 | FORFEITURES | Compliance | Yes |
| 2300 | GENERATE_XML | Transform | Yes |
| 2400 | DEPWD_DETAIL_UPDATE | Compliance | Yes |
| 2500 | ACH_PREP | Compliance | Yes |
| 2600 | ACH_CALC | Compliance | Yes |

---

## Custodian Deadlines
| Custodian | Deadline | Timezone |
|-----------|----------|----------|
| Matrix Trust | 3:30 PM | Central |
| Schwab | 12:00 PM | Central |

## Environment Configuration
| Environment | DynamoDB Suffix | Redis Cluster | SQL Server |
|------------|----------------|---------------|------------|
| dev | -dev | redis-dev.bluestar | CapitalSG-64-Dev |
| uat | -uat | redis-uat.bluestar | CapitalSG-64-UAT |
| prod | (none) | redis-prod.bluestar | CapitalSG-64 |
