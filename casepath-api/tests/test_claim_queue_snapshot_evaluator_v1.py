from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import textwrap


def test_snapshot_consistency_uses_canonical_corpus_identity() -> None:
    repository = Path(__file__).resolve().parents[2]
    module_uri = (
        repository / "casepath-qa/claim-queue-snapshot-consistency-v1.mjs"
    ).as_uri()
    program = textwrap.dedent(
        """
        import { createHash } from 'node:crypto';
        import {
          canonicalQueueValue,
          queueSnapshotIsConsistent,
        } from __MODULE_URI__;

        const FLOAT_FIELDS = new Set(['confidence', 'cost_usd']);
        function claimLoopCanonical(value, field = null) {
          if (value === null || typeof value !== 'object') {
            if (typeof value === 'number'
              && Number.isInteger(value)
              && FLOAT_FIELDS.has(field)) {
              return value.toFixed(1);
            }
            return JSON.stringify(value);
          }
          if (Array.isArray(value)) {
            return `[${value.map(item => claimLoopCanonical(item)).join(',')}]`;
          }
          return `{${Object.keys(value).sort().map(
            key => `${JSON.stringify(key)}:${claimLoopCanonical(value[key], key)}`,
          ).join(',')}}`;
        }
        function claimLoopSha(value) {
          return createHash('sha256').update(claimLoopCanonical(value)).digest('hex');
        }
        function without(value, key) {
          return Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
        }
        function exactLoopSha(value, field) {
          return value[field] === claimLoopSha(without(value, field));
        }
        function clone(value) {
          return JSON.parse(JSON.stringify(value));
        }
        function row(index) {
          const claimId = `claim-${String(index).padStart(3, '0')}`;
          return {
            claim_id: claimId,
            revision: index + 1,
            state_sha256: claimLoopSha({ claim_id: claimId, kind: 'state' }),
            operational_projection: {
              projection_sha256: claimLoopSha({ claim_id: claimId, kind: 'projection' }),
            },
          };
        }
        function withProjectionSha(page) {
          return { ...page, projection_sha256: claimLoopSha(page) };
        }

        const rows = Array.from({ length: 150 }, (_, index) => row(index));
        const stateRoster = [...rows]
          .sort((left, right) => left.claim_id.localeCompare(right.claim_id))
          .map(value => ({
            claim_id: value.claim_id,
            revision: value.revision,
            state_sha256: value.state_sha256,
            operational_projection_sha256: value.operational_projection.projection_sha256,
          }));
        const common = {
          generated_at: '2026-09-04T00:00:00Z',
          corpus_identity: {
            aggregate_sha256: claimLoopSha('aggregate'),
            manifest_sha256: claimLoopSha('manifest'),
          },
          request_sha256: claimLoopSha('request'),
          state_roster_sha256: claimLoopSha(stateRoster),
          total_count: 150,
          facets: { readiness: { ready: 149, abstain: 1 } },
        };
        const encodedPages = [
          JSON.stringify(withProjectionSha({
            ...common,
            page_count: 100,
            items: rows.slice(0, 100),
            next_cursor: 'cursor-100',
          })),
          JSON.stringify(withProjectionSha({
            ...common,
            page_count: 50,
            items: rows.slice(100),
            next_cursor: null,
          })),
        ];
        const pages = encodedPages.map(value => JSON.parse(value));
        const options = { pageLimit: 100, stateRosterSha256: claimLoopSha };

        const changedCorpus = clone(pages);
        changedCorpus[1].corpus_identity.manifest_sha256 = claimLoopSha('changed');
        const changedRoster = clone(pages);
        changedRoster[1].state_roster_sha256 = claimLoopSha('changed');
        const duplicateRow = clone(pages);
        duplicateRow[1].items[49] = clone(duplicateRow[1].items[48]);
        const missingRow = clone(pages);
        missingRow[1].items.pop();

        process.stdout.write(JSON.stringify({
          separate_object_references:
            pages[0].corpus_identity !== pages[1].corpus_identity,
          canonical_corpus_identity_equal:
            canonicalQueueValue(pages[0].corpus_identity)
              === canonicalQueueValue(pages[1].corpus_identity),
          page_projection_hashes_valid:
            pages.every(page => exactLoopSha(page, 'projection_sha256')),
          page_projection_hashes_distinct:
            pages[0].projection_sha256 !== pages[1].projection_sha256,
          equal_identity_accepted: queueSnapshotIsConsistent(pages, options),
          changed_corpus_rejected: !queueSnapshotIsConsistent(changedCorpus, options),
          changed_state_roster_rejected: !queueSnapshotIsConsistent(changedRoster, options),
          duplicate_row_rejected: !queueSnapshotIsConsistent(duplicateRow, options),
          missing_row_rejected: !queueSnapshotIsConsistent(missingRow, options),
        }));
        """
    ).replace("__MODULE_URI__", json.dumps(module_uri))
    completed = subprocess.run(
        [
            shutil.which("node") or "node",
            "--input-type=module",
            "-e",
            program,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "separate_object_references": True,
        "canonical_corpus_identity_equal": True,
        "page_projection_hashes_valid": True,
        "page_projection_hashes_distinct": True,
        "equal_identity_accepted": True,
        "changed_corpus_rejected": True,
        "changed_state_roster_rejected": True,
        "duplicate_row_rejected": True,
        "missing_row_rejected": True,
    }
