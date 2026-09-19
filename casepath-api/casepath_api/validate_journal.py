"""Read-only semantic validation for the durable claim-loop journal."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

from .claim_loop_store import ClaimLoopStore, ClaimLoopStoreError
from .claim_workspace_v1 import (
    ClaimWorkspaceError,
    ClaimWorkspaceStore,
    WORKSPACE_LOOP_PREFIX,
    WORKSPACE_SESSION_ID,
)
from .foundation.common import canonical_json_bytes, digest_value
from .workspace_corpus import (
    CORPUS_PROFILES,
    PublicCorpus,
    WorkspaceCorpusError,
    default_public_corpus_root,
)


class JournalValidationError(RuntimeError):
    """Raised when the durable journal is not an exact replayable authority."""


def validate_journal(database: Path) -> dict[str, object]:
    descriptor = -1
    try:
        descriptor = os.open(
            database,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise JournalValidationError(
                "durable claim-loop database is not an unlinked regular file"
            )
    except OSError as exc:
        raise JournalValidationError(
            "durable claim-loop database is not readable"
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    loop_rows: list[dict[str, object]] = []
    event_count = 0
    with sqlite3.connect(
        f"file:{database.as_posix()}?mode=ro", uri=True
    ) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise JournalValidationError("durable database failed integrity check")
        application_objects = list(
            connection.execute(
                """SELECT type,name,tbl_name,sql FROM sqlite_master
                WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"""
            )
        )
        has_journal = any(row[1] == "claim_loop_events" for row in application_objects)
        if not has_journal:
            if application_objects or connection.execute("PRAGMA user_version").fetchone()[0] != 0:
                raise JournalValidationError(
                    "durable database lacks the journal but is not pristine"
                )
            receipt = {
                "contract": "casepath.read-only-journal-validation/1.0.0",
                "database_path": str(database.resolve()),
                "loop_count": 0,
                "event_count": 0,
                "loop_roster_sha256": digest_value([]),
            }
            return {**receipt, "receipt_sha256": digest_value(receipt)}
        workspace_stores: dict[str, ClaimWorkspaceStore] = {}
        identities = list(
            connection.execute(
                """SELECT session_id,loop_id,COUNT(*) AS event_count
                FROM claim_loop_events GROUP BY session_id,loop_id
                ORDER BY session_id,loop_id"""
            )
        )
        for identity in identities:
            session_id = identity["session_id"]
            loop_id = identity["loop_id"]
            rows = ClaimLoopStore._event_rows(connection, session_id, loop_id)
            is_workspace_session = session_id == WORKSPACE_SESSION_ID
            is_workspace_loop = loop_id.startswith(WORKSPACE_LOOP_PREFIX)
            if is_workspace_session != is_workspace_loop:
                raise JournalValidationError(
                    "workspace journal identity is outside its exact namespace"
                )
            try:
                if is_workspace_session:
                    # The import identifies which immutable bundled corpus to
                    # replay. It selects a verifier, never grants authority:
                    # _replay_rows still checks the entire hash chain and exact
                    # corpus identity/binding against that admitted bundle.
                    try:
                        imported = json.loads(rows[0]["event_json"])
                        manifest_sha256 = imported["command"]["corpus_identity"]["manifest_sha256"]
                    except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
                        raise ClaimWorkspaceError("workspace import corpus identity is invalid") from exc
                    if not isinstance(manifest_sha256, str):
                        raise ClaimWorkspaceError("workspace import corpus identity is unsupported")
                    if not workspace_stores:
                        for corpus_id in CORPUS_PROFILES:
                            corpus = PublicCorpus(default_public_corpus_root(corpus_id))
                            workspace_stores[corpus.identity["manifest_sha256"]] = (
                                ClaimWorkspaceStore.open_read_only(database, corpus)
                            )
                    if manifest_sha256 not in workspace_stores:
                        raise ClaimWorkspaceError("workspace import corpus identity is unsupported")
                    workspace_store = workspace_stores[manifest_sha256]
                    state = workspace_store._replay_rows(rows)
                    last_event_sha256 = state["last_event_sha256"]
                    state_sha256 = state["state_sha256"]
                else:
                    loop_state = ClaimLoopStore._replay_rows_uncached(
                        rows, session_id=session_id, loop_id=loop_id
                    )
                    last_event_sha256 = loop_state.last_event_sha256
                    state_sha256 = loop_state.state_sha256
            except (ClaimLoopStoreError, ClaimWorkspaceError, WorkspaceCorpusError) as exc:
                raise JournalValidationError(
                    f"durable claim-loop replay failed: {session_id}/{loop_id}"
                ) from exc
            event_count += len(rows)
            loop_rows.append(
                {
                    "session_id": session_id,
                    "loop_id": loop_id,
                    "event_count": len(rows),
                    "last_event_sha256": last_event_sha256,
                    "state_sha256": state_sha256,
                }
            )
    receipt = {
        "contract": "casepath.read-only-journal-validation/1.0.0",
        "database_path": str(database.resolve()),
        "loop_count": len(loop_rows),
        "event_count": event_count,
        "loop_roster_sha256": digest_value(loop_rows),
    }
    return {**receipt, "receipt_sha256": digest_value(receipt)}


def main() -> int:
    if len(sys.argv) != 2:
        raise JournalValidationError("usage: validate_journal DATABASE")
    receipt = validate_journal(Path(sys.argv[1]).resolve())
    sys.stdout.buffer.write(canonical_json_bytes(receipt) + b"\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JournalValidationError as exc:
        raise SystemExit(f"CasePath journal validation failed: {exc}") from exc
