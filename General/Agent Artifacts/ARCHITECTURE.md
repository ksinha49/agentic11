# Architecture: AI-Powered Payroll Processing Platform

**BlueStar Retirement Services**
**Version 2.0 | February 24, 2026**
**Classification: CONFIDENTIAL**

---

## 1. Executive Summary

This document defines the technical architecture for BlueStar's AI-powered payroll processing platform. The system replaces the legacy Stata/Blue Prism workflow with a multi-agent architecture built on **Strands Agents SDK**, **Amazon Bedrock**, and **in-process Small Language Models (SLMs) co-deployed inside agent containers on ECS Fargate**.

The hybrid model-serving strategy is the defining architectural choice: high-volume agent tasks (IDP, Validation, Transformation) embed **CPU-native SLMs directly in-process** via `llama-cpp-python` — zero HTTP overhead, zero network hops, zero serialization. Complex reasoning agents (Orchestrator, Compliance) call **Bedrock API** models (Claude Sonnet, Claude Haiku) via LiteLLM for frontier intelligence. There is **no separate SLM service tier, no internal ALB for model routing, and no Ollama** — the SLM runs as a Python library inside the agent process itself.

### Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | Strands Agents SDK 1.x | AWS-native, Graph orchestration, MCP support, multi-model |
| SLM deployment | **In-process via llama-cpp-python** | **Zero latency: model loaded in agent process memory. ~2x faster than HTTP server mode.** |
| SLM models | Qwen3 0.6B, SmolLM3 3B, Phi-4 Mini 3.8B, Arcee AFM 4.5B | Purpose-built CPU-native sub-5B models. No GPU anywhere. |
| Frontier model access | Amazon Bedrock API | Claude Sonnet/Haiku for Orchestrator + Compliance agents |
| Model gateway | LiteLLM (Bedrock-only) | Unified API for Bedrock calls with fallback, cost tracking. SLM agents bypass LiteLLM entirely. |
| Structured outputs | Instructor + PydanticAI | Type-safe extraction with Pydantic validation and retry |
| Tool sharing | FastMCP | MCP servers for DynamoDB rules, SQL Server access, S3 ops |
| Document ingestion | MarkItDown | Convert XLSX/CSV/PDF to markdown for LLM consumption |
| Token management | tiktoken | Context window budgeting, chunking, cost estimation |
| Business rules | DynamoDB (8 tables) | Versioned rules engine consumed by all agents |
| Compliance | Bedrock Guardrails + On-prem Token Service | PII filtering, NACHA bank data isolation |

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                           │
│   Operations Dashboard  │  Admin Console  │  Monitoring Dashboard    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                     API GATEWAY (Amazon API Gateway)                 │
│              Routes: /files, /schemas, /reviews, /admin              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                   ORCHESTRATION LAYER                                │
│                                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────────┐   │
│  │ EventBridge │→ │ Strands Graph │→ │  SQS Processing Queues    │   │
│  │ (Events)    │  │ (Orchestrator)│  │  (IDP/Val/Xform/Comply)  │   │
│  └─────────────┘  └──────┬───────┘  └───────────────────────────┘   │
│                          │                                           │
│                  ┌───────▼───────┐                                   │
│                  │  LiteLLM      │ ← Bedrock-only (Orchestrator +   │
│                  │  (Bedrock API)│   Compliance agents)              │
│                  └───────┬───────┘                                   │
│                          │                                           │
│                  ┌───────▼───────────────────────────────────┐       │
│                  │           BEDROCK API                      │       │
│                  │  Claude Sonnet 4  │  Claude Haiku 3.5     │       │
│                  │  Bedrock Guardrails (PII/Compliance)       │       │
│                  └───────────────────────────────────────────┘       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              AGENT APPLICATION LAYER (ECS Fargate)                    │
│          SLM models embedded IN-PROCESS — zero network hops          │
│                                                                      │
│  ┌────────────────────┐  ┌────────────────────┐                     │
│  │ ORCHESTRATOR AGENT │  │  COMPLIANCE AGENT  │                     │
│  │ 3 services         │  │  6 services        │                     │
│  │ Model: Bedrock     │  │  Model: Bedrock    │                     │
│  │ (via LiteLLM)      │  │  (via LiteLLM)     │                     │
│  │ No local SLM       │  │  No local SLM      │                     │
│  └────────────────────┘  └────────────────────┘                     │
│                                                                      │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────┐  │
│  │    IDP AGENT       │  │  VALIDATOR AGENT   │  │ TRANSFORM    │  │
│  │    3 services      │  │  5 services        │  │ AGENT        │  │
│  │ ┌────────────────┐ │  │ ┌────────────────┐ │  │ 9 services   │  │
│  │ │ SmolLM3 3B     │ │  │ │ Arcee AFM 4.5B │ │  │┌────────────┐│  │
│  │ │ (IN-PROCESS)   │ │  │ │ (IN-PROCESS)   │ │  ││Phi-4 Mini  ││  │
│  │ │ llama-cpp-py   │ │  │ │ llama-cpp-py   │ │  ││(IN-PROCESS)││  │
│  │ │ Zero HTTP      │ │  │ │ Zero HTTP      │ │  ││llama-cpp-py││  │
│  │ └────────────────┘ │  │ └────────────────┘ │  │└────────────┘│  │
│  │ + Bedrock escalate │  │                    │  │              │  │
│  └────────────────────┘  └────────────────────┘  └──────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                       DATA LAYER                                     │
│                                                                      │
│  ┌─────────────┐ ┌───────┐ ┌───────────────┐ ┌──────────────────┐  │
│  │  DynamoDB   │ │ Redis │ │  S3 (Files)   │ │ SQL Server       │  │
│  │  (8 Rules   │ │ (Hot  │ │  (Raw/Output/ │ │ (On-Prem: STP    │  │
│  │   Tables)   │ │ Cache)│ │   Archive)    │ │  tables, Relius, │  │
│  └─────────────┘ └───────┘ └───────────────┘ │  PlanConnect)    │  │
│                                               └──────────────────┘  │
│  ┌──────────────────┐  ┌────────────────────────────────────────┐   │
│  │ FastMCP Servers   │  │  On-Premises Integration               │   │
│  │ (Tool Exposure)   │  │  Token Service (NACHA bank data)       │   │
│  └──────────────────┘  │  CapitalSG-64 (SQL Server ODBC)        │   │
│                         └────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Hybrid In-Process SLM Architecture

