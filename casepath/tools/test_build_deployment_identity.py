from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_deployment_identity as identity  # noqa: E402
import build_static_site as static_site  # noqa: E402


ASSET_REFERENCE = re.compile(
    r"[\"'](?P<path>assets/[A-Za-z0-9._/-]+\.(?:css|js|json))(?:\?[^\"']*)?[\"']"
)


def test_local_fallback_is_deterministic_and_never_aligned(tmp_path: Path) -> None:
    first = identity.build_payload({})
    second = identity.build_payload({"RENDER_GIT_COMMIT": "not-a-commit"})
    assert first == second
    assert first["release_id"] == "casepath-v20-reference-20260811"
    assert first["component_version"] == "20.0.0"
    assert first["source_commit"] == "unknown"
    assert first["alignment_eligible"] is False

    output = tmp_path / "deployment.json"
    identity.write_payload(output, first)
    assert json.loads(output.read_text(encoding="utf-8")) == first
    assert int(output.stat().st_mtime) == identity.SOURCE_DATE_EPOCH


def test_render_commit_is_normalized_and_alignment_eligible() -> None:
    commit = "ABCDEF0123456789ABCDEF0123456789ABCDEF01"
    payload = identity.build_payload({"RENDER_GIT_COMMIT": commit})
    assert payload["source_commit"] == commit.lower()
    assert payload["source_commit_source"] == "RENDER_GIT_COMMIT"
    assert payload["alignment_eligible"] is True


def test_explicit_source_commit_supports_non_render_delivery() -> None:
    commit = "0123456789ABCDEF0123456789ABCDEF01234567"
    payload = identity.build_payload({"CASEPATH_SOURCE_COMMIT": commit})
    assert payload["source_commit"] == commit.lower()
    assert payload["source_commit_source"] == "CASEPATH_SOURCE_COMMIT"
    assert payload["alignment_eligible"] is True


def test_curated_static_build_has_exact_runtime_inventory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / static_site.OUTPUT_DIRECTORY_NAME
    monkeypatch.setattr(static_site, "DEFAULT_OUTPUT", output)
    payload = static_site.build_static_site(output, {})

    assert payload["source_commit"] == "unknown"
    assert payload["alignment_eligible"] is False
    files, directories = static_site.inventory(output)
    assert files == static_site.PUBLIC_INVENTORY
    assert directories == static_site.PUBLIC_DIRECTORIES
    assert len(files) == 48
    assert {"corpus.html", "assets/corpus.css", "assets/corpus.js", "assets/corpus-index.json"} <= files
    assert {"method.html", "assets/method-guide.js", "assets/method-guide.css",
            "assets/method-guide-data.json"} <= files
    assert {"research.html", "assets/research-evidence.css", "assets/paired-study-evidence.json", "assets/native-study-evidence.json"} <= files
    assert {"assets/agent-work-v1.js", "assets/agent-work-v1.css"} <= files
    assert {"assets/claims-workspace-presentation-v1.js", "assets/claims-workspace-presentation-v1.css"} <= files
    assert json.loads((output / "deployment.json").read_text(encoding="utf-8")) == (
        payload
    )
    for relative_path in (
        *static_site.PUBLIC_ROOT_FILES,
        *static_site.PUBLIC_ASSETS,
    ):
        assert (output / relative_path).read_bytes() == (
            static_site.SOURCE_ROOT / relative_path
        ).read_bytes()
    built_index = (output / "index.html").read_text(encoding="utf-8")
    for relative_path in static_site.CONTENT_BOUND_ASSETS:
        digest = hashlib.sha256((output / relative_path).read_bytes()).hexdigest()
        assert built_index.count(f"{relative_path}?sha256={digest}") == 1

    assert not (output / "README.md").exists()
    assert not (output / "tools").exists()
    assert not (output / "releases").exists()
    assert not (output / "source-manifest.json").exists()
    assert not (output / "assets/guided-v15-lifecycle.js").exists()

    stale = output / "assets/legacy.js"
    stale.write_text("legacy", encoding="utf-8")
    static_site.build_static_site(output, {})
    static_site.verify_inventory(output)
    assert not stale.exists()


