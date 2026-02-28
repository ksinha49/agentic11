# `bluestar/orchestration` — Pipeline Orchestration

Abstraction over how pipeline steps are dispatched and tracked. Two implementations: SQS for dev/test and Strands Graph for production.

## Implementations

| File | Class | Use Case |
|------|-------|----------|
| `sqs_orchestrator.py` | `SQSOrchestrator` | Local development and testing |
| `strands_orchestrator.py` | `StrandsOrchestrator` | Production (Strands Agent Graph) |

## How It Works

```
1. Orchestrator loads pipeline steps from DynamoDB
2. For each step (in order):
   a. Check dependsOn / enabled flags
   b. Dispatch to the assigned agent
   c. Wait for completion callback
   d. Update workflow state
3. On failure: mark step FAILED, optionally escalate
4. On restart: skip COMPLETED steps, resume from last pending
```

## SQS Mode (Dev/Test)

Steps are dispatched as messages to per-agent SQS queues:

```
bluestar-orchestrator-queue
bluestar-idp-queue
bluestar-validator-queue
bluestar-transform-queue
bluestar-compliance-queue
```

## Strands Graph Mode (Production)

Builds a directed graph with 5 agent nodes and conditional edges. Wires Bedrock models for Orchestrator/Compliance and in-process SLMs for IDP/Validator/Transform.

## Current Status

Both orchestrators are **Stage 2 placeholders** with documented interfaces. The `IOrchestrator` and `IWorkflowState` protocols in `protocols.py` define the contract.
