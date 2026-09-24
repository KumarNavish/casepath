from casepath_api.agent_work.authority import ExistingCasePathAuthority
from casepath_api.agent_work.contracts import digest


def test_packet_identity_checks_current_binding_and_source_roster_without_loop_view():
    class Workspace:
        def __init__(self):
            self.record = {
                "claim_id": "claim-1",
                "state": {"claim_id": "claim-1", "binding": {"binding_sha256": "a" * 64}},
                "artifacts": [{"artifact_id": "notice", "sha256": "b" * 64,
                               "file_name": "notice.pdf", "media_type": "application/pdf",
                               "size_bytes": 12, "role": "attachment"}],
            }

        def detail(self, claim_id):
            assert claim_id == "claim-1"
            return self.record

    workspace = Workspace()
    authority = ExistingCasePathAuthority(lambda: workspace,
                                          lambda: (_ for _ in ()).throw(AssertionError("loop view called")))
    first = authority.packet_identity("claim-1")
    assert first == {"binding_sha256": "a" * 64,
                     "source_roster_sha256": digest(authority.list_sources("claim-1"))}
    workspace.record["artifacts"][0]["sha256"] = "c" * 64
    assert authority.packet_identity("claim-1")["source_roster_sha256"] != first["source_roster_sha256"]
    workspace.record["state"]["binding"]["binding_sha256"] = "d" * 64
    assert authority.packet_identity("claim-1")["binding_sha256"] == "d" * 64
