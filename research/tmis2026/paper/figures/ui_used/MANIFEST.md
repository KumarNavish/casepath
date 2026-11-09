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
