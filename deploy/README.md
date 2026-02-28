# `deploy/` — Infrastructure as Code

AWS deployment configurations for ECS Fargate hosting.

## Structure

```
deploy/
├── cdk/       # AWS CDK stack definitions (Stage 2)
└── ecs/       # ECS task definitions and service manifests (Stage 2)
```

## Planned Architecture

Each agent runs as a separate ECS Fargate task using the same Docker image with different CMD overrides:

| Service | vCPU | Memory | Model |
|---------|------|--------|-------|
| Orchestrator | 2 | 8 GB | Claude Sonnet (API) |
| IDP | 4 | 16 GB | SmolLM3 3B (in-process) |
| Validator | 4 | 16 GB | Arcee AFM 4.5B (in-process) |
| Transform | 4 | 16 GB | Phi-4 Mini 3.8B (in-process) |
| Compliance | 2 | 8 GB | Claude Sonnet (API) |
| API | 1 | 2 GB | None |

## CDK Stacks (Planned)

- **NetworkStack** — VPC, subnets, security groups
- **DataStack** — DynamoDB tables, S3 buckets, Redis (ElastiCache)
- **ComputeStack** — ECS cluster, task definitions, service discovery
- **ObservabilityStack** — CloudWatch dashboards, X-Ray tracing, alarms

## Current Status

Placeholder directories — CDK stacks will be implemented in Stage 2.