### 3.1 The Co-Deployment Pattern

Instead of running SLMs as separate services behind a load balancer, the IDP, Validator, and Transformation agents **embed their SLM directly in-process** using `llama-cpp-python` as a Python library. The model weights are loaded into the agent's process memory at container startup. LLM inference is a local function call — `llm.create_chat_completion()` — with zero HTTP serialization, zero network hops, and zero server overhead.

Research shows the HTTP server mode of llama.cpp introduces **~50% throughput penalty** compared to direct library calls. For an agent making 10+ AI calls per record across 6,000 records, eliminating this overhead is significant.

```
BEFORE (Separate SLM Service):                 AFTER (In-Process):
Agent → HTTP → ALB → SLM Container → response  Agent → llm.create_chat_completion() → result
       ~2-10ms network + serialization                  ~0ms (in-process function call)
       ~50% throughput penalty from HTTP                ~2x throughput vs HTTP mode
```

**Which agents embed SLMs vs. call Bedrock:**

| Agent | Model Strategy | Why |
|-------|---------------|-----|
| **IDP Agent** | **In-process: SmolLM3 3B** + Bedrock escalation for unknown schemas | High-volume parsing (6K records). Schema inference is rare (new vendors only). |
| **Validator Agent** | **In-process: Arcee AFM 4.5B** | Highest call volume (6K records × 14 rules = 84K evaluations). Must be fast. |
| **Transformation Agent** | **In-process: Phi-4 Mini 3.8B** | Deterministic transforms with AI-assisted field normalization. Speed critical. |
| **Orchestrator Agent** | **Bedrock: Claude Sonnet 4** (via LiteLLM) | Low call volume (~26 dispatch decisions per batch). Needs frontier reasoning for exception handling. |
| **Compliance Agent** | **Bedrock: Claude Sonnet 4** (via LiteLLM) | Complex compliance analysis, NACHA reasoning. Bedrock Guardrails integration for PII. |

### 3.2 CPU-Native SLM Models (2025-2026 Generation)

The 2025-2026 generation of SLMs are **designed from the ground up for CPU inference**. Research shows sub-1.5B models actually **outperform GPU** on multi-threaded CPU (Qwen2-0.5B achieves 1.31x speedup over GPU with Q4 quantization). The sweet spot for in-process Fargate deployment is **0.5B to 4.5B parameters**.

| Model | Params | RAM (Q4) | CPU tok/s | Agent | License |
|-------|--------|----------|-----------|-------|---------|
| **Arcee AFM 4.5B** | 4.5B | ~3 GB | 30-50 (200+ with Intel AMX/OpenVINO) | Validator | Apache 2.0 |
| **SmolLM3 3B** | 3B | ~2.2 GB | 20-35 | IDP | Apache 2.0 |
| **Phi-4 Mini 3.8B** | 3.8B | ~2.5 GB | 15-30 | Transformation | MIT |
| **Qwen3 0.6B** | 0.6B | ~400 MB | 50-80 | Routing (lightweight, optional) | Apache 2.0 |

All models use **Q4_K_M GGUF** quantization (4.5 effective bits/weight). No GPU required. No CUDA. No special hardware.

### 3.3 In-Process Integration: llama-cpp-python

Each SLM agent loads its model at container startup via `llama-cpp-python`:

```python
from llama_cpp import Llama

class InProcessSLM:
    """Wraps llama-cpp-python for in-process inference inside a Strands agent."""

    def __init__(self, model_path: str, n_ctx: int = 4096, n_threads: int = 4):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,      # Match Fargate vCPU count
            n_batch=512,              # Batch size for prompt processing
            verbose=False,
            chat_format="chatml",     # Adjust per model
        )
        self._warm_up()

    def _warm_up(self):
        """Warm up the model to avoid cold-start latency on first real request."""
        self.llm.create_chat_completion(
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=1,
        )

    def chat(self, messages: list, max_tokens: int = 512,
             temperature: float = 0.1) -> str:
        """Direct in-process inference — zero HTTP, zero serialization."""
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response["choices"][0]["message"]["content"]

    def structured_output(self, messages: list, response_format: dict,
                          max_tokens: int = 512) -> dict:
        """JSON mode for structured extraction."""
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            response_format=response_format,  # {"type": "json_object"}
            temperature=0.0,
        )
        return json.loads(response["choices"][0]["message"]["content"])
```

### 3.4 Agent Container Dockerfile (Single Container = Agent + SLM)

Each SLM agent is a **single Docker image** containing both the agent code AND the GGUF model:

```dockerfile
# Validator Agent + Arcee AFM 4.5B in-process
FROM python:3.12-slim

# Install dependencies
RUN pip install --no-cache-dir \
    llama-cpp-python==0.3.8 \
    strands-agents==1.27.0 \
    strands-agents-tools==0.1.0 \
    pydantic-ai==1.63.0 \
    instructor==1.14.5 \
    boto3==1.35.0 \
    redis==5.2.0 \
    pyodbc==5.2.0 \
    markitdown==0.1.5 \
    tiktoken==0.12.0 \
    fastmcp==3.0.2

# Copy agent code
COPY agent/ /app/agent/
COPY config/ /app/config/

# Copy GGUF model (baked into image from S3 during ECR build)
COPY models/arcee-afm-4.5b-Q4_K_M.gguf /models/model.gguf

WORKDIR /app
ENV MODEL_PATH=/models/model.gguf
ENV N_CTX=4096
ENV N_THREADS=4
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8080/health')"

CMD ["python", "-m", "agent.validator_main"]
```

**Image sizes (model baked in):**

