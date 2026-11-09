"""Settings come from the environment of the internal runtime, never from Git.

No endpoint, deployment, tenant or credential is stored in this repository.
The model endpoint must be an Azure OpenAI resource host, so the application
cannot be pointed at a personal or third-party model provider by accident.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse

AZURE_HOST_SUFFIXES = (".openai.azure.com", ".cognitiveservices.azure.com", ".services.ai.azure.com")
DATABRICKS_HOST_SUFFIXES = (".azuredatabricks.net",)
PROVIDERS = {"azure_openai": AZURE_HOST_SUFFIXES, "databricks": DATABRICKS_HOST_SUFFIXES}


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class ModelSettings:
    endpoint: str
    deployment: str
    reasoning: bool
    timeout_seconds: float
    max_output_tokens: int
    ca_bundle: str | None
    trust_env: bool
    api_version: str | None = None
    reading_deployment: str | None = None
    gateway_hosts: tuple = ()
    provider: str = "azure_openai"
    chat_path: str | None = None
    auth: str = "app"  # "user": call the model as the person who started the run, with the token the platform forwards
    api: str = "chat"  # for a workspace model: "chat" (OpenAI-compatible chat completions) or "messages" (the Messages API)
    forced_tools: bool = True  # False where the endpoint refuses a forced tool choice

    def __post_init__(self):
        if self.provider not in PROVIDERS:
            raise SettingsError(f"the model provider is one of {', '.join(PROVIDERS)}")
        if self.api not in {"chat", "messages"}:
            raise SettingsError("CASEPATH_MODEL_API is chat or messages")
        if self.auth not in {"app", "user"} or (self.auth == "user" and self.provider != "databricks"):
            raise SettingsError("CASEPATH_MODEL_AUTH is app, or user for a Databricks workspace model")
        parsed = urlparse(self.endpoint)
        gateway = parsed.hostname in self.gateway_hosts  # an API gateway in front of the resource, named exactly
        if parsed.scheme != "https" or not parsed.hostname or not (gateway or parsed.hostname.endswith(PROVIDERS[self.provider])):
            raise SettingsError("the model endpoint must be an https Azure OpenAI resource, a Databricks workspace "
                                "(with CASEPATH_MODEL_PROVIDER=databricks) or a configured gateway host")
        if (parsed.path not in {"", "/"} and not gateway) or parsed.query:
            raise SettingsError("give the resource endpoint only; the client adds /openai/v1/")
        if not self.deployment or "/" in self.deployment:
            raise SettingsError("an exact deployment name is required")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    catalogue_dir: Path | None
    model: ModelSettings | None
    identity_header: str | None
    dev_user: str | None
    max_upload_bytes: int
    max_text_chars: int
    reading_workers: int = 6
    run_workers: int = 2
    page_image_side: int = 1700
    identity_format: str = "plain"
    identity_user_claim: str = "sub"
    identity_roles_claim: str = "roles"
    required_role: str | None = None
    allowed_users: frozenset = frozenset()
    volume: str | None = None


def _flag(env, name, default):
    value = env.get(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes"}


def load_settings(env=None):
    env = os.environ if env is None else env
    model = None
    provider = env.get("CASEPATH_MODEL_PROVIDER", "azure_openai").strip().lower() or "azure_openai"
    if provider == "databricks":  # a model in a Databricks workspace; the endpoint is the workspace
        endpoint, deployment = env.get("CASEPATH_MODEL_ENDPOINT") or env.get("DATABRICKS_HOST", ""), env.get("CASEPATH_MODEL", "")
        if endpoint and not endpoint.startswith("https://"):
            endpoint = "https://" + endpoint
    else:
        endpoint, deployment = env.get("CASEPATH_AZURE_OPENAI_ENDPOINT", ""), env.get("CASEPATH_AZURE_OPENAI_DEPLOYMENT", "")
    if endpoint or deployment:
        model = ModelSettings(
            endpoint=endpoint.rstrip("/"),
            deployment=deployment,
            reasoning=provider == "azure_openai" and _flag(env, "CASEPATH_MODEL_REASONING", "gpt-5" in deployment or "-o" in deployment),
            timeout_seconds=float(env.get("CASEPATH_MODEL_TIMEOUT_SECONDS", "120")),
            max_output_tokens=int(env.get("CASEPATH_MODEL_MAX_OUTPUT_TOKENS", "16000")),
            ca_bundle=env.get("CASEPATH_CA_BUNDLE") or None,
            trust_env=_flag(env, "CASEPATH_MODEL_TRUST_ENV", True),
            api_version=env.get("CASEPATH_AZURE_OPENAI_API_VERSION") or None,
            reading_deployment=env.get("CASEPATH_AZURE_OPENAI_READING_DEPLOYMENT") or env.get("CASEPATH_READING_MODEL") or None,
            provider=provider, chat_path=env.get("CASEPATH_CHAT_PATH") or None,
            auth=(env.get("CASEPATH_MODEL_AUTH") or "app").strip().lower(),
            api=(env.get("CASEPATH_MODEL_API") or "chat").strip().lower(),
            forced_tools=_flag(env, "CASEPATH_MODEL_FORCED_TOOLS", True),
            gateway_hosts=tuple(h.strip().lower() for h in env.get("CASEPATH_MODEL_GATEWAY_HOSTS", "").split(",") if h.strip()),
        )
    if env.get("CASEPATH_IDENTITY_HEADER") and env.get("CASEPATH_DEV_USER"):
        raise SettingsError("choose either a trusted identity header or a development user, not both")
    identity_format = env.get("CASEPATH_IDENTITY_FORMAT", "plain").strip().lower()
    if identity_format not in {"plain", "jwt"}:
        raise SettingsError("CASEPATH_IDENTITY_FORMAT is plain or jwt")
    required_role = env.get("CASEPATH_REQUIRED_ROLE") or None
    if required_role and not (env.get("CASEPATH_IDENTITY_HEADER") and identity_format == "jwt"):
        raise SettingsError("a required role needs a trusted identity header with CASEPATH_IDENTITY_FORMAT=jwt")
    catalogue = env.get("CASEPATH_WORKFLOW_CATALOGUE")
    return Settings(
        data_dir=Path(env.get("CASEPATH_DATA_DIR", ".casepath-internal")).resolve(),
        catalogue_dir=Path(catalogue).resolve() if catalogue else None,
        model=model,
        identity_header=env.get("CASEPATH_IDENTITY_HEADER") or None,
        dev_user=env.get("CASEPATH_DEV_USER") or None,
        max_upload_bytes=int(env.get("CASEPATH_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024))),
        max_text_chars=int(env.get("CASEPATH_MAX_TEXT_CHARS", "4000000")),
        reading_workers=int(env.get("CASEPATH_READING_WORKERS", "6")),
        run_workers=int(env.get("CASEPATH_RUN_WORKERS", "2")),
        page_image_side=int(env.get("CASEPATH_PAGE_IMAGE_SIDE", "1700")),
        identity_format=identity_format,
        identity_user_claim=env.get("CASEPATH_IDENTITY_USER_CLAIM", "sub"),
        identity_roles_claim=env.get("CASEPATH_IDENTITY_ROLES_CLAIM", "roles"),
        required_role=required_role,
        volume=env.get("CASEPATH_VOLUME") or None,
        allowed_users=frozenset(u.strip().lower() for u in env.get("CASEPATH_ALLOWED_USERS", "").split(",") if u.strip()),
    )
