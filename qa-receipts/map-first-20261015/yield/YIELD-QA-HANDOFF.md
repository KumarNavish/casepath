Bounded yield QA complete. No browser/profile processes remain; quiet window released. No tracked QA or product edits by this agent.

Frozen source: `2908c2dedeb82bc45a969d65e3c956b57c8c21fe`, root combined `1b493f3`. Served JS SHA `2a5e229f4a316bb68392c124b76cf89caafe263c47724d79f9991f9b7845fa30`; CSS unchanged `404b05220ed333e14ba9af9ce3f8033d58973fba8fedadf9a058d8fcc75f0e87`. Assets were extracted with git show and actual served body hashes checked. Root/writer separately reports 214 focused module checks; this agent did not run that module group.

One changed-source 4× cold native Chromium profile was run after explicit quiet GO, using the unchanged existing runner. `profile-command.json` records exact argv/environment/runner and asset hashes. `map-first-yield-4x-cold.json`, `.cpuprofile`, `map-first-yield-4x.log`, and `map-first-yield-receipt.json` retain the raw results. Terminal 0, no page errors. Same 824 operations, 21 checkpoints, native result revision 48/state `ceb64b6282749e60cbefd76263261f3d40fe99e5bfdc549cc96d3b81eaedd88d`, operation chain and trace as the pre-yield run and original 7904 baseline.

Compared with the pre-yield final candidate:

- Maximum long task: 1583→261ms. New overall maximum occurs before the first visible operation.
- Observed last document check→decision interval: old one 1583ms task; new seven tasks of 123, 123, 142, 100, 129, 115, and 78ms. Their total is 810ms; maximum 142ms.
- Total long-task time: 4270→3465ms. Count: 21→36.
- Wall: 26.447→26.846s. Frame p95: 16.8ms unchanged. Frame p99: 66.7→133.3ms.

`profile-comparison.json` binds all three workloads and preserves phase/task timestamps. Operation mutation timestamps identify broad intervals; exact animation callback timestamps and Profiler/navigation offsets were not captured. This demonstrates a smaller worst pause while preserving the native output. It does not establish improvement at every frame percentile or universal smoothness.

The bounded actual native browser group also passed: 10/10, zero failures/skips, 35.114s, terminal 0. `controls-command.json` records exact argv/environment and unchanged runner hash; `controls.log` is raw output; `controls/` contains eight JSON receipts and four running PNGs. Coverage:

- 1280×800, 1428×771, 1360×900, 390×844: exact native source inspection, pause retained after closing, Resume, Skip under three seconds, exact native result/graph/CO links, and all 824 original operations retained in History.
- Reduced motion at entry and during real reading: exact checked result with no stale actors or hidden pending landings, all 824 operations retained.
- Valid late old operations response after navigating to another recorded claim: new paused claim, operation, revision, and state stay unchanged; Resume/Skip reaches the new exact head.
- Default transport: first operations request remains live GET; exact final native result.

Only the authorized one changed 4× profile and this focused group were run. All requests were loopback GET/HEAD; no production/provider requests or writes. No source or geometry reruns. Earlier negative profile/oracle/product attempts remain unchanged under `/workspace/casepath-map-first-qa-evidence-20261015`; copy this directory as a separate follow-up evidence bundle. Asset duplicates may be omitted only if the exact hashes already exist in the evidence branch. No additional work or writes are pending.