| Agent Container | Model | Image Size | Fargate Spec | Cold Start |
|----------------|-------|-----------|-------------|-----------|
| bluestar-agent-idp | SmolLM3 3B (2.2 GB) | ~3.0 GB | 4 vCPU / 8 GB | ~15 sec |
| bluestar-agent-validator | Arcee AFM 4.5B (3 GB) | ~3.8 GB | 4 vCPU / 8 GB | ~20 sec |
| bluestar-agent-transform | Phi-4 Mini 3.8B (2.5 GB) | ~3.3 GB | 4 vCPU / 8 GB | ~18 sec |
| bluestar-agent-orchestrator | No local model | ~500 MB | 2 vCPU / 4 GB | ~5 sec |
| bluestar-agent-compliance | No local model | ~500 MB | 2 vCPU / 4 GB | ~5 sec |

### 3.5 Strands Agent with In-Process SLM

Strands Agents SDK supports custom model providers. The in-process SLM is wrapped as a Strands model:

```python
from strands import Agent, tool
from strands.models import Model
from llama_cpp import Llama
import os

class InProcessModel(Model):
    """Strands model provider backed by in-process llama-cpp-python."""

    def __init__(self):
        self.llm = Llama(
            model_path=os.environ["MODEL_PATH"],
            n_ctx=int(os.environ.get("N_CTX", "4096")),
            n_threads=int(os.environ.get("N_THREADS", "4")),
            chat_format="chatml",
            verbose=False,
        )

    def converse(self, messages, tools=None, **kwargs):
        # Convert Strands message format to llama-cpp format
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        response = self.llm.create_chat_completion(
            messages=formatted,
            max_tokens=kwargs.get("max_tokens", 512),
            temperature=kwargs.get("temperature", 0.1),
        )
        return self._format_strands_response(response)

# Validator Agent: SLM in-process, no network
validator_agent = Agent(
    model=InProcessModel(),  # AFM 4.5B loaded in this process
    system_prompt="""You are the Validator Agent for BlueStar payroll processing.
    Validate records against business rules from DynamoDB...""",
    tools=[validate_ssn, clean_dates, check_employment_status,
           detect_issues, check_contrib_rates, query_relius]
)
```

For the IDP Agent's schema-inference escalation, a **dual-model pattern** coexists in the same container:

```python
from strands.models.bedrock import BedrockModel

# Primary: in-process SmolLM3 3B (routine parsing)
idp_local_model = InProcessModel()

# Escalation: Bedrock Claude Haiku (unknown schema inference)
idp_bedrock_model = BedrockModel(
    model_id="anthropic.claude-3-5-haiku-20241022-v1:0"
)

@tool
def infer_unknown_schema(sample_rows: str) -> dict:
    """Escalate to Bedrock for unknown vendor schema inference."""
    inference_agent = Agent(
        model=idp_bedrock_model,  # Bedrock API call (rare)
        system_prompt="Analyze payroll file structure and map columns..."
    )
    return inference_agent(f"Map columns:\n{sample_rows}")

# IDP Agent: local SLM by default, Bedrock escalation via tool
idp_agent = Agent(
    model=idp_local_model,  # SmolLM3 3B in-process
    tools=[match_schema, parse_file, destring_fields,
           infer_unknown_schema]  # This tool uses Bedrock
)
```

### 3.6 Instructor Integration with In-Process SLM

Instructor works with `llama-cpp-python` directly for structured extraction with Pydantic validation:

```python
import instructor
from llama_cpp import Llama
from pydantic import BaseModel

# Patch llama-cpp-python with Instructor
llm = Llama(model_path="/models/model.gguf", n_ctx=4096, n_threads=4,
            chat_format="chatml")
client = instructor.patch(
    create=llm.create_chat_completion,
    mode=instructor.Mode.JSON,
)

class ValidationResult(BaseModel):
    ssn: str
    is_valid: bool
    issues: list[str]
    warnings: list[str]

# Structured extraction — in-process, no HTTP, with Pydantic retry
result = client(
    response_model=ValidationResult,
    messages=[{"role": "user", "content": f"Validate: {record_json}"}],
    max_retries=2,
)
```

### 3.7 Cost: In-Process vs. Separate SLM Services

| Architecture | Containers | Monthly Fargate | SLM Network | Total |
|-------------|-----------|----------------|-------------|-------|
| **In-Process (this design)** | **7 agent containers (3 with SLM baked in)** | **~$210/mo** | **$0 (no ALB, no SLM service)** | **~$210/mo** |
| Separate SLM services (previous) | 6 SLM + 7 agent + 2 LiteLLM = 15 | ~$565/mo | ~$20 ALB | ~$585/mo |
| Bedrock API only | 7 agent containers | ~$90/mo | $0 | ~$90 + ~$7,680 tokens = ~$7,770/mo |

**The in-process pattern saves ~$375/month** by eliminating the entire SLM service tier (6 containers, ALB, LiteLLM proxy for SLM routing) while simultaneously **eliminating all SLM network latency**.

---

## 4. LiteLLM: Bedrock API Gateway

### 4.1 Role

LiteLLM serves **only the Orchestrator and Compliance agents** — the two agents that call Bedrock API for frontier reasoning. The IDP, Validator, and Transformation agents **bypass LiteLLM entirely** because their SLMs are loaded in-process. LiteLLM runs as a lightweight sidecar or shared service, not as a universal proxy.

### 4.2 Configuration

```yaml
# litellm_config.yaml — Bedrock-only (SLM agents use in-process llama-cpp-python)
model_list:
  # --- Bedrock API Models (frontier reasoning) ---
  - model_name: bedrock/claude-sonnet
    litellm_params:
      model: bedrock/us.anthropic.claude-sonnet-4-20250514-v1:0
      aws_region_name: us-east-1

  - model_name: bedrock/claude-haiku
    litellm_params:
      model: bedrock/anthropic.claude-3-5-haiku-20241022-v1:0
      aws_region_name: us-east-1

  # --- Agent-Specific Routes ---
  - model_name: agent/orchestrator
    litellm_params:
      model: bedrock/claude-sonnet

  - model_name: agent/compliance
    litellm_params:
      model: bedrock/claude-sonnet

  - model_name: agent/idp-inference
    litellm_params:
      model: bedrock/claude-haiku  # Schema inference escalation (rare)

router_settings:
  routing_strategy: simple-shuffle
  num_retries: 3
  timeout: 60
  fallbacks:
    - bedrock/claude-sonnet: [bedrock/claude-haiku]

general_settings:
  master_key: sk-bluestar-litellm-key
  database_url: postgresql://litellm:pw@rds-litellm.bluestar.internal/litellm
  enable_spend_tracking: true
  max_budget: 300.00  # Monthly budget cap ($) — Bedrock only
  budget_duration: 1mo

litellm_settings:
  guardrails:
    - guardrail_name: bluestar-pii-filter
      litellm_params:
        guardrail: bedrock
        guardrailIdentifier: "bsrs-pii-guardrail-v1"
        guardrailVersion: "1"
        mode: "during_call"  # Applied on Compliance agent calls
```

