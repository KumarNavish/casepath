# CasePath presenter guide

Tested and deployed source: b20685d1670b33b941b1bfcb902638a879c01b93

## Open the completed example

Use a 1440 × 900 browser window for the reference layout.

1. Open [the earlier case](http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_f69b1747447bc221) on the owner's Mac. This is an isolated engineering demo with recorded Test handler actions. Select Process builder to inspect the added Compare both complete notices step and its connection. Use the source rail to inspect the original tenant and spouse PDFs.
2. Open [the receiving case](http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_0e538990cc6ba7ef). Select Result checker. The graph and own source reader stay present.
3. Show the two original receiving-case date passages: 30. Juni and 31. Juli. Click either source fact to open that case's exact source.
4. Show Exact saved version 1, its source-case link and version provenance. The source library also contains version 2; this receiving case still pins version 1.
5. Show the current effect: Prepare challenge, extension or settlement now also requires Compare both complete notices. Resolution remains blocked. The earlier evidence connection is retained, and Preserve challenge or extension deadline remains next.
6. Open When applied to inspect the actual historical before/after comparison. Separate that recorded change from the current evaluation shown above it.
7. Reload the receiving case. Result and the version pin are retained in that browser. For a fresh browser, choose Result checker again.

The [video](review-walkthrough.webm) records the actual edit, preview, accept, save and reuse interactions. It is evidence from the isolated deterministic run. Its Test handler events are engineering QA and do not authorize a real claim outcome.

## Public demonstration

Open the presentation before screen sharing and wait for its introduction/start control. The free host may need time to wake, and the recorded cold opening can briefly show a different loading case. The actual six-act presentation lasts 88.05 seconds. Pause on dense evidence or law text as needed; the film is a recorded fictional example, and the local review workspace is the editable demonstration.

[Open the public presentation](https://casepath-autonomous.kumarnavish.chatgpt.site/?present=1#autonomous/demonstration). Start it once and let all six acts finish. The public site reviews recorded fictional cases and remains read-only. Its draft editor saves a local browser copy and does not send a message.

## Normal review workspace

The normal local workspace is available at http://127.0.0.1:4173/?journey=review&view=northstar. It uses its existing separate data directory. The completed engineering example uses port 4194 and an independently copied QA data directory. Its startup does not seed, start or replay investigations; opening it does not start a batch.

Edits made in the engineering example create real new events only in that isolated copy. The original sealed QA data and the public saved histories remain separate. Keep the original evidence receipt when rehearsing; do not relabel Test handler as a qualified human reviewer.

## Qualified review

Open [OPERATOR_REVIEW.md](../OPERATOR_REVIEW.md) for the exact original file identities, dates, proposed completion criterion and the decision that remains with a qualified reviewer. The concrete question is whether this prerequisite should be accepted for reuse and under what scope, without obstructing protective actions. The UI's process review is distinct from approval of a claim outcome.

## Recovery

The local servers run in owned Commander sessions on the owner's Mac. [The current server receipt](local-demo-current-server.json) identifies the restarted process, boot ID and Commander session. [The initial owner receipt](local-demo-owner.json) remains historical. [The actual stop/start rehearsal](local-demo-restart-verified.json) preserves both claim views, the claim journal and the work journal.

If the completed example is already running, use its existing URL. Once its recorded owned process has fully stopped, the following command reopens the same QA store without copying, resetting, seeding or replaying work. It refuses a concurrent owner and verifies the sealed source and original QA ancestry.

```bash
/usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1 CASEPATH_MODEL_MODE=deterministic_reference CASEPATH_AGENT_WORK_EXTERNAL_FACTS=0 CASEPATH_DEMO_SESSION=manual-terminal \
  '/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024/.runtime/casepath-dev-v2/venv/bin/python' -I -B -P \
  '/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024/.runtime/commander-northstar/release/resume_existing_review_qa.py'
```

Keep that terminal open while using the demo. A future legitimate QA edit is preserved across restart; this command does not restore the original screenshot state. Do not rerun a mutation or overwrite a journal to repair an uncertain result. The normal workspace and completed example use separate stores; restarting one is not a reset of the other.

For a meeting, first open the two local links and the public presentation. The completed read soak and browser receipts describe the tested release; they are not a promise of future network availability.
