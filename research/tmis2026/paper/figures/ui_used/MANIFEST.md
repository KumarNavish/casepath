# CasePath UI captures for the TMIS paper

These are real screens of the `casepath-internal` workspace, rendered locally in a cloud container on 2026-11-09 between 22:29 and 22:38 UTC. Every case, name and address in them is invented. The workflow is a rendering fixture written for this capture. It is not Mobiliar's process. Nothing here is committed.

## Provenance

- **Code.** `KumarNavish/casepath`, branch `claude/casepath-internal-20261027`, commit `457b9ddb20399392b1f2917fb3b50ee655384a16`. It was checked out unmodified as a worktree at `/home/user/work/casepath-ui`; no product source was edited.
- **Launch.** `source/launch.sh` runs `python -m casepath_internal serve --host 127.0.0.1 --port 8765` with these settings:
  - sign-in through the development user `Sachbearbeitung (Demo)`;
  - `CASEPATH_WORKFLOW_CATALOGUE` set to a folder holding only `source/mould-defect.json`;
  - the model is reached through the app's own chat-completions connector (`CASEPATH_MODEL_PROVIDER=databricks`, `CASEPATH_MODEL_ENDPOINT=https://openrouter.ai`, `CASEPATH_CHAT_PATH=/api/v1/chat/completions`, `CASEPATH_MODEL_GATEWAY_HOSTS=openrouter.ai`, `CASEPATH_MODEL=gpt-6-luna`). The container proxy supplies the credential.
- **Model.** `openai/gpt-6-luna` via OpenRouter. These are real agent runs, not scripted.
- **Cases.** Both were seeded with `source/seed.py` and `source/seed2.py`, using the app's own PDF renderer.
  - Case 1 is `case_2d5b1824c6814df1`, "Synthetischer Fall: Schimmel im Bad und im Kinderzimmer". The landlord was told by phone only, the child is coughing, and there is no medical report. It ran as `run_43edc9074ef5490b` and completed in 2 min 3 s.
  - Case 2 is `case_30e0064700cd481e`, "… Aussenwand im Schlafzimmer". It has a written notice and a ventilation log without humidity readings. It ran as `run_4a3e3ad61420477c`.
- **Handler correction (case 1).** Through the documented API (`POST /api/cases/{id}/edits`), I added the document need "Lüftungs- und Heizprotokoll" with `use_for_similar=true`. That started the document-only recheck `run_468393ed064843a9`. I then approved the resulting Knowledge item through `POST /api/knowledge/{id}/activate`.
- **Tokens.**

  | Run | Input | Output |
  |---|---|---|
  | Case 1 | 73,904 (47,179 cached) | 11,483 |
  | Recheck | 6,536 | 307 |
  | Case 2 | 96,218 | 13,477 |

  The total cost is about USD 0.03 at list price ($0.10 per million input tokens, $0.50 per million output tokens).
- **Capture.** Playwright Chromium with a 1440×900 viewport (`-tall`: 1440×1600) and deviceScaleFactor 2, so the PNGs are 2880×1800 or 2880×3200. There is no browser chrome. The URL is `/?lang=en` or `/?lang=de`; German is the product default.
- **File variants.** `-cropN` is a single panel cut out by its DOM element. `de/` holds the same states in German, captured after the correction (`de-` prefix).

## Files (en/; de/ mirrors them)

- **Case list:** `a-cases` (2 cases, 1 process). `h-cases` is the list after case 2.
- **Claim reader (Fallleser), case 1:** `b-claim-reader`.
  - Process spine of the questions, with answered ones ticked.
  - Source PDF with the quoted sentences highlighted.
  - Brief listing the request, parties and timeline.
  - Crops: `crop1` is the spine, `crop2` the document, `crop3` the brief.
- **Source checker (Quellenprüfer):** `c-source-checker`. Each fact and document carries a "supported" or "not checked" verdict, the exact quotes with file and page, and ✓/✗ buttons for the person.
- **Process builder (Prozessbauer):** `d-process-builder`.
  - Six-step path; step 6 is the open node.
  - Cards for Source facts, Basis, Current evidence (3), Evidence still needed (Arztbericht) and From earlier cases (none).
  - `crop1` is the graph alone.