### 4.3 Routing Strategy

```
Orchestrator Agent → LiteLLM → Bedrock Claude Sonnet (frontier reasoning)
Compliance Agent  → LiteLLM → Bedrock Claude Sonnet + Guardrails (PII filtered)
IDP Agent (rare)  → LiteLLM → Bedrock Claude Haiku (schema inference escalation)

IDP Agent (routine)       → IN-PROCESS SmolLM3 3B     (bypasses LiteLLM)
Validator Agent           → IN-PROCESS Arcee AFM 4.5B  (bypasses LiteLLM)
Transformation Agent      → IN-PROCESS Phi-4 Mini 3.8B (bypasses LiteLLM)
```

### 4.4 LiteLLM Deployment (Lightweight — Bedrock Only)

LiteLLM runs as a single lightweight container (1 vCPU / 2 GB) since it only proxies Bedrock API calls from 2 agents, not routing SLM traffic.

```dockerfile
FROM ghcr.io/berriai/litellm:main-latest
COPY litellm_config.yaml /app/config.yaml
ENV AWS_REGION=us-east-1
EXPOSE 4000
CMD ["litellm", "--config", "/app/config.yaml", "--port", "4000"]
```

---

## 5. Strands Agents SDK: Multi-Agent Orchestration

### 5.1 Graph-Based Pipeline

The Strands Graph pattern provides deterministic, conditional workflow control across the 5 agents. Each node is a Strands Agent with its own model assignment, system prompt, and tool set.

```python
from strands import Agent, tool
from strands.models import LiteLLMModel
from strands.multiagent import GraphBuilder

# --- Model configuration: Hybrid In-Process + Bedrock ---

# Orchestrator + Compliance: Bedrock via LiteLLM (frontier reasoning)
orchestrator_model = LiteLLMModel(
    model_id="agent/orchestrator",
    client_args={"api_base": "http://litellm-proxy:4000/v1"}
)
compliance_model = LiteLLMModel(
    model_id="agent/compliance",
    client_args={"api_base": "http://litellm-proxy:4000/v1"}
)

# IDP + Validator + Transform: In-process SLMs (zero network)
idp_model = InProcessModel()        # SmolLM3 3B loaded in this process
validator_model = InProcessModel()   # Arcee AFM 4.5B loaded in this process
transform_model = InProcessModel()   # Phi-4 Mini 3.8B loaded in this process


# --- Agent Definitions ---
orchestrator = Agent(
    model=orchestrator_model,
    system_prompt="""You are the Orchestrator Agent for BlueStar payroll processing.
    You load the processing pipeline from DynamoDB, dispatch steps to specialized agents,
    track workflow state, and handle exceptions. You coordinate the IDP, Validator,
    Transformation, and Compliance agents in the correct pipeline order.""",
    tools=[load_pipeline, dispatch_step, check_workflow_state,
           escalate_to_human, emit_event]
)

idp_agent = Agent(
    model=idp_model,
    system_prompt="""You are the IDP (Intelligent Document Processing) Agent.
    You identify vendor file formats via schema fingerprinting, parse columns into
    the canonical payroll record structure, and handle destringing. For unknown
    schemas, you analyze sample data to infer column mappings.""",
    tools=[match_schema, parse_file, destring_fields,
           learn_new_schema, read_s3_file]
)

validator_agent = Agent(
    model=validator_model,
    system_prompt="""You are the Validator Agent. You validate payroll records
    against business rules from DynamoDB: SSN validation (7 checks), date cleaning,
    employment status correction, issue/warning detection, and contribution rate
    verification. You cross-reference data against Relius via SQL Server.""",
    tools=[validate_ssn, clean_dates, check_employment_status,
           detect_issues, check_contrib_rates, query_relius]
)

transform_agent = Agent(
    model=transform_model,
    system_prompt="""You are the Transformation Agent. You execute deterministic
    data transformations: compensation calculation, employer match formula,
    ER contributions, duplicate consolidation, hours estimation, negative payroll
    handling, plan totals, XML generation, and file exports. ALL financial
    calculations are deterministic — you NEVER use AI inference for contribution
    amounts.""",
    tools=[calc_compensation, calc_match, calc_er_contrib,
           dedup_employees, estimate_hours, zero_negatives,
           calc_totals, generate_xml, export_files]
)

compliance_agent = Agent(
    model=compliance_model,
    system_prompt="""You are the Compliance Agent. You enforce regulatory
    compliance: plan hold evaluation, forfeiture application (Davis-Bacon aware),
    ACH generation (NACHA compliant — bank data NEVER cached), DepWDDetail
    population via stored procedure, and custodian deadline monitoring.""",
    tools=[evaluate_plan_hold, apply_forfeitures, prepare_ach,
           calculate_ach, update_depwd_detail, monitor_deadlines]
)


# --- Graph Orchestration ---
builder = GraphBuilder()
builder.add_node(orchestrator, "orchestrator")
builder.add_node(idp_agent, "idp")
builder.add_node(validator_agent, "validator")
builder.add_node(transform_agent, "transform")
builder.add_node(compliance_agent, "compliance")

# Pipeline flow
builder.add_edge("orchestrator", "idp")
builder.add_edge("idp", "validator")
builder.add_edge("validator", "transform",
    condition=lambda state: state.get("validation_passed", False))
builder.add_edge("validator", "orchestrator",
    condition=lambda state: not state.get("validation_passed", False))
builder.add_edge("transform", "compliance")
builder.add_edge("compliance", "orchestrator")  # Completion callback

builder.set_entry_point("orchestrator")
pipeline = builder.build()
```

