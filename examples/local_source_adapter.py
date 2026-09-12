"""Minimal local source adapter for CasePath.

The example intentionally delegates persistence and exact-once semantics to the
audited local registry. It performs no network, model, credential, or external
system access.
"""

from pathlib import Path

from casepath_api.local_artifact_registry import LocalArtifactRegistryAdapterV1


def build_adapter(root: Path) -> LocalArtifactRegistryAdapterV1:
    """Return one isolated implementation of the source.register@1 capability."""

    return LocalArtifactRegistryAdapterV1(root)