- **Document finder (Dokumentenfinder):** `e-document-finder` is the checklist table: present ×3 and missing ×1, each with why, proof quote and origin. `e2-document-finder-after-correction` adds the handler's "Lüftungs- und Heizprotokoll" as missing, origin "Added for this case".
- **Result checker (Ergebnisprüfer):** `f-result-checker`. It shows where the case stands, the checklist (3 present, 1 still needed), the next step (obtain the Arztbericht), open points with ✓/✗, two learning proposals, a short assessment, and a reply draft whose clauses say what each rests on or asks for.
- **Knowledge (Wissen):**
  - `g-knowledge`: two candidate questions from the result checker.
  - `g1-knowledge-after-correction`: adds the candidate from the case worker's change.
  - `n-knowledge-refinement`: the item is active v1, used once in case 2 and found "unusable" there. Next to it is a candidate "refines v1 → v2" proposed from case 2, with a quote and an "Apply refinement" button.
- **Case 2:**
  - `i`–`m` repeat the five tabs.
  - `l-case2-document-finder` shows the ventilation log "unusable", origin "From Knowledge", with its quote, plus suggested needs.
  - The footer reads "This case used Knowledge from earlier cases. Qualified review is still required."
- **live/:** frames taken mid-run.
  - `run1-claim-reader-live-quotes-and-strip` is the best single frame. It shows the spine with untaken branches struck through ("notified in writing", "no health effects"), quotes highlighted in yellow and red, the agent pointer, the task list, the growing checklist with the Arztbericht, and the provenance strip "schadenmeldung.pdf, page 1 + question".
  - The other live frames show the process builder, document finder and result checker at work.

## Known defects and content limits visible in the captures

- **Auto-follow still jumps** while a run is going. Live frames requested for one tab show the active agent's tab instead. There is no jumping after a run completes, so all frames in `en/` and `de/` are stable.
- **Raw tool names do not show.** The process builder's work log reads "adds a question for this case", not "add_question".
- **No "Nichts fehlt" contradiction.** The process cards and the checklist agree (1 missing).
- **Smaller wrinkles:**
  - The source checker lists "Written notice (Mängelrüge) (missing) · not checked" although the branch made it not required.
  - "End of the process: Defect assessed" appears while the Arztbericht is still needed.
  - In case 2 the item shows "confirmed 1" yet the document is "unusable".
- **Model quality (gpt-6-luna):**
  - The brief's "request" line is generic ("Brief mit Parteien … erstellt").
  - The customer-report proof is the weak quote "Was muss ich jetzt tun?".
  - One added question ("In welchem Jahr …") is typed yes/no.
  - Case 2's agent text names the insurer brand "Protekta" ("Was soll Protekta für Sie konkret tun?"), which comes from the agents' system prompt.
- **Simplified process graph.** It shows the evaluated path only, not the untaken branches; only the spine strip on the agent tabs shows those.
- **Tall captures.** Some `-tall` frames start slightly scrolled. Use the 900-px frame for the page heading.

---

# Round 2: English cases (`en2/`), rendered 2026-11-09 22:49–23:02 UTC

## Setup

- **Code.** `claude/casepath-internal-20261027` at commit `0a0573b8a5806362df684c2c7db00cc8e60adb85`, the head at render time. It was checked out unmodified as a worktree at `/home/user/work/casepath-ui2`; no product source was edited.
- **Launch.** `en2/source/launch-A.sh` and `launch-B.sh`, port 8765, development user "Case handler (demo)". The model is `openai/gpt-6-luna` via OpenRouter through the app's chat connector, as in round 1. The UI uses `?lang=en`.
- **Capture.** Playwright, 1440×900 at 2×, plus `-tall` frames (1440×1600) and `-crop` panels.
- **Cases.** Written by `en2/source/seed_en.py`. The case files are in English, with invented names and the app's own PDF renderer. The case-1 family differs in one sentence only:
  - **yes:** "Our daughter has been coughing for weeks; the paediatrician suspects a link with the mould. I do not have a medical report yet."
  - **open:** "Our daughter has been coughing for a few weeks; we do not know whether it has anything to do with the mould and have not seen a doctor."
  - **no:** "Nobody in our household has any health complaints."
- **Two fixtures, differing only in the health question.**
  - **Fixture A** (`source/mould-defect-A.json`): "Does the tenant report effects of the mould on anyone's health?"
  - **Fixture B** (`source/mould-defect-B.json`): "Has the mould affected anyone's health?"

## Runs

