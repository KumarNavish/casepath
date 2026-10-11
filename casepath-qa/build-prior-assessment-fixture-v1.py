"""Export verified synthetic journal prefixes; no provider or production access.

Run with the prepared CasePath Python environment. By default JSON goes to
stdout; --output writes the same bundle to a caller-selected artifact file.
The semantic reader is the repository's existing, explicit isolated test double.
"""
import argparse
import base64
import json
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'casepath-api'), str(ROOT / 'casepath-api' / 'tests')]

from fastapi import FastAPI
from fastapi.testclient import TestClient
from casepath_api.autonomous_api_v1 import create_autonomous_router
from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from test_autonomous_controller_v1 import SemanticFixture, packet


class UpdatedEvidenceFixture(SemanticFixture):
    """The existing fixture with one source-cited changed condition."""
    def interpret(self, context, identity):
        proposal = super().interpret(context, identity)
        update = next((row for row in context['sources']
                       if row['file_name'] == 'later-statement.txt'), None)
        if update:
            condition = next(row for row in proposal['result']['conditions']
                             if row['flag'] == 'family_home')
            condition.update(verdict='false', summary='The later source says this is not a family home.',
                             citations=[{'artifact_id': update['artifact_id'], 'quote': update['text']}])
            proposal['result']['documents'] = []
        return proposal


class FailedReassessmentFixture(SemanticFixture):
    def interpret(self, context, identity):
        raise ValueError('Explicit isolated fixture failure; no reassessment proposal accepted.')


class FixtureClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def build_fixture():
    # Journal timestamps contribute to hashes. Freeze the isolated fixture clock,
    # so repeated builds export byte-identical accepted states and prefixes.
    with patch('casepath_api.autonomous_store_v1.datetime', FixtureClock):
        return _build_fixture()


def _build_fixture():
    with tempfile.TemporaryDirectory(prefix='casepath-prior-assessment-') as temporary:
        store = AutonomousStore(Path(temporary) / 'synthetic.sqlite3')
        policy = PublicCorpus(default_workspace_corpus_root()).static_policy()
        reader = UpdatedEvidenceFixture()
        service = AutonomousController(store, policy, reader)
        app = FastAPI()
        app.include_router(create_autonomous_router(lambda: service))
        base = '/api/claim-loops/v1/autonomous'
        try:
            with TestClient(app) as client:
                claim_id = store.intake(packet(), 'qa.prior-assessment.intake')['claim_id']
                before = service.run(claim_id)
                before_json = json.dumps(before, sort_keys=True, separators=(',', ':'))
                revisions = {'assessed': before['revision']}
                states = {'assessed': before}
                snapshot = client.get(f'{base}/claims/{claim_id}/snapshot')
                snapshot.raise_for_status()
                snapshots = {'assessed': snapshot.json()}
                arrival = store.add_sources(claim_id, [{
                    'file_name': 'later-statement.txt', 'media_type': 'text/plain',
                    'content_base64': base64.b64encode(
                        b'The earlier spouse notice is withdrawn. This is not our family home.').decode(),
                }], expected_revision=before['revision'], expected_state_sha256=before['state_sha256'],
                    idempotency_key='qa.prior-assessment.arrival')
                states['arrived'] = arrival
                revisions['arrived'] = arrival['revision']
                snapshots['arrived'] = client.get(f'{base}/claims/{claim_id}/snapshot').json()
                service.model = None
                deferred = service.run(claim_id)
                assert deferred['deferral']['code'] == 'model_unavailable'
                assert deferred['graph'] == before['graph']
                assert len(deferred['acquired_sources']) == 3
                states['deferred'] = deferred
                revisions['deferred'] = deferred['revision']
                snapshots['deferred'] = client.get(f'{base}/claims/{claim_id}/snapshot').json()
                # The exact unavailable-reader input is idempotent on retry.
                retry = service.run(claim_id)
                assert retry == deferred
                states['same_roster_retry'] = retry
                snapshots['same_roster_retry'] = client.get(f'{base}/claims/{claim_id}/snapshot').json()
                # Failed work stays failed. Fork the verified journal for this
                # independent branch rather than authorize a retry in the UI.
                failure_path = Path(temporary) / 'failed.sqlite3'
                with store.journal.connect() as connection, sqlite3.connect(failure_path) as backup:
                    connection.backup(backup)
                failed_service = AutonomousController(AutonomousStore(failure_path), policy, FailedReassessmentFixture())
                failed_app = FastAPI()
                failed_app.include_router(create_autonomous_router(lambda: failed_service))
                failure_prefixes = {}
                try:
                    failed = failed_service.run(claim_id)
                    assert failed['deferral']['code'] == 'verification_deferred'
                    assert failed['graph'] == before['graph']
                    assert failed['receipts'] == before['receipts']
                    states['failed'] = failed
                    revisions['failed'] = failed['revision']
                    with TestClient(failed_app) as failed_client:
                        snapshots['failed'] = failed_client.get(f'{base}/claims/{claim_id}/snapshot').json()
                        for sequence in range(1, failed['revision'] + 1):
                            response = failed_client.get(f'{base}/claims/{claim_id}/replay?through_seq={sequence}')
                            response.raise_for_status()
                            failure_prefixes[str(sequence)] = response.json()
                finally:
                    failed_service.shutdown()
                service.model = reader
                after = service.run(claim_id)
                assert after['graph']['conditions']['family_home']['verdict'] == 'false'
                spouse = next(row for row in after['evaluation']['documents']
                              if row['document_type'] == 'spouse_notice_copy')
                assert spouse['route_state'] == 'not_needed' and spouse['request'] is False
                assert after['actions'][:len(before['actions'])] == before['actions']
                assert len(reader.calls) == 4
                states['reassessed'] = after
                revisions['reassessed'] = after['revision']
                snapshots['reassessed'] = client.get(f'{base}/claims/{claim_id}/snapshot').json()
                assert json.dumps(before, sort_keys=True, separators=(',', ':')) == before_json
                prefixes = {}
                for sequence in range(1, after['revision'] + 1):
                    response = client.get(f'{base}/claims/{claim_id}/replay?through_seq={sequence}')
                    response.raise_for_status()
                    prefixes[str(sequence)] = response.json()
                assert prefixes[str(before['revision'])]['state'] == before
                sources = {}
                for descriptor in after['source_descriptors']:
                    artifact_id = descriptor['artifact_id']
                    response = client.get(f'{base}/sources/{claim_id}/{artifact_id}/text')
                    response.raise_for_status()
                    sources[f'{claim_id}/{artifact_id}'] = response.json()
                return {'fixture': 'existing SemanticFixture, zero inference',
                        'branches': {'main': ['assessed', 'arrived', 'deferred', 'same_roster_retry', 'reassessed'],
                                     'independent_failed_copy': ['assessed', 'arrived', 'deferred', 'failed']},
                        'claim_id': claim_id, 'revisions': revisions, 'states': states,
                        'snapshots': snapshots, 'prefixes': prefixes, 'failure_prefixes': failure_prefixes, 'sources': sources,
                        'knowledge': service.knowledge.view(), 'reader_calls': len(reader.calls)}
        finally:
            service.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    arguments = parser.parse_args()
    encoded = json.dumps(build_fixture(), indent=2, sort_keys=True) + '\n'
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded)
    else:
        sys.stdout.write(encoded)
