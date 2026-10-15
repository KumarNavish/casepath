# Routed fixture storage isolation review

No blocking finding at bfc624ab148ccbdb1b279c39ba71df326ab2fb6d. Only the QA routingFixture helper changes:3 added lines/1 removed line. Product JS remains SHA256364bc44c4a10a8a57afcaad28b765f476ba31ee2478d190b552fe9f7c74c74bb; module SHA256e50c5be19eb1ae8228158af944ae04175a5bb4dd9fa50360d1c417b8cdb9d283. Working tree was clean.

Exact source cause: routed tests share the same API identity but previously inherited ambient sessionStorage. An earlier Knowledge read can persist a valid checked Knowledge representation. restoreReadCache restores it in a later test; loadClaims directly invokes warmKnowledge, whose existing cache guard correctly suppresses another GET. setImmediate versus setTimeout ordering is not the cause of this zero request count.

The helper now owns a fresh in-memory sessionStorage per routing fixture, retains it across that test's navigation/remounts, and restores the original property descriptor or removes the added property at teardown. It does not disable product caching or clear ambient storage. The exact zero-before/one-after assertions, waits, thresholds and product code are unchanged.

Reviewed writer evidence: unchanged699119e under Node24.19.0 with --experimental-webstorage reproduces223/224 with the same sole Knowledge0!==1 failure and requestIdleCallback undefined. Fixed same-flag224/224 and default224/224 pass, zero failures/skips. Logs in /workspace/casepath-recorded-packet-prototype-evidence-20261015: module-ambient-session-storage-699-negative.log, module-isolated-session-storage-final.log and module-isolated-storage-default-final.log. QA-STORAGE-ISOLATION-FINAL.json binds commands and hashes.

This is a Cloud Node24 WebStorage capability reproduction, not an execution of Mac Node26.8.2 or its combined230-test command. Mac's229/230 report remains a separate attestation. No reviewer test, browser, profile, network or product edit was performed. Earlier review artifacts remain byte-unchanged.