| Prefix | Fixture | Case id | Run id | Input tok (cached) | Output tok | USD |
|---|---|---|---|---|---|---|
| A-yes- | A | case_9e4ea47846254a08 | run_436a1b6286fa4a67 | 84,262 (56,401) | 13,522 | 0.0152 |
| A-open- | A | case_c5fb01b6679f40d5 | run_a5e2293bb09f4ab8 | 76,399 (45,578) | 12,649 | 0.0140 |
| A-no- | A | case_1b671f40d10840ec | run_5f41040c55274974 | 59,701 (31,745) | 8,673 | 0.0103 |
| k1-after-correction- (recheck on A-yes) | A | case_9e4ea47846254a08 | run_5f8bd70af5264abc | 6,232 | 269 | 0.0008 |
| case2- | A | case_63429e90ecd64623 | run_256bec481cbb452b | 101,639 (55,936) | 13,792 | 0.0171 |
| B-open- | B | case_8b5c6d2f21764431 | run_35224ecb1d874389 | 87,658 (41,994) | 10,981 | 0.0143 |
| B-yes- | B | case_7e6b551778f94f2c | run_aee4694cab284344 | 69,406 (28,806) | 11,314 | 0.0126 |

Round 2 cost about USD 0.084 at list price, with no cache discount applied; rounds 1 and 2 together cost about USD 0.11. Each case has frames numbered 1 claim reader, 2 source checker, 3 process builder, 4 document finder, 5 result checker, and 6 Knowledge where relevant.

## What the app did (as captured, nothing staged)

- **A-open: the app decided "yes".**
  - The claim reader established `health_effects = true` from the sentence "…we do not know whether it has anything to do with the mould…".
  - The source checker accepted it: "uncertainty about whether it is related to the mould does not negate the reported health effect."
  - So the path runs through "Obtain a medical report", and the Medical report shows as missing. A-open therefore looks like A-yes.
- **A-no:** `health_effects = false`. The path skips the medical step, and the checklist has 3 present, 0 missing.
- **B-open: the process stops at the open fact.**
  - The fact is recorded as unknown.
  - Process builder: step 4 "Check for health effects" is the open node, with both branch buttons ("health affected" / "no health effects"). Steps 5 and 6 are drawn dashed, as not reached.
  - Result checker: "Current step: Check for health effects · waiting for: Has the mould affected anyone's health?", with the next step "Answer: …".
  - **The medical report is not marked "depends".** It is simply absent from the checklist ("2 present, 0 still needed", "Evidence still needed: Nothing missing"). The photos are absent too, because their step is beyond the stop.
- **B-yes: also unknown.** Under fixture B, "the paediatrician suspects a link" was not accepted as established, so the B-yes screens look like B-open.
- **Three worlds as real screens:** use A-yes, A-no and B-open, and note in the caption that B uses the stricter health question.
- **Knowledge sequence:**
  1. `k1-after-correction-*`: the handler adds "Ventilation and heating log" to A-yes via `POST /api/cases/{id}/edits` with `use_for_similar=true`, which creates candidate `know_96be9d982e3948ea`. The recheck run marks the log missing ("Added for this case").
  2. The item is activated via `POST /api/knowledge/{id}/activate`. `k2-knowledge-active-card1.png` is a clean crop of the active v1 card; `k2-knowledge-active.png` / `-tall.png` show the full page.
  3. `case2-*`: the item is applied ("From Knowledge"). **This time the supplied log was judged "present", not "unusable"**; round 1 in German had judged it unusable. The result checker still proposed refinement `know_cecc6d3281d14858`, "refines v1 → v2: Distinguish ventilation/heating records from humidity measurements", citing "Humidity readings are missing…".
  4. `k3-knowledge-refinement-card1/2.png` crops the active item and the proposed refinement. `case2-6-knowledge` and `k3-knowledge-refinement(-tall).png` show the full page.

## Visible defects and weak model output (en2)

- **Language: agent-written text is mostly German despite English files and the English interface.** This affects the process builder's questions and source-facts labels, most open points, the short assessment, the reply draft, Knowledge proposals and some timelines. Quotations, the brief and many timeline rows are English, and case2's answer is English.
  - Cause: the agents' prompt says to write "in the language of the case files, usually German", and luna leans German.
  - There is no setting to change this without editing the product.
- **Brand name:** the reply draft signs "Freundliche Grüsse Protekta".
- **Wrong document-row language:** in case2, items added for the case and suggested by Knowledge are German ("Beleg über die Aufgabe …").
- **Source facts card:** under fixture B it does not show the unknown health fact. The waiting question appears only in the result checker's status box and the graph.
- **Process-builder additions:** "In welchem Jahr…" style questions again; A-yes asks for the year.
- **Labelling:** "suggested by Knowledge" appears on rows whose origin reads "Added for this case".
- **Layout:** the "Documents · N missing" side card stretches to the height of the source-facts column.
