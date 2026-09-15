from pathlib import Path
from copy import deepcopy
import json
import pytest
from casepath_api import workspace_corpus as corpus_module


def test_original_150_profile_is_distinct_and_not_a_padding_of_development():
    full = corpus_module.PublicCorpus(corpus_module.default_public_corpus_root('synthetic-150'))
    dev = corpus_module.PublicCorpus(corpus_module.default_public_corpus_root())
    assert full.identity['claim_count'] == 150
    assert len(set(full.bindings)) == 150
    assert dev.identity['claim_count'] == 60
    assert len(set(full.bindings) - set(dev.bindings)) == 90
    assert full.identity['static_template_sha256'] == dev.identity['static_template_sha256']
    for claim_id in dev.bindings:
        assert full.binding(claim_id) == dev.binding(claim_id)
        assert full.claim(claim_id) == dev.claim(claim_id)
    assert full.manifest['contains_expected_outputs'] is False
    assert full.manifest['contains_sealed_targets'] is False
    assert full.identity['file_count'] == 660


def test_invalid_profile_is_rejected_before_read():
    with pytest.raises(corpus_module.WorkspaceCorpusError):
        corpus_module.default_public_corpus_root('../../other')
    with pytest.raises(corpus_module.WorkspaceCorpusError):
        corpus_module.default_public_corpus_root('made-up-150')


def test_all_150_original_claims_enter_the_same_workflow_without_accepting_evidence(tmp_path):
    from test_workspace_claim_loop_v1 import _system, _ensure
    from casepath_api.claim_workspace_intake_v1 import compile_intake_assessment
    corpus = corpus_module.PublicCorpus(corpus_module.default_workspace_corpus_root())
    storage, workspace, normal, facade = _system(tmp_path, corpus=corpus)
    seeded = workspace.seed(timestamp='2026-09-01T12:00:00+00:00')
    assert seeded['claim_count'] == 150 and seeded['new_import_count'] == 150
    assert workspace.seed(timestamp='2026-09-01T12:00:00+00:00')['new_import_count'] == 0
    checked = []
    for claim_id in sorted(corpus.bindings):
        initial = workspace.store.recover(claim_id)
        started = workspace.start(claim_id, idempotency_key='full150.start.'+claim_id,
                                  expected_revision=initial['revision'],
                                  timestamp='2026-09-01T12:00:01+00:00')['state']
        loop = _ensure(facade, claim_id, started)
        assert loop['claim_id'] == claim_id
        assert loop['loop_state']['observations'] == []
        assert loop['operational_projection']['readiness_scope'] == 'claim_process'
        assert loop['loop_state']['process']['nodes']
        assert loop['loop_state']['checklist']['items']
        assert loop['operational_projection']['pending_evidence_count'] > 0
        assert workspace.detail(claim_id)['message']['body'] == corpus.claim(claim_id)['customer_message']['body']
        checked.append(claim_id)
    assert len(checked) == len(set(checked)) == 150
