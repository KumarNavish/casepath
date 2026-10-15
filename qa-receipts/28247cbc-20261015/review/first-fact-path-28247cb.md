# Shipped heating packet: first fact path

Read-only static inspection of exact28247cbc87785b366fa542bb0aa0bd5f37e6c2e3, unchanged JS364bc44c4a10a8a57afcaad28b765f476ba31ee2478d190b552fe9f7c74c74bb and published packet1995cf8675257d674f7117fb9f53320020b4ad8be90b615f4fdb54b2c0fab383. No browser, timing benchmark, API request, engine run or source edit. Values below describe actual ordered bytes and source control flow, not measured execution cost.

The first fact is wire frame21, operation sequence12. Only it requests visible attention; preceding operations1–11 all return false from operationAttention. Its native citation is339 Unicode characters; stageFactSpan selects exact compact quote CHF1800,7 characters. operationReadDuration returns700ms. No earlier source acquisition, scan, phrase match or reducer operation adds a presentation pause.

| Wire frame | Content | Wire bytes including newline |
|---|---|---:|
|1|binding, from_seq28|848|
|2–7|ops1–6:process.inspect, condition.evaluate, node.evaluate, three document.require|2527,1081,1335,1310,1310,1310|
|8–15|checkpoints28–35, in order|285792,11897,24458,26998,28511,12574,122568,12921|
|16|op7 source.open|1903|
|17|op8 span.read|1961|
|18|op9 phrase.match|1268|
|19|op10 span.read|1972|
|20|op11 phrase.match|1481|
|21|op12 fact.extract|1507|

Total through first fact545532 bytes. Reconstructed canonical checkpoint state sizes, including state_sha256:272378,272553,274415,276616,278473,278635,315818,315992 bytes, total2284880. Actual canonical hash materials omit the hash property:2284224 bytes total. First checkpoint is full state; subsequent seven are exact deltas. Full saved-head state is564545 canonical bytes; decoded opening/head bodies are7847/1511895 bytes. These state/event/source checks remain mandatory and ordered; no prefix or operation may be skipped or relabeled.

Before playback, packet decode checks exact raw-body hashes. readReplay checks zero; checkedAtomicOperationHead checks pinned full state, complete journal, original binding/descriptors, checkedSavedSnapshot source/citation integrity and reference start. Planned process/start/binding checks finish before selection. The chosen opening carries referenceReady, so startOperations does not repeat the full head admission. It does read the opening again and reconcile release context. Cheap repeated reference/journal comparisons exist, but there is no second full-head hash after playing that can explain a delay after the first fact is already current.

During prefix consumption each non-result frame receives its canonical trace hash. checkedOperation verifies operation/input/result hashes, causes, chain, source text and Unicode span; checkpoint validation reconstructs exact deltas, hashes state, compares the pinned event, checks chain and calls readReplay. operationFrameYield yields only between verified frames. After fact12 becomes current, consumer validation waits on its presentation gate; no later checkpoint is required for that first landing.

Presentation path: render positions the exact source; afterSourceScroll waits for scrollend or90ms quiet at the target, with a1200ms instant-settle fallback. Then the visible WAAPI sweep runs700ms, and its onfinish begins a600ms curved transfer. The flight's onfinish marks the dock landed. The300ms source-operation pause follows completion and affects the next operation. There is no explicit extra1–2s read delay. The sweep completion depends on WAAPI/rendering progress, not an equivalent JS timer.

resized() calls positionOperationAttention(), whose normal entry cancels the old read and creates a new choreography. This is a real cancellation/restart path; geometry or font changes can use it. It does not establish why a replacement WAAPI animation has null startTime/currentTime0 while JS timers continue. bufferedOperations drains and canonicalizes the complete stream ahead of paced consumption, but source inspection alone cannot attribute elapsed time to that work. Coordination's newer long-task/timer/rAF observations do not support CPU starvation as the demonstrated cause.

Recommendation: no product change is supported by this evidence. Keep current validation/order/visible-flight requirements. Distinguish a source-triggered cancellation from the independently observed animation-frame suppression, and establish foreground/occlusion/render-timeline behavior before selecting a fix. A timeout that declares a fact landed without a completed visible flight would invalidate the acceptance evidence. No native timing or packet head is substituted for this published capture.