### 5.2 Model Escalation Within Agents

The IDP Agent demonstrates the **dual-model in-process pattern**: its default model (SmolLM3 3B) is loaded in-process for zero-latency parsing, but the `infer_unknown_schema` tool creates a temporary Bedrock-backed agent for rare schema inference tasks.

```python
from strands import Agent
from strands.models import LiteLLMModel

# Primary: in-process SLM (loaded at container startup, zero latency)
idp_local = InProcessModel()  # SmolLM3 3B — see Section 3.3

# Escalation: Bedrock via LiteLLM (only for unknown vendor schemas)
idp_bedrock = LiteLLMModel(
    model_id="agent/idp-inference",
    client_args={"api_base": "http://litellm-proxy:4000/v1"}
)

@tool
def infer_unknown_schema(sample_rows: str, column_count: int) -> dict:
    """Escalate to Bedrock for unknown vendor schema inference (rare)."""
    inference_agent = Agent(
        model=idp_bedrock,  # Bedrock Claude Haiku (API call)
        system_prompt="Analyze payroll file structure and map columns."
    )
    return inference_agent(f"Analyze {column_count}-column file:\n{sample_rows}")

# IDP Agent: in-process SLM by default, Bedrock escalation via tool
idp_agent = Agent(
    model=idp_local,  # SmolLM3 3B — in-process, zero HTTP
    tools=[match_schema, parse_file, destring_fields,
           infer_unknown_schema]  # This tool internally calls Bedrock
)
```

**Latency comparison for the IDP Agent:**
- Routine parsing (99% of calls): ~0ms network overhead (in-process)
- Schema inference (1% of calls — new vendors): ~200-500ms (Bedrock API round-trip)

---

## 6. Instructor + PydanticAI: Structured Outputs

### 6.1 Instructor for LLM → Structured Data

Instructor wraps the LiteLLM completion call to guarantee Pydantic-validated structured outputs from both self-hosted SLMs and Bedrock models.

```python
import instructor
from litellm import completion
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date

client = instructor.from_litellm(completion)

class CanonicalPayrollRecord(BaseModel):
    """Single employee payroll record in canonical format."""
    planid: str
    ssn: str = Field(..., min_length=9, max_length=9)
    fname: str
    lname: str
    dob: Optional[date] = None
    doh: Optional[date] = None
    dot: Optional[date] = None
    dor: Optional[date] = None
    hours: float = Field(ge=0)
    salary: float = Field(ge=0)
    bonus: float = Field(default=0, ge=0)
    commissions: float = Field(default=0, ge=0)
    overtime: float = Field(default=0, ge=0)
    deferral: float = Field(default=0)
    rothdeferral: float = Field(default=0)
    match: float = Field(default=0)
    shmatch: float = Field(default=0)
    pshare: float = Field(default=0)
    shne: float = Field(default=0)
    loan: float = Field(default=0)

    @field_validator('ssn')
    @classmethod
    def validate_ssn_format(cls, v):
        if not v.isdigit():
            raise ValueError('SSN must be 9 digits')
        return v

class SchemaInferenceResult(BaseModel):
    """Result of AI-powered schema inference for unknown vendor."""
    vendor_name: str
    column_mappings: List[dict]
    confidence: float = Field(ge=0, le=1)
    file_format: str = Field(pattern=r'^(CSV|TSV|XLSX|FIXED)$')

class ValidationResult(BaseModel):
    """Structured validation output per record."""
    ssn: str
    is_valid: bool
    badssn: bool = False
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    corrected_fields: dict = Field(default_factory=dict)

# Usage with self-hosted SLM via LiteLLM
result = client.chat.completions.create(
    model="agent/validator",  # Routes to self-hosted Arcee AFM 4.5B (CPU-only)
    response_model=ValidationResult,
    messages=[{"role": "user", "content": f"Validate: {record_json}"}],
    max_retries=3,  # Auto-retries with validation error feedback
    api_base="http://litellm-proxy:4000/v1",
)
```

### 6.2 PydanticAI for Type-Safe Agent Logic

PydanticAI adds dependency injection and structured tool definitions to agents that need database access and complex validation.

```python
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

@dataclass
class ValidatorDeps:
    """Dependencies injected into Validator Agent at runtime."""
    plan_id: str
    batch_id: str
    dynamodb: boto3.resource
    redis_client: redis.Redis
    odbc_connection: pyodbc.Connection

validator_pydantic = Agent(
    OpenAIModel(
        model_name="agent/validator",
        base_url="http://litellm-proxy:4000/v1",
    ),
    deps_type=ValidatorDeps,
    output_type=ValidationResult,
    system_prompt="Validate payroll records against DynamoDB business rules.",
)

@validator_pydantic.tool
async def load_validation_rules(ctx: RunContext[ValidatorDeps],
                                 category: str) -> dict:
    """Load validation rules from DynamoDB with Redis caching."""
    cache_key = f"rules:validation:{category}"
    cached = ctx.deps.redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    table = ctx.deps.dynamodb.Table('bluestar-validation-rules')
    item = table.get_item(Key={
        'PK': f'CATEGORY#{category}',
        'SK': f'RULE#{category}_001'
    })['Item']
    ctx.deps.redis_client.setex(cache_key, 3600, json.dumps(item))
    return item

@validator_pydantic.tool
async def query_relius(ctx: RunContext[ValidatorDeps],
                        ssn: str) -> dict:
    """Cross-reference employee against Relius via ODBC."""
    cursor = ctx.deps.odbc_connection.cursor()
    cursor.execute(
        "SELECT firstname, lastname, dob FROM PersonalInfoByPlan WHERE planid=? AND ssn=?",
        ctx.deps.plan_id, ssn
    )
    row = cursor.fetchone()
    return {"fname": row[0], "lname": row[1], "dob": str(row[2])} if row else {}
```

---

## 7. FastMCP: Shared Tool Servers

### 7.1 DynamoDB Rules MCP Server

FastMCP exposes the DynamoDB business rules engine as MCP tools consumed by all agents via Strands' native MCP client.

