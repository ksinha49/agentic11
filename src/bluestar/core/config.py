"""Application configuration using pydantic-settings with grouped env prefixes."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = {"env_prefix": "BLUESTAR_LLM_"}

    provider: Literal["mock", "bedrock", "in_process"] = "mock"
    bedrock_model: str = "anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_haiku_model: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
    litellm_base_url: str = "http://litellm-proxy:4000/v1"
    slm_model_path: str = "/models/model.gguf"
    slm_n_threads: int = 4
    slm_n_ctx: int = 4096
    temperature: float = 0.0


class DynamoDBConfig(BaseSettings):
    """DynamoDB configuration."""

    model_config = {"env_prefix": "BLUESTAR_DYNAMO_"}

    table_suffix: str = ""  # "-dev", "-uat", or "" for prod
    region: str = "us-east-1"
    endpoint_url: str | None = None  # LocalStack override


class RedisConfig(BaseSettings):
    """Redis cache configuration."""

    model_config = {"env_prefix": "BLUESTAR_REDIS_"}

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    decode_responses: bool = True


class S3Config(BaseSettings):
    """S3 file storage configuration."""

    model_config = {"env_prefix": "BLUESTAR_S3_"}

    bucket: str = "bluestar-payroll-files"
    region: str = "us-east-1"
    endpoint_url: str | None = None  # LocalStack override


class SQSConfig(BaseSettings):
    """SQS queue configuration."""

    model_config = {"env_prefix": "BLUESTAR_SQS_"}

    region: str = "us-east-1"
    endpoint_url: str | None = None  # LocalStack override
    idp_queue_url: str = ""
    validator_queue_url: str = ""
    transform_queue_url: str = ""
    compliance_queue_url: str = ""
    human_review_queue_url: str = ""


class SQLServerConfig(BaseSettings):
    """On-premises SQL Server (Relius/PlanConnect) configuration."""

    model_config = {"env_prefix": "BLUESTAR_SQL_"}

    connection_string: str = ""
    pool_size: int = 5
    timeout: int = 30


class TokenServiceConfig(BaseSettings):
    """On-premises Token Service (NACHA compliance) configuration."""

    model_config = {"env_prefix": "BLUESTAR_TOKEN_"}

    base_url: str = "https://token-service.bluestar.internal"
    timeout: int = 10


class AppSettings(BaseSettings):
    """Root application settings aggregating all sub-configs."""

    model_config = {"env_prefix": "BLUESTAR_"}

    environment: Literal["dev", "uat", "prod"] = "dev"
    log_level: str = "INFO"

    llm: LLMConfig = LLMConfig()
    dynamodb: DynamoDBConfig = DynamoDBConfig()
    redis: RedisConfig = RedisConfig()
    s3: S3Config = S3Config()
    sqs: SQSConfig = SQSConfig()
    sql_server: SQLServerConfig = SQLServerConfig()
    token_service: TokenServiceConfig = TokenServiceConfig()
