---
name: bluestar-agent-skills
description: "Complete agent skill definitions for the BlueStar Retirement Services AI-powered payroll processing platform. Contains operational skill files for all 5 agents: Agentcore Orchestrator (pipeline execution, workflow state, escalation), IDP Agent (schema matching, file parsing, destring), Validator Agent (SSN validation, date cleaning, issue detection, employment status, contribution rate check), Transformation Agent (compensation calc, two-tier match, ER contributions, dedup, hours, negatives, XML, exports), and Compliance Agent (plan holds, forfeitures, ACH/NACHA, DepWDDetail, deadline monitoring). Each skill defines the agent's DynamoDB access patterns, Redis caching strategy, service abstractions, and execution logic derived from 24+ legacy Stata subroutines."
---

# BlueStar Agent Skills

## Overview

This directory contains the operational skill definitions for the 5 AI agents that power the BlueStar Retirement Services payroll processing platform. Each skill file defines:

- **Role and boundaries** — what the agent does and does NOT do
- **Service abstractions** — the named services within each agent
- **DynamoDB access patterns** — exact table, PK/SK, and API operation for each service
- **Redis caching strategy** — cache key patterns, TTLs, and bypass exceptions
- **Execution logic** — step-by-step processing rules derived from Stata subroutines
- **External I/O** — SQL Server ODBC queries, Token Service calls, S3 operations
- **Error handling** — failure modes and recovery/escalation actions
- **Output files** — naming conventions and generation conditions

## Directory Structure

```
agent-skills/
├── README.md                          (this file)
├── orchestrator-agent/
│   └── SKILL.md                       (3 services: PipelineExecutor, WorkflowStateManager, EscalationRouter)
├── idp-agent/
│   └── SKILL.md                       (3 services: SchemaMatcherService, FileParserService, DestringService)
├── validator-agent/
│   └── SKILL.md                       (5 services: SSNValidator, DateCleaner, IssueDetector, EmploymentStatus, ContribRateCheck)
├── transformation-agent/
│   └── SKILL.md                       (9 services: CompensationCalc, MatchCalc, ERContribCalc, DuplicateEmployee, HoursEstimation, NegativePayroll, TotalsByPlan, XMLGenerator, FileExport)
├── compliance-agent/
│   └── SKILL.md                       (6 services: PlanHold, Forfeiture, ACHPrep, ACHCalc, DepWDDetail, DeadlineMonitor)
└── shared/
    └── references/
        └── data-model-reference.md    (canonical record schema, DynamoDB tables, cache keys, pipeline steps)
```

## Agent Summary

| Agent | Services | Pipeline Steps | Primary DynamoDB Tables | Runtime |
|-------|----------|---------------|------------------------|---------|
| Orchestrator | 3 | ALL (coordination) | ProcessingPipeline, ClientProcessingConfig | AWS Agentcore |
| IDP | 3 | 0100-0500 | VendorSchemaMapping, ClientProcessingConfig | ECS Fargate + Claude Bedrock |
| Validator | 5 | 0900, 1000, 1200, 1600 | ValidationRules, ClientProcessingConfig | ECS Fargate + Claude Bedrock |
| Transformation | 9 | 0550-2300 (excluding validation/compliance) | BusinessCalculationRules, ComplianceLimits, ClientProcessingConfig | ECS Fargate |
| Compliance | 6 | 2000-2600 | PlanHoldRules, ACHConfiguration, BusinessCalculationRules | ECS Fargate |
| **TOTAL** | **26** | **26 steps** | **8 DynamoDB tables** | |

## Processing Pipeline Flow

```
EventBridge (file.received)
    ↓
Orchestrator → loads pipeline from ProcessingPipeline table
    ↓
[0100-0500] IDP Agent
    Schema fingerprint → column mapping → parse → destring
    ↓
[0900-1600] Validator Agent  
    SSN checks → date cleaning → employment status → issue detection
    ↓
[0550-2300] Transformation Agent
    Comp calc → match → ER contrib → dedup → hours → negatives → totals → XML → export
    ↓
[2000-2600] Compliance Agent
    Plan holds → forfeitures → DepWDDetail → ACH prep → ACH calc
    ↓
EventBridge (file.completed)
```

## Key Design Decisions

### Rules are Data, Not Code
All business logic lives in DynamoDB tables. Agents are generic rule executors. Changing a validation rule, match formula, or plan hold condition requires updating a DynamoDB item — NOT redeploying agent code.

### DynamoDB → Redis → Agent
Every rule read follows a three-tier hierarchy: source-of-truth (DynamoDB) → hot cache (Redis with TTL) → agent logic. A batch of 6,000 records requires ~15 DynamoDB reads, not 6,000.

### Financial Calculations are Deterministic
The Transformation Agent uses NO AI inference for contribution calculations. Every match and ER amount is computed from explicit formulas. This is a regulatory requirement for auditability.

### NACHA Compliance: Bank Data Never in Cloud
The Compliance Agent's ACH services call an on-premises Token Service for bank account data. This data is held in memory only during file generation, then discarded. It is never written to Redis, DynamoDB, or S3.

### Client-Specific with GLOBAL Fallback
Calculation rules use a two-level lookup: first check `CLIENT#{planId}`, then fall back to `GLOBAL`. This enables per-client overrides without duplicating the entire rule set.

## Subroutine Traceability

Every service maps back to the original Stata subroutine it replaces:

| Stata Subroutine | Agent | Service |
|-----------------|-------|---------|
| subroutine-BadSSNs.do | Validator | SSNValidatorService |
| subroutine-FormatDatesandStrings.do | Validator | DateCleanerService |
| subroutine-employmentstatus.do | Validator | EmploymentStatusService |
| subroutine-Issues.do | Validator | IssueDetectorService |
| subroutine-ContribRateCheck.do | Validator | ContribRateCheckService |
| subroutine-calcmatch.do | Transformation | MatchCalcService |
| subroutine-calcERamt.do | Transformation | ERContribCalcService |
| subroutine-DuplicateEmployees.do | Transformation | DuplicateEmployeeService |
| subroutine-fixinghours.do | Transformation | HoursEstimationService |
| subroutine-negativepayroll.do | Transformation | NegativePayrollService |
| subroutine-totalsbyplanid.do | Transformation | TotalsByPlanService |
| subroutine-XML.do | Transformation | XMLGeneratorService |
| subroutine-exportingfiles.do | Transformation | FileExportService |
| subroutine-DestringNumbers.do | IDP | DestringService |
| subroutine-planholdPC.do | Compliance | PlanHoldService |
| subroutine-Forfeitures.do | Compliance | ForfeitureService |
| subroutine-achprep.do | Compliance | ACHPrepService |
| subroutine-achcalc.do | Compliance | ACHCalcService |
| subroutine-DepWDDetailPopulate.do | Compliance | DepWDDetailService |
| subroutine-getAdopterAssociations.do | Orchestrator | PipelineExecutor (routing) |
| subroutine-planidcrossreferencePC.do | Orchestrator | PipelineExecutor (routing) |
| subroutine-splitmonthPEO.do | Transformation | (Pipeline step 0550) |
| subroutine-dropvvariables.do | IDP | (Pipeline step 0400) |
| subroutine-statename2statecd.do | Validator | DateCleanerService |