```python
from fastmcp import FastMCP
import boto3
import json

mcp = FastMCP("BlueStar Business Rules",
              dependencies=["boto3", "redis"])

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
redis_client = redis.Redis(host='redis-prod.bluestar.internal', port=6379)

@mcp.tool
def get_client_config(plan_id: str, pay_freq: str) -> dict:
    """Load client processing configuration from DynamoDB."""
    cache_key = f"config:{plan_id}:{pay_freq}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    table = dynamodb.Table('bluestar-client-processing-config')
    # Get latest version
    response = table.query(
        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
        ExpressionAttributeValues={
            ':pk': f'CLIENT#{plan_id}',
            ':sk': f'CONFIG#{pay_freq}'
        },
        ScanIndexForward=False,
        Limit=1
    )
    item = response['Items'][0] if response['Items'] else {}
    redis_client.setex(cache_key, 3600, json.dumps(item, default=str))
    return item

@mcp.tool
def get_validation_rules(category: str) -> dict:
    """Load validation rule set by category."""
    cache_key = f"rules:validation:{category}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    table = dynamodb.Table('bluestar-validation-rules')
    response = table.query(
        KeyConditionExpression='PK = :pk',
        ExpressionAttributeValues={':pk': f'CATEGORY#{category}'}
    )
    items = response.get('Items', [])
    redis_client.setex(cache_key, 3600, json.dumps(items, default=str))
    return items

@mcp.tool
def get_calculation_rule(plan_id: str, calc_type: str) -> dict:
    """Load calculation rule with CLIENT→GLOBAL fallback."""
    cache_key = f"rules:calc:{plan_id}:{calc_type}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    table = dynamodb.Table('bluestar-business-calculation-rules')
    # Try client-specific first
    response = table.query(
        KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
        ExpressionAttributeValues={
            ':pk': f'CLIENT#{plan_id}',
            ':sk': f'CALC#{calc_type}'
        },
        ScanIndexForward=False, Limit=1
    )
    if not response['Items']:
        # Fall back to GLOBAL
        response = table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
            ExpressionAttributeValues={
                ':pk': 'GLOBAL',
                ':sk': f'CALC#{calc_type}'
            },
            ScanIndexForward=False, Limit=1
        )
    item = response['Items'][0] if response['Items'] else {}
    redis_client.setex(cache_key, 3600, json.dumps(item, default=str))
    return item

@mcp.tool
def get_plan_holds(plan_id: str) -> list:
    """Load all hold items for a plan (15-minute cache TTL)."""
    cache_key = f"hold:{plan_id}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    table = dynamodb.Table('bluestar-plan-hold-rules')
    response = table.query(
        KeyConditionExpression='PK = :pk',
        ExpressionAttributeValues={':pk': f'PLAN#{plan_id}'}
    )
    items = response.get('Items', [])
    redis_client.setex(cache_key, 900, json.dumps(items, default=str))  # 15 min
    return items

@mcp.tool
def get_pipeline_steps(plan_id: str, pay_freq: str) -> list:
    """Load ordered processing pipeline for a client."""
    cache_key = f"pipeline:{plan_id}:{pay_freq}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    table = dynamodb.Table('bluestar-processing-pipeline')
    response = table.query(
        KeyConditionExpression='PK = :pk',
        ExpressionAttributeValues={':pk': f'CLIENT#{plan_id}_{pay_freq}'},
        ScanIndexForward=True  # Returns steps in order
    )
    items = response.get('Items', [])
    redis_client.setex(cache_key, 3600, json.dumps(items, default=str))
    return items

@mcp.tool
def get_irs_limits(year: int) -> dict:
    """Load IRS annual limits for a given year."""
    cache_key = f"limits:{year}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    table = dynamodb.Table('bluestar-compliance-limits')
    item = table.get_item(Key={'PK': f'YEAR#{year}', 'SK': 'LIMITS'}).get('Item', {})
    redis_client.setex(cache_key, 86400, json.dumps(item, default=str))  # 24 hr
    return item

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
```

### 7.2 Connecting Agents to MCP Servers

```python
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp import StdioServerParameters, stdio_client

# Connect agent to DynamoDB rules MCP server
rules_mcp = MCPClient(lambda: stdio_client(
    StdioServerParameters(command="python", args=["mcp_rules_server.py"])
))

# Connect agent to SQL Server MCP server (for Relius cross-reference)
sql_mcp = MCPClient(lambda: stdio_client(
    StdioServerParameters(command="python", args=["mcp_sql_server.py"])
))

with rules_mcp, sql_mcp:
    validator_agent = Agent(
        model=validator_model,
        system_prompt="...",
        tools=[
            *rules_mcp.list_tools_sync(),  # DynamoDB rule tools
            *sql_mcp.list_tools_sync(),    # SQL Server query tools
        ]
    )
```

---

## 8. MarkItDown + tiktoken: Document Ingestion

### 8.1 File Ingestion Pipeline

```python
from markitdown import MarkItDown
import tiktoken

class PayrollFileIngester:
    def __init__(self, max_chunk_tokens: int = 8000):
        self.md = MarkItDown()
        self.enc = tiktoken.get_encoding("cl100k_base")  # ~±10-15% for Claude
        self.max_chunk = max_chunk_tokens

    def ingest(self, s3_path: str) -> dict:
        """Convert vendor file to LLM-ready markdown with token budgeting."""
        # Download from S3
        local_path = download_from_s3(s3_path)

        # Convert to markdown (handles XLSX, CSV, PDF, DOCX)
        result = self.md.convert(local_path)
        markdown = result.text_content

        # Token counting
        tokens = self.enc.encode(markdown)
        token_count = len(tokens)

        # Route to appropriate model based on token count
        if token_count < 2000:
            model_recommendation = "slm/phi-mini"  # Tiny file, use smallest SLM
        elif token_count < 8000:
            model_recommendation = "slm/smollm3-3b"  # Standard file, self-hosted
        else:
            model_recommendation = "bedrock/claude-haiku"  # Large file, needs big context

        # Chunk if exceeds SLM context window (8K for Mistral/Llama quantized)
        chunks = self._chunk(markdown, tokens) if token_count > self.max_chunk else [markdown]

        return {
            "markdown": markdown,
            "chunks": chunks,
            "token_count": token_count,
            "chunk_count": len(chunks),
            "model_recommendation": model_recommendation,
            "source_format": local_path.split('.')[-1].upper(),
        }

    def _chunk(self, text: str, tokens: list) -> list:
        """Split into overlapping chunks for multi-pass processing."""
        chunks = []
        overlap = 500  # Token overlap for context continuity
        start = 0
        while start < len(tokens):
            end = min(start + self.max_chunk, len(tokens))
            chunk_text = self.enc.decode(tokens[start:end])
            chunks.append(chunk_text)
            start = end - overlap
        return chunks
```

