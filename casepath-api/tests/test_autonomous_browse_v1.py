"""Browsing projection never changes the accepted case or invents a request."""
from casepath_api.autonomous_browse_v1 import customer_request
from casepath_api.autonomous_store_v1 import AutonomousStore


def test_request_is_an_exact_span_and_unknown_stays_unknown():
    for message, expected in [
        ('My specific request is: keep the deadline; the date is uncertain.', 'keep the deadline'),
        ('Mein Anliegen ist: Reparatur und Prüfung; der Betrag ist offen.', 'Reparatur und Prüfung'),
        ('For the request “urgent repair”: records are incomplete.', 'urgent repair'),
        ('The heating is broken. Could you help?', None),
        (None, None),
    ]:
        assert customer_request(message) == expected
        if expected:
            assert expected in message


def test_summary_request_does_not_change_native_state_or_journal(tmp_path):
    store = AutonomousStore(tmp_path / 'browse.db')
    state = store.intake({'title': 'My flat', 'message': 'My specific request is: inspect the heating; the cause is unknown.'}, idempotency_key='browse.request')
    rows = store.list_summaries()
    assert rows[0]['customer_request'] == 'inspect the heating'
    assert rows[0]['revision'] == state['revision']
    assert rows[0]['state_sha256'] == state['state_sha256']
    assert 'customer_request' not in state
    rows[0]['customer_request'] = 'caller rewrite'
    assert store.list_summaries()[0]['customer_request'] == 'inspect the heating'
    assert store.get(state['claim_id']) == state
