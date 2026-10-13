Actual native v1-to-v2 reference evidence from product commit
`56ca8f1a183dd073e1ee1061d70fac1913355a6b`, base
`2af5e4897284b0b1eab7a82a4e98273ae481b77b`.

The compressed fixture contains 9 completed legacy v1 runs followed by 9 real
v2 source admissions and completed v2 runs, 393 GET replay prefixes, 57 physical
source text/raw responses, 9 actual unprocessed GET snapshots captured before
admission, and 9 complete `before_v1_snapshots`. Every prefix retains the exact
head-bound `replay_start`; its reset state/event hashes identify the accepted
`process.prepared` event. Every original, v1 and v2 source remains present.
No provider transport, budget operation, production state, full suite or source
seal was used.

Fixture gzip SHA256:
`5864980a9016bd332dd63537fb86b3ba0bcbbd2f74c98b2541177c078971cfe8`.
Uncompressed JSON SHA256:
`ba3ddf796cb39489e47158ca6b69d53be1866e365afa0363a7b49665af7224ce`.
See `native-receipt.json` for exact per-claim revisions, state hashes and resets;
`runtime-source-identity.json` pins all authored and immutable legacy bytes.

Focused verification passed: 37 cases, then 3 final pin/metadata smoke cases.
The only warnings were existing PyMuPDF deprecations. Initial missing ignored
PDF/image setup files were generated through standard repository scripts. The
first export completed all native cases but failed while writing its JSON
because `/tmp` was full; its failure log is retained. The successful retry used
separate workspace temporary/output paths and the same product bytes.

Successful export command, from the product checkout:

```sh
HOME=/tmp/casepath-reference-polish-20261013/export-home \
TMPDIR=/workspace/casepath-reference-polish-evidence-20261013/export-tmp \
PYTHONPATH=$PWD/casepath-api PYTHONDONTWRITEBYTECODE=1 \
/workspace/casepath-release-ae0-inventory/.runtime/casepath-dev-v2/venv/bin/python \
/tmp/casepath-reference-polish-20261013/export-native-v1-v2-fixture.py \
/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json
```

Decompress the gzip to a local JSON file and set `CASEPATH_REFERENCE_FIXTURE` to
that path for the existing browser-fixture seam. `earlier_context` is null;
`before_v1_snapshots` supplies the actual prior completed assessments.