### 8.2 Integration with IDP Agent

```python
@tool
def read_and_parse_vendor_file(s3_path: str) -> dict:
    """Read vendor file from S3, convert to markdown, and prepare for parsing."""
    ingester = PayrollFileIngester(max_chunk_tokens=7500)
    result = ingester.ingest(s3_path)

    return {
        "markdown_preview": result["markdown"][:2000],  # First 2K chars for schema matching
        "total_tokens": result["token_count"],
        "chunks": result["chunks"],
        "source_format": result["source_format"],
        "model_recommendation": result["model_recommendation"],
    }
```

---

## 9. Bedrock Guardrails: Compliance Layer

### 9.1 PII Protection

```python
import boto3

bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

# Applied to Compliance Agent calls via LiteLLM guardrail config
guardrail_config = {
    "guardrailIdentifier": "bsrs-pii-guardrail-v1",
    "guardrailVersion": "1",
    "trace": "enabled"
}

# Guardrail definition (created via Bedrock console or API):
# - SSN: BLOCK (never output SSNs in agent responses)
# - Bank Account: BLOCK
# - Date of Birth: ANONYMIZE (replace with [DOB])
# - Address: ANONYMIZE
# - Custom regex for Employee IDs: r'\b\d{3}-\d{2}-\d{4}\b' → BLOCK
# - Custom regex for Plan Numbers: r'\b[A-Z]{3,20}\d{0,5}\b' → ALLOW (needed for processing)
```

### 9.2 NACHA Compliance Architecture

```
Agent in AWS VPC                    On-Premises
┌────────────────┐                  ┌──────────────────┐
│ Compliance     │  SEFA tokens     │ Token Service    │
│ Agent          │ ───────────────→ │                  │
│                │                  │ Resolves tokens  │
│ ACHCalcService │ ←─────────────── │ to actual bank   │
│                │  Bank data       │ routing/account  │
│ IN MEMORY ONLY │  (encrypted TLS) │ numbers          │
│ NEVER CACHED   │                  └──────────────────┘
│ NEVER LOGGED   │
│ NEVER TO S3    │
│ DISCARDED AFTER│
│ FILE GENERATION│
└────────────────┘
```

---

## 10. Infrastructure Summary

### 10.1 ECS Fargate Container Inventory

| Container | vCPU | Memory | Embedded SLM | Count | Monthly Cost (est.) | Role |
|-----------|------|--------|-------------|-------|-------------------|------|
| Orchestrator Agent | 2 | 4 GB | None (Bedrock) | 1 | ~$25 | Strands Graph coordinator |
| IDP Agent + SmolLM3 3B | 4 | 8 GB | SmolLM3 3B (2.2 GB GGUF) | 2 | ~$81 | File parsing + in-process SLM |
| Validator Agent + AFM 4.5B | 4 | 8 GB | Arcee AFM 4.5B (3 GB GGUF) | 2 | ~$81 | Validation + in-process SLM |
| Transform Agent + Phi-4 Mini | 4 | 8 GB | Phi-4 Mini 3.8B (2.5 GB GGUF) | 1 | ~$40 | Transformation + in-process SLM |
| Compliance Agent | 2 | 4 GB | None (Bedrock) | 1 | ~$25 | Compliance processing |
| LiteLLM Proxy | 1 | 2 GB | N/A | 1 | ~$12 | Bedrock API gateway |
| FastMCP Rules Server | 1 | 2 GB | N/A | 2 | ~$25 | DynamoDB tool exposure |
| FastMCP SQL Server | 1 | 2 GB | N/A | 1 | ~$12 | Relius/PlanConnect tools |
| **TOTAL** | | | | **11 containers** | **~$301/mo** | |

**Eliminated by in-process co-deployment (vs. separate SLM service architecture):**
- ~~6 SLM service containers~~ → SLMs embedded in 3 agent containers
- ~~Internal ALB for SLM routing~~ → No network between agent and model
- ~~2 LiteLLM proxy replicas for SLM routing~~ → 1 lightweight proxy for Bedrock only
- **8 fewer containers, ~$280/month savings, zero SLM network latency**
| LiteLLM Proxy | 2 | 4 GB | 2 | ~$50 | Model gateway (HA) |
| Orchestrator Agent | 2 | 4 GB | 1 | ~$25 | Strands Graph coordinator |
| IDP Agent | 2 | 4 GB | 2 | ~$50 | File parsing workers |
| Validator Agent | 2 | 4 GB | 2 | ~$50 | Validation workers |
| Transformation Agent | 2 | 4 GB | 2 | ~$50 | Transform workers |
| Compliance Agent | 2 | 4 GB | 1 | ~$25 | Compliance processing |
| FastMCP Rules Server | 1 | 2 GB | 2 | ~$25 | DynamoDB tool exposure |
| FastMCP SQL Server | 1 | 2 GB | 1 | ~$12 | Relius/PlanConnect tools |
| **TOTAL** | | | **19 containers** | **~$565/mo** | |

### 10.2 Bedrock API Costs (Frontier Models Only)

| Model | Usage | Monthly Est. |
|-------|-------|-------------|
| Claude Sonnet 4 (Orchestrator + Compliance) | ~50M tokens | ~$225 |
| Claude Haiku 3.5 (Schema inference, escalation) | ~10M tokens | ~$12 |
| Bedrock Guardrails (PII filtering) | ~5M tokens | ~$4 |
| **TOTAL Bedrock** | | **~$241/mo** |

### 10.3 Total Platform Cost

