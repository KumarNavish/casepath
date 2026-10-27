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

    def __post_init__(self):
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(AZURE_HOST_SUFFIXES):
            raise SettingsError("the model endpoint must be an https Azure OpenAI resource")
        if parsed.path not in {"", "/"} or parsed.query:
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


def _flag(env, name, default):
    value = env.get(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes"}


def load_settings(env=None):
    env = os.environ if env is None else env
    model = None
    if env.get("CASEPATH_AZURE_OPENAI_ENDPOINT") or env.get("CASEPATH_AZURE_OPENAI_DEPLOYMENT"):
        deployment = env.get("CASEPATH_AZURE_OPENAI_DEPLOYMENT", "")
        model = ModelSettings(
            endpoint=env.get("CASEPATH_AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
            deployment=deployment,
            reasoning=_flag(env, "CASEPATH_MODEL_REASONING", "gpt-5" in deployment or "-o" in deployment),
            timeout_seconds=float(env.get("CASEPATH_MODEL_TIMEOUT_SECONDS", "120")),
            max_output_tokens=int(env.get("CASEPATH_MODEL_MAX_OUTPUT_TOKENS", "16000")),
            ca_bundle=env.get("CASEPATH_CA_BUNDLE") or None,
            trust_env=_flag(env, "CASEPATH_MODEL_TRUST_ENV", True),
        )
    if env.get("CASEPATH_IDENTITY_HEADER") and env.get("CASEPATH_DEV_USER"):
        raise SettingsError("choose either a trusted identity header or a development user, not both")
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
    )
