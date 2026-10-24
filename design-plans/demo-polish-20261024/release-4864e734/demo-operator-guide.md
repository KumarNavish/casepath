# CasePath presenter and restart runbook

Tested and deployed source: 4864e7347c299bf1b580a5b35667635bc1c47f15

## Public demonstration

Open [the public presentation](https://casepath-autonomous.kumarnavish.chatgpt.site/?present=1#autonomous/demonstration). Its purpose appears while admission completes, then playback starts automatically. Do not wait for or click a manual Start control before admission. The six acts last 88.05 seconds and display the 4× indicator. Use the actual visible transport controls once available; pause on dense evidence or legal text when presenting.

The recorded cold-opening inspection observed admission after 21,297 ms and paused there. It is a separate measurement from the [continuous film](release/published-browser-4864e734/public-walkthrough.webm). The earlier baseline only recorded a first-active observation at 23,758 ms; its old harness then waited for a manual-start condition that was not applicable. No completed exact baseline or calculated speedup is claimed.

## Show the completed engineering example

Use a 1440 × 900 desktop viewport for the reference layout.

1. Open [the earlier case](http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_f69b1747447bc221). Select Process builder and inspect Compare both complete notices and its connection. Keep the original tenant and spouse documents available in the source rail.
2. Open [the receiving case](http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_0e538990cc6ba7ef) and choose Result checker. The actual historical Before/After comparison is visible immediately.
3. Show the receiving case's own 30. Juni and 31. Juli source passages. Selecting a source fact opens that case's original source.
4. Show the exact saved version 1 and its source/version provenance. Library version 2 does not silently replace the receiving case's existing pin.
5. Show the additional prerequisite and affected-step ordinal. Open the full-process disclosure when the complete 12-node graph is useful.
6. Show that Preserve challenge or extension deadline remains the next protective action and that the original evidence connection remains. Process validation is separate from approval of a claim outcome.

The [operator walkthrough](sealed-browser/review-walkthrough.webm) records the actual edit, preview, acceptance, saved version and later-case reuse in the final standalone recording, completed with explicit TAP output after the full release gate. Its Test handler events are engineering QA. An earlier standalone child test passed but its parent wrapper failed while parsing the default spec summary; that attempt is preserved separately. The full gate itself also passed the mandatory review suite, but its launcher did not export recording artifacts.

## Local workspace identities

- Standard workspace: http://127.0.0.1:4173/?journey=review&view=northstar
- Retained engineering example: http://127.0.0.1:4194/?journey=review&view=northstar
- Engineering session observed during verification: cp-polish-20261024-engineering-demo-4194
- Standard session observed during verification: cp-polish-20261024-standard-workspace-4173

The [engineering promotion receipt](release/engineering-promotion-verified-4864.json) identifies the current code, process, preserved previous-server bytes, original owner/copy receipts, and exact current data/view fingerprints. The [standard promotion receipt](standard-promotion/cp-polish-standard-20261024-01/verify/receipt.json) preserves the original data-root provenance and native boot lineage.

## Controlled future restart of the engineering example

Use the installed helpers on the owner's Mac. The copies in this bundle document the exact implementation; their install-path checks intentionally prevent executing them from the evidence directory.

Take a fresh checkpoint of the running owned service, stop only the session identified by that checkpoint, and preserve the actual Commander stop and terminal result objects. Use a new output filename and new session ID for each deliberate restart. Do not reuse an uncertain attempt or replay an application mutation.

~~~bash
CP_POLISH_ROOT='/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024'
CP_POLISH_NS="$CP_POLISH_ROOT/.runtime/commander-demo-polish"
CP_POLISH_BASE="$CP_POLISH_NS/release"
CP_POLISH_PY="$CP_POLISH_ROOT/.runtime/casepath-dev-v2/venv/bin/python"

env PYTHONDONTWRITEBYTECODE=1 "$CP_POLISH_PY" -I -B \
  "$CP_POLISH_BASE/verify_promoted_review_qa.py" checkpoint \
  --out "$CP_POLISH_BASE/<fresh-before>.json"
~~~

After the parent has observed that exact owned session's actual terminal state, launch under a new owned Commander session. Use exec so the service PID equals the Commander PID:

~~~bash
exec env PYTHONDONTWRITEBYTECODE=1 "$CP_POLISH_PY" -I -B \
  "$CP_POLISH_BASE/resume_promoted_review_qa.py" \
  --before "$CP_POLISH_BASE/<fresh-before>.json" \
  --stop-receipt "$CP_POLISH_BASE/<actual-stop>.json" \
  --terminal-receipt "$CP_POLISH_BASE/<actual-terminal>.json" \
  --session-id '<new-owned-session-id>'
~~~

Preserve the new actual running result, then verify once the service is ready:

~~~bash
env PYTHONDONTWRITEBYTECODE=1 "$CP_POLISH_PY" -I -B \
  "$CP_POLISH_BASE/verify_promoted_review_qa.py" verify \
  --before "$CP_POLISH_BASE/<fresh-before>.json" \
  --running-receipt "$CP_POLISH_BASE/<actual-running>.json" \
  --out "$CP_POLISH_BASE/<fresh-verification>.json"
~~~

These helpers preserve legitimate later QA edits. They do not copy, reset, seed, start or replay investigations. The original owner/copy evidence remains b206 ancestry; the running code uses the released immutable 4864 capsule.

## Standard workspace

The official launcher belongs to the original workspace at /Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024. It uses the existing separate standard data directory and native boot history. The completed source promotion was a fast-forward followed by official prepare; it was not a reset or data migration. Future starts use that workspace's official ./bin/casepath dev after its owned prior session has stopped and port 4173 is free. Preserve native boot history and DATA_ROOT_PROVENANCE.json. Do not rerun the one-time b206-to-4864 source-promotion attempt.

## Qualified review

Read [OPERATOR_REVIEW.md](../../northstar-review-20261024/OPERATOR_REVIEW.md) for the source identities and remaining substantive judgment. The question is whether this additional notice-comparison prerequisite, its scope and completion criterion are appropriate for reuse while preserving protective actions and deadlines. Qualified approval remains pending; no engineering receipt substitutes for it.