| Category | Monthly Cost |
|----------|-------------|
| ECS Fargate (11 containers, 3 with embedded SLMs) | ~$301 |
| Bedrock API (Orchestrator + Compliance + rare IDP escalation) | ~$241 |
| DynamoDB (PAY_PER_REQUEST) | ~$5 |
| Redis (ElastiCache r6g.medium) | ~$95 |
| S3 (storage + requests) | ~$15 |
| CloudWatch (logs + metrics) | ~$30 |
| **TOTAL** | **~$687/mo** |

**Cost reduction from in-process co-deployment:** The original separate-SLM-service architecture cost ~$971/mo. The in-process pattern eliminates 8 containers and the internal ALB, saving **~$284/month (29%)** while simultaneously removing all SLM network latency.

### 10.4 Technology Stack Summary

| Layer | Library/Service | Version | Purpose |
|-------|----------------|---------|---------|
| Agent Framework | Strands Agents SDK | 1.27.x | Multi-agent Graph orchestration |
| SLM Runtime | llama-cpp-python (library mode) | 0.3.8 | **In-process** CPU inference — zero HTTP, zero serialization |
| CPU-Native SLMs | SmolLM3 3B, Phi-4 Mini 3.8B, Arcee AFM 4.5B | Q4_K_M GGUF | Embedded in agent containers — no separate SLM service |
| Intel Optimization | OpenVINO + Optimum Intel | Latest | AMX-accelerated inference for AFM 4.5B on Intel Xeon |
| Model Gateway | LiteLLM Proxy | 1.81.x | Unified routing: SLM ↔ Bedrock |
| Frontier Models | Amazon Bedrock | API | Claude Sonnet/Haiku for complex reasoning |
| Structured Output | Instructor | 1.14.x | Pydantic-validated LLM extraction with retry |
| Type-Safe Agents | PydanticAI | 1.63.x | Dependency injection, structured tools |
| Tool Sharing | FastMCP | 3.0.x | MCP servers for DynamoDB/SQL tools |
| Document Ingestion | MarkItDown | 0.1.5 | XLSX/CSV/PDF → Markdown conversion |
| Token Management | tiktoken | 0.12.x | Token counting, chunking, cost estimation |
| Compliance | Bedrock Guardrails | Managed | PII filtering, content safety |
| Rules Engine | DynamoDB | Managed | 8 tables, versioned business rules |
| Cache | Redis (ElastiCache) | 7.x | Hot rule cache, session state |
| Operations DB | SQL Server (On-Prem) | Existing | STP tables, Relius, PlanConnect |
| File Storage | S3 | Managed | Raw/validated/output/archive files |
| Container Runtime | ECS Fargate | Managed | All containers including SLM inference |
| CI/CD | ECR + CodePipeline | Managed | Container image builds and deployments |

---

## 11. Deployment Architecture

### 11.1 VPC Layout

```
VPC: bluestar-ai-platform (10.0.0.0/16)
│
├── Public Subnets (10.0.1.0/24, 10.0.2.0/24)
│   └── ALB (external) → API Gateway
│
├── Private Subnets - Application (10.0.10.0/24, 10.0.11.0/24)
│   ├── ECS Fargate: Orchestrator Agent (2vCPU/4GB, Bedrock via LiteLLM)
│   ├── ECS Fargate: IDP Agent + SmolLM3 3B IN-PROCESS (4vCPU/8GB)
│   ├── ECS Fargate: Validator Agent + AFM 4.5B IN-PROCESS (4vCPU/8GB)
│   ├── ECS Fargate: Transform Agent + Phi-4 Mini IN-PROCESS (4vCPU/8GB)
│   ├── ECS Fargate: Compliance Agent (2vCPU/4GB, Bedrock via LiteLLM)
│   ├── ECS Fargate: LiteLLM Proxy (1vCPU/2GB, Bedrock-only)
│   ├── ECS Fargate: FastMCP servers
│   └── NAT Gateway → Bedrock API
│   (NO separate SLM subnet — models embedded in agent containers)
│
├── Private Subnets - Data (10.0.30.0/24, 10.0.31.0/24)
│   ├── ElastiCache Redis Cluster
│   ├── RDS PostgreSQL (LiteLLM spend tracking)
│   └── VPC Endpoints: DynamoDB, S3, Bedrock
│
└── Direct Connect / VPN → On-Premises
    ├── SQL Server (CapitalSG-64)
    ├── Token Service (NACHA)
    └── BlueStar SFTP Server (Azure)
```

### 11.2 Container Image Pipeline

```
Developer pushes code
    │
    ▼
CodePipeline triggered
    │
    ├── Build agent+SLM images (model GGUF baked in — single container per agent)
    │   └── ECR: bluestar-agent-orchestrator:v{tag}       (~500 MB, no SLM)
    │   └── ECR: bluestar-agent-idp:v{tag}                (~3.0 GB, SmolLM3 3B embedded)
    │   └── ECR: bluestar-agent-validator:v{tag}           (~3.8 GB, Arcee AFM 4.5B embedded)
    │   └── ECR: bluestar-agent-transform:v{tag}           (~3.3 GB, Phi-4 Mini embedded)
    │   └── ECR: bluestar-agent-compliance:v{tag}          (~500 MB, no SLM)
    │
    ├── Build infrastructure images
    │   └── ECR: bluestar-litellm-proxy:v{tag}   (~200 MB, Bedrock-only)
    │   └── ECR: bluestar-mcp-rules:v{tag}
    │   └── ECR: bluestar-mcp-sql:v{tag}
    │
    ▼
Deploy to ECS (Blue/Green via CodeDeploy)
```

---

## 12. Companion Documents

| Document | ID | Description |
|----------|-----|------------|
| Data Model Tech Spec | BSRS-DM-SPEC-001 v1.1 | DynamoDB schemas, SQL Server tables, Redis cache patterns |
| Agent Skills Package | bluestar-agent-skills | SKILL.md files for all 5 agents (26 services) |
| Skills ↔ Rules Integration | BSRS-SKILL-INT-001 | Runtime binding between skills and DynamoDB rules engine |
| DynamoDB Schemas (detail) | dynamodb-schemas.md | Full JSON item examples for all 8 DynamoDB tables |
| Agent Layer Diagram | agent-layer-architecture.jsx | Interactive React architecture visualization |
