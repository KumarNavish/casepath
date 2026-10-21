# Three CasePath design options

Prepared for the planner's [design-options request](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6312675839). These are standalone desktop prototypes at **1440 × 900**, awaiting the user's choice. The original palette, Instrument font and hairlines are retained. The planner's reference at `f4d3d9c` is option 0.

The interrupted product port is preserved, unverified and unsealed, on `codex/casepath-agent-desk-20261021` at `6491628`. This options branch starts from the approved W2.6 commit `8856ca7`; its changes are confined to this design-plan directory.

## Compare

| Option | Prototype | Mid-work | Case 1 result | Case 4 result |
|---|---|---|---|---|
| A · Evidence desk | [desk.html](A/desk.html) | [A-work.png](A/A-work.png) | [A-case1-result.png](A/A-case1-result.png) | [A-case4-result.png](A/A-case4-result.png) |
| B · Document and margin | [desk.html](B/desk.html) | [B-work.png](B/B-work.png) | [B-case1-result.png](B/B-case1-result.png) | [B-case4-result.png](B/B-case4-result.png) |
| C · Process timeline | [desk.html](C/desk.html) | [C-work.png](C/C-work.png) | [C-case1-result.png](C/C-case1-result.png) | [C-case4-result.png](C/C-case4-result.png) |

**A · Evidence desk**

Keep sources, reading and process together.
Each quote feeds a nearby process step; the result replaces the reading card.
Best when the reader wants steady orientation and short eye movements.

**B · Document and margin**

Make the source document the main workspace.
A compact file strip frees room for the text, with the live process in its margin.
Best when reading the evidence is the main task; the result gets the same generous page.

**C · Process timeline**

Show the whole process across the top.
The cited text opens below it, with a thread to the step it supports.
Best for understanding sequence and comparing the result with the completed path.

## Run locally

The existing isolated, seeded nine-case preview must be available at `127.0.0.1:4180`. From the repository root:

```sh
python3 design-plans/options-20261021/serve.py
```

Open **http://127.0.0.1:4181/** for the comparison gallery. This loopback server serves this directory and proxies only GET reads of preview assets and case records to 4180. It does not deploy or change the product.

Each `A/desk.html`, `B/desk.html` and `C/desk.html` embeds its own script and styles. They can also be served directly by a seeded preview, using its existing `/assets/` and `/api/` paths. The common source is `prototype.js`; regenerate the three files with `python3 design-plans/options-20261021/build_options.py`.

- Default: play recorded operations, hold the result, then advance through the nine-case roster.
- `?case=4&frame=result`: open the completed fourth case without playback.
- `?case=1&frame=work`: pause at the middle legal-test observation in the recorded presentation. The exact operation ID and prefix index are in `capture-receipt.json`; this is an actual prefix, not a simulated state.
- Pause, resume, skip to result, choose a case, inspect a file/step/legal-test citation, return to result, and open the recorded draft all work.
- Reduced motion opens the completed case immediately, with no animations or threads.

## Recorded-data semantics

Only the nine seeded synthetic cases and their deterministic operation streams are read. `mode=live` is this preview's GET-only deterministic reconstruction route; no model is invoked. The final operation result must match the saved state hash. Every displayed source highlight must match its exact recorded Unicode offsets and quote.

Files read counts distinct `(role, file_name)` groups with a recorded `span.read`. The customer message initially says **Request received**, and is not counted as read without that event. Facts counts `fact.extract` entries whose `verification_required` is not false, including repeated recorded observations; file subtotals use the same rule. Rule checks counts `condition.evaluate`, `node.evaluate`, `dependency.evaluate`, `process.inspect` and `document.require`. Completed steps counts distinct graph nodes with `step.complete` status `completed`.

Law references come from recorded legal facts. A legal predicate attaches to the document fact with the identical quote, otherwise to the terminal node. **Not met** is reserved for recorded `failed` predicates; unresolved predicates stay open. The result retains the exact recorded lead. A remaining summary sentence is labelled Still open only when it explicitly says unknown, unresolved or undetermined; full wording and authority limits remain under Why.

Draft letters are read-only recorded content. No send, local-save, hosted write, deployment, paid inference or original-nine execution is performed. These are design prototypes, not a production integrity or release gate.

## Verification

- Nine requested PNG frames: **zero visible box/text overlaps**, no horizontal overflow, and all result cards above the fixed footer. The overlap audit excludes closed disclosure content and clips scrolled source text to its actual visible region.
- **27 result-count checks**: all nine cases in A, B and C match independent counts from the preview's operation records. Browser checks reuse those freshly read records in memory to respect the preview's 12-read/minute operation limit.
- **Three interaction checks**: failed predicate opens its exact source quote; recorded draft opens; customer message opens; completed case survives reload.
- **Three reduced-motion checks**: final result immediately, zero animations, zero threads.
- Browser checks reject non-GET/HEAD requests; observed writes and page errors: **zero**.
- `motion-receipt.json` records pause/resume/skip checks and geometric quote-thread checks for each option.

Receipts: [capture](capture-receipt.json), [counts, interactions and reduced motion](verification-receipt.json), [motion](motion-receipt.json).

```sh
node design-plans/options-20261021/capture.mjs
node design-plans/options-20261021/verify.mjs
node design-plans/options-20261021/check_motion.mjs
```

The first rapid verification pass reached the preview's existing read limit. The final verifier reads each source once and uses that captured fixture for the three browser layouts; no limit was raised. An initial draft-label assertion was corrected to allow CSS uppercase text. No product files or source seals were changed for this delivery.

Next: the user chooses a direction. Further product porting remains on hold. Review handoff uses `design-plans/tools/wait_for_planner.sh` only.