def test_curated_asset_allowlist_is_the_recursive_runtime_closure() -> None:
    discovered = {
        match.group("path")
        for entry_point in static_site.PUBLIC_ROOT_FILES
        if entry_point.endswith(".html")
        for match in ASSET_REFERENCE.finditer(
            (static_site.SOURCE_ROOT / entry_point).read_text(encoding="utf-8")
        )
    }
    pending = list(discovered)
    scanned: set[str] = set()
    while pending:
        relative_path = pending.pop()
        if relative_path in scanned:
            continue
        scanned.add(relative_path)
        if not relative_path.endswith(".js"):
            continue
        source = static_site.SOURCE_ROOT / relative_path
        nested = {
            match.group("path")
            for match in ASSET_REFERENCE.finditer(source.read_text(encoding="utf-8"))
        }
        pending.extend(sorted(nested - discovered))
        discovered.update(nested)

    assert discovered == set(static_site.PUBLIC_ASSETS)
    assert "assets/live-v16-viewer-fix.css" in discovered
    assert "assets/live-v18-law-normalize.js" in discovered
    assert "assets/foundation-live.css" in discovered
    assert "assets/foundation-live.js" in discovered
    assert "assets/insurance-protocol-v1.css" in discovered
    assert "assets/insurance-protocol-v1.js" in discovered
    assert "assets/claims-workspace-v1.css" in discovered
    assert "assets/claims-workspace-v1.js" in discovered


def test_insurance_product_asset_urls_are_content_bound() -> None:
    index = (static_site.SOURCE_ROOT / "index.html").read_text(encoding="utf-8")
    for relative_path in static_site.CONTENT_BOUND_ASSETS:
        digest = hashlib.sha256(
            (static_site.SOURCE_ROOT / relative_path).read_bytes()
        ).hexdigest()
        assert index.count(relative_path) == 1
        assert index.count(f"{relative_path}?sha256={digest}") == 1
    for relative_path, loader_path in static_site.DYNAMIC_CONTENT_BOUND_ASSETS.items():
        digest = hashlib.sha256(
            (static_site.SOURCE_ROOT / relative_path).read_bytes()
        ).hexdigest()
        loader = (static_site.SOURCE_ROOT / loader_path).read_text(encoding="utf-8")
        assert loader.count(relative_path) == 1
        assert loader.count(f"{relative_path}?sha256={digest}") == 1


def test_known_commit_requirement_fails_before_replacing_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / static_site.OUTPUT_DIRECTORY_NAME
    monkeypatch.setattr(static_site, "DEFAULT_OUTPUT", output)
    output.mkdir()
    sentinel = output / "keep-on-refusal.txt"
    sentinel.write_text("untouched", encoding="utf-8")

    try:
        static_site.build_static_site(output, {}, require_known_commit=True)
    except static_site.StaticSiteBuildError as exc:
        assert "identity is unknown" in str(exc)
    else:
        raise AssertionError("unknown commit unexpectedly produced an alignable build")
    assert sentinel.read_text(encoding="utf-8") == "untouched"

    commit = "ABCDEF0123456789ABCDEF0123456789ABCDEF01"
    payload = static_site.build_static_site(
        output,
        {"RENDER_GIT_COMMIT": commit},
        require_known_commit=True,
    )
    assert payload["source_commit"] == commit.lower()
    assert payload["alignment_eligible"] is True
    static_site.verify_inventory(output)
    assert not sentinel.exists()


def test_curated_static_build_refuses_symlink_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "sentinel.txt"
    sentinel.write_text("untouched", encoding="utf-8")
    output = tmp_path / static_site.OUTPUT_DIRECTORY_NAME
    monkeypatch.setattr(static_site, "DEFAULT_OUTPUT", output)
    output.symlink_to(target, target_is_directory=True)

    try:
        static_site.build_static_site(output, {})
    except static_site.StaticSiteBuildError as exc:
        assert "must not be a symlink" in str(exc)
    else:
        raise AssertionError("symlink output was unexpectedly accepted")
    assert sentinel.read_text(encoding="utf-8") == "untouched"


def test_curated_static_build_refuses_broad_output_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        static_site,
        "DEFAULT_OUTPUT",
        tmp_path / static_site.OUTPUT_DIRECTORY_NAME,
    )
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("untouched", encoding="utf-8")

    try:
        static_site.build_static_site(tmp_path, {})
    except static_site.StaticSiteBuildError as exc:
        assert "dedicated 'casepath-public' directory name" in str(exc)
    else:
        raise AssertionError("broad output directory was unexpectedly accepted")
    assert sentinel.read_text(encoding="utf-8") == "untouched"


def test_curated_static_build_refuses_foreign_dedicated_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        static_site,
        "DEFAULT_OUTPUT",
        tmp_path / "owned" / static_site.OUTPUT_DIRECTORY_NAME,
    )
    foreign = tmp_path / "foreign" / static_site.OUTPUT_DIRECTORY_NAME
    foreign.mkdir(parents=True)
    sentinel = foreign / "sentinel.txt"
    sentinel.write_text("untouched", encoding="utf-8")

    try:
        static_site.build_static_site(foreign, {})
    except static_site.StaticSiteBuildError as exc:
        assert "repository-owned" in str(exc)
    else:
        raise AssertionError("foreign dedicated directory was unexpectedly accepted")
    assert sentinel.read_text(encoding="utf-8") == "untouched"
