# Scrub report: what to remove or decide before anything is made public

For the repository's owner. **This file is itself internal: delete it before any release.** It names files and lines,
not the content of secrets; no credential value is reproduced. Prepared 2026-11-11.

## What was searched, and how

- **(A) The tested product:** `casepath-internal/` at commit `6a72159cdb35a01059d0549b1d437c0b3d5c20cb`
  (114 files).
- **(B) The paper branch:** the whole tracked tree of `claude/casepath-tmis-paper-20261109` at commit `40965582`
  (25,270 files, 1.71 GB). Ignored and untracked files are not part of (B); they are listed in section 7.
- Method: `git grep -I -P` per category on both trees (text files only), plus three extra passes: the contents of
  every tracked `.zip`, `.tar.gz` and `.gz` file, the text layer of every tracked PDF, and two of the paper's screen
  crops by eye. Images and videos were not read by machine (no text recognition); see item 13.
- Search terms per category:
  - **Insurer:** the insurer's name, its legal-protection subsidiary's name and the short form of the insurer's
    name as a whole word or with `.ch`, `.yaml`, `-` or `_` (the three terms given in the task), case-insensitive.
  - **People:** the owner's first and last name; a salutation followed by a surname (German and English); the
    co-authors' surnames; local user names in paths. No person's name was found in `expert_study/`. The product's
    docs name only the owner.
  - **E-mail:** any address. **Hosts and ids:** internal domains, workspace hosts, local home paths, workspace,
    tenant and subscription ids, ticket numbers.
  - **Insurer material:** the Knowledge seed folder, the seed's family id, "request letter", "process catalogue",
    "internal copy". **Real case content:** "real case/claim/file/dossier", claim and policy number labels, IBAN
    and Swiss social-security number patterns.
  - **Credentials:** common key and token shapes (provider keys, GitHub, cloud, workspace and chat-platform tokens,
    private keys, signed web tokens) and literal values assigned to names such as `api_key`, `secret`, `token`,
    `password`.
  - **Assistants and vendors:** the names of the coding assistant used in this repository, of the model vendors
    and of the model router, and model ids.
  - **Internal systems:** the data platform, its catalogue and gateway, the in-house workbench, the source host of
    the internal copy, the desktop gateway, "hackathon", "inside the insurer".

## 1. Counts

Hits are matching lines. (B) includes (A)'s files only where the paper branch has its own older copy of
`casepath-internal/`; that copy is not the tested product.

| Category | (A) product: hits / files | (B) paper branch: hits / files | Real problems after review |
|---|---:|---:|---|
| Insurer and subsidiary names | 71 / 21 | 3,391 / 610 | All: see items 1–9 |
| People (owner) | 18 / 7 | 537 / 255 (first name); local user name in paths: 3,417 / 523 | Owner's name in product docs and examples; local paths that name the employer |
| People (salutation + surname) | 4 / 3 | 1,108 / 803 (all patterns) | None: synthetic names in synthetic data |
| E-mail addresses | 15 / 8 | 79 / 48 | One paper author address (intended); the rest are example domains, LaTeX style authors or synthetic |
| Internal hosts, local paths | 9 / 5 | 203 / 98 | (A) only placeholder hosts. (B): 186 container paths, 3 local paths of the owner's computer, the subsidiary's public web page |
| Workspace, tenant, ticket ids | 0 / 0 | 49 / 33 | None found that is a real id (field names and test values) |
| Insurer-derived material | 19 / 9 | 35 / 27 | The Knowledge seed file and the text that refers to it; descriptions of the catalogue |
| Real case content | 29 / 12 | 9,645 / 182 | No real case content found. Hits are the words "real case" and synthetic claim numbers or IBANs (the standard example IBAN) |
| Credential patterns | 0 / 0 | 444 / 431 | **No real credential found.** 425 hits are substrings of encrypted model output in cached responses; 19 are test fixtures with fake values |
| Assistant and vendor names | 62 / 15 | 119,411 / 18,900 | (A): 5 assistant-name hits, all in one internal doc; the rest are connector names and API routes. (B): mostly model ids in stored runs (80,353) |
| Internal systems | 195 / 39 | 391 / 124 | Product deploy files and docs; research docs on the expert study |

## 2. Blockers and decisions (most serious first)

1. **Git history.** The local repository holds 1,110 commits on 12 branches. Making it public publishes all of
   them, including every earlier state of the files below and of data that was later pseudonymised
   (`data/casepath-tenancy-claims/release-records/PSEUDONYMIZATION.json`: the intake mailbox of a real insurer was
   replaced after the evaluation). Cleaning the current tree does not clean the history.
   **Recommendation:** do not change the visibility of this repository. Publish a new repository whose first commit
   is a reviewed export of the files to be released.
2. **The tested product names the insurer in its code.** Any edit to `casepath-internal/casepath/` changes the
   parity hash `030480203f…` that the paper reports, because the hash covers every file of the package
   (`casepath/parity.py:26`, json and js included). The places are listed in section 3, A1–A6.
   **Decision needed:**
   - (a) publish `6a72159c` unchanged, with the insurer's written approval; or
   - (b) publish a scrubbed commit, report its new hash beside the tested one in the paper, and state that the
     two differ only in names and the removed seed file; `reproduce.sh` would then check the new hash.
3. **Knowledge seed derived from the insurer's letters.**
   `casepath-internal/casepath/process/knowledge_seed/osm-mold.pilot.json`: practice rules "derived from" the
   subsidiary's first document-request letters in 7 hackathon cases, with counts from those letters. It names the
   owner and the activation date, and ships as package data (`pyproject.toml:28`). The interface text that cites it
   is `casepath/web/ui/assets/casepath.js:1003-1004`. The paper's author note in `paper/sections/app_g_repro.tex`
   flags it too.
   **Recommendation:** remove it (and `tests/test_knowledge_seed.py`, the loader line `process/knowledge.py:113`,
   and the interface text), or keep it only with the insurer's written approval.
4. **Internal product documents.** These describe the insurer's internal work and systems:
   - `docs/COORDINATION.md`: a session bridge to the internal remote desktop, the owner's local folder named after
     the employer, data classes and who may read them.
   - `docs/history/PLAN.md` and `docs/HANDLER_BAR.md` (scores on 7 real hackathon cases).
   - `docs/FEEDBACK_DESIGN.md` (the insurer's experts, sealed dossiers D2, D4, D7, a consent statement).
   - `docs/FORMATIVE_SESSION.md`.
   - `README.md` lines 11, 51–56 and 62 (the subsidiary's processes, the internal copy, the in-house pipeline files).

   **Recommendation:** remove the five documents. Replace the README lines by neutral text.
5. **Deployment files for the insurer's platform:** `deploy/databricks/` (`app.yaml`, `package.sh`, `smoke.py`),
   `deploy/workspace/` (`env.example` names the owner), `deploy/cloudshell/start.sh` and `docs/DEPLOYMENT.md`.
   They hold no secrets, only `FILL-IN` placeholders, but they describe the internal stack.
   **Recommendation:** keep with the owner's approval, or remove, with the README's "Ship" section.
6. **`design-plans/` on the paper branch.** 3,174 of the 3,391 insurer hits, in 484 files. Most are local paths of the
   owner's computer whose folder is named after the employer, in evidence manifests and receipts. It also holds
   26 videos (295 MB) and 9 screen recordings (56 MB).
   **Recommendation:** leave the whole folder out of the public repository.
7. **The paper branch's own `casepath-internal/`** (package `casepath_internal`, last changed at `aa4fb25`). It has
   the same kinds of hits as the product and is not the tested product, so it confuses readers.
   **Recommendation:** leave it out; publish the tested commit's `casepath-internal/` instead.
8. **Local paths and names in top-level and research documents:**
   - `CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md:4058`, `HANDOFF.md`, `docs/HYBRID_DEVELOPMENT.md`, `docs/PRO_HANDOFF.md`,
     `docs/setup.md`;
   - `casepath-api/tests/test_arena_v1.py:10`;
   - `research/casepath/obligation-control/IMPLEMENTATION.md:5,128` and `COMPARISON.proposed.json:19`;
   - `research/casepath/package_submission.py:18`: a pattern list that spells out the owner's identities.

   **Recommendation:** replace the paths by neutral ones. Leave out handoff documents that only serve internal work.
9. **Public policy terms of the subsidiary used as research sources:** `research/casepath/SOURCE_SUFFICIENCY.md`
   (lines 61, 628–641, 698–732, 1260–1426) and `research/casepath/reference_contracts/legal_expenses.json`
   (37 lines, including the subsidiary's public reporting page at line 289). The material is public, but it ties
   the research to this insurer by name.
   **Recommendation:** keep with the owner's approval, or rename the insurer to a neutral label as in the data sets.
10. **Licences.** No licence is stated for `fresh/`, `fresh2/`, `dev_probe/`, `rule_review/`, `runs/` (it holds model
    output), `expert_study/` and `paper/`. The authors' note in `paper/sections/app_g_repro.tex` asks for one.
    **Recommendation:** add a licence file to each before release.

## 3. (A) The product at `6a72159c`, line by line

Paths are under `casepath-internal/`.

### A1. Insurer and subsidiary names (71 hits in 21 files; files with counts, then the ten most serious)

| File | Hits | Recommendation |
|---|---:|---|
| `docs/COORDINATION.md` | 11 | remove the file |
| `docs/history/PLAN.md` | 10 | remove the file |
| `docs/FEEDBACK_DESIGN.md` | 6 | remove the file |
| `casepath/process/mining.py` | 5 | replace by a neutral default (organisation from `CASEPATH_ORGANISATION`; rename the schema field of line 63, which carries the subsidiary's name) |
| `casepath/quality/synthetic.py` | 5 | replace "inside <insurer>" by "inside the deployment" |
| `docs/HANDLER_BAR.md` | 5 | remove the file |
| `tests/test_voice.py` | 5 | follows the default chosen in `team.py` and `mining.py` |
| `README.md` | 4 | replace lines 11, 51, 56, 62 |
| `docs/FORMATIVE_SESSION.md` | 3 | remove the file |
| `tests/test_mining.py` | 3 | replace by a neutral organisation |
| `casepath/process/knowledge_seed/osm-mold.pilot.json` | 2 | remove (item 3) |
| `casepath/quality/scorecard.py` | 2 | replace by neutral wording |
| `casepath/web/ui/assets/casepath.js` | 2 | replace lines 1003–1004 (they cite the seed file) |
| `casepath/__main__.py` | 1 | replace the help text of `synthetic` (line 22) |
| `casepath/agents/team.py` | 1 | replace the default organisation (line 36) by a neutral one |
| `casepath/process/workflows.py` | 1 | replace line 7 ("invents no <insurer> procedure") |
| `deploy/preview/preview.py` | 1 | replace line 5 |
| `docs/DEPLOYMENT.md` | 1 | replace "default <subsidiary>" (line 38) |
| `tests/fixtures/example-defect.json` | 1 | replace by "not a real insurer's process" |
| `tests/oracle_walk.py` | 1 | as `workflows.py` |
| `tests/test_app.py` | 1 | replace line 178 |

The ten most serious:

1. `casepath/agents/team.py:36`: the agents' default organisation is the subsidiary. Every model prompt and reply
   draft names it unless `CASEPATH_ORGANISATION` is set.
2. `casepath/process/mining.py:27`: the same default for process mining, and line 63, a schema field named after
   the subsidiary.
3. `casepath/process/knowledge_seed/osm-mold.pilot.json:2,10`: derived from the subsidiary's letters (item 3).
4. `casepath/web/ui/assets/casepath.js:1003-1004`: the interface says a Knowledge item comes "from <subsidiary>'s
   first request letters".
5. `docs/COORDINATION.md:4-68`: internal access, the owner's employer folder, the remote desktop.
6. `docs/HANDLER_BAR.md:3-71`: goals for the subsidiary's employees and results on real hackathon cases.
7. `docs/FEEDBACK_DESIGN.md:70-133`: the subsidiary's experts and the insurer's consent.
8. `docs/history/PLAN.md:1-102`: the build plan "inside <insurer>".
9. `README.md:11,51,56,62`: the catalogue of the subsidiary's processes and the internal copy's pipeline files.
10. `casepath/quality/synthetic.py:1-23,496,518` and `casepath/quality/scorecard.py:1,108`: "inside <insurer>"
    in user-facing help text.

### A2. People

| Path:line | What it is | Recommendation |
|---|---|---|
| `casepath/process/knowledge_seed/osm-mold.pilot.json:2` | owner's full name (activation note) | remove with the file |
| `deploy/workspace/env.example:6` | owner's full name as an example | replace by "Jane Example" |
| `deploy/preview/preview.py:96,101,108,109,114,118` | owner's initial and surname as the preview user | replace by a neutral user |
| `docs/COORDINATION.md:4,13,15,22,53,66` | owner's first name, his computer, his approvals | remove the file |
| `docs/FEEDBACK_DESIGN.md:122` | owner's first name, a decision | remove the file |
| `docs/FORMATIVE_SESSION.md:14` | owner's first name | remove the file |
| `docs/history/PLAN.md:3,90` | owner's first name | remove the file |
| `casepath/quality/examples.py:27,29`, `tests/test_synthetic.py:15`, `tests/test_team.py:276` | synthetic names | keep |

### A3. E-mail addresses (15): keep

All are on `example.ch` or `example.org`:

- `casepath/quality/examples.py:22`;
- `tests/test_app.py:19,137,138,139`;
- `tests/test_chat_model.py:93`;
- `tests/test_drawio_evidence.py:85`;
- `tests/test_model_agent.py:78`;
- `tests/test_msg.py:25,32,48,83`;
- `tests/test_parity.py:47,50`;
- `tests/test_synthetic.py:16`.

### A4. Hosts (9): keep

`casepath/config.py:15` is a domain suffix used for validation. The others are placeholder hosts in tests:

- `tests/test_chat_model.py:9,100`;
- `tests/test_messages_team.py:69`;
- `tests/test_mirror.py:41,45,67`;
- `tests/test_model_agent.py:12,22`.

No workspace, tenant or ticket id was found.

### A5. Insurer-derived material (19)

| Path:line | What it is | Recommendation |
|---|---|---|
| `casepath/process/knowledge_seed/osm-mold.pilot.json:2,6,23,39` | the seed (item 3) | remove, or keep with approval |
| `pyproject.toml:28`, `casepath/process/knowledge.py:113`, `tests/test_knowledge_seed.py:25,30` | load and test the seed | remove with the seed |
| `casepath/web/ui/assets/casepath.js:1003` | interface text citing the letters | replace |
| `README.md:51,52,56` | the subsidiary's catalogue, benchmark and pipeline as the "internal copy" | replace by neutral text |
| `docs/HANDLER_BAR.md:10,31,71` | results on the hackathon cases with request letters | remove the file |
| `docs/PARITY.md:61,62,70` | says the internal copy carries the insurer's catalogue (no content) | keep: the paper relies on this document |
| `deploy/databricks/package.sh:8` | packages the internal copy | see item 5 |

### A6. Real case content (29 hits): none found

Every hit describes real cases without quoting them:

- `casepath/__main__.py:25`;
- `casepath/process/mining.py:1`;
- `casepath/quality/evaluate.py:31`, `examples.py:1`, `scorecard.py:1`;
- `casepath/quality/synthetic.py:3,5,6,14,73,120,134,520,528`;
- `casepath/read/reading.py:1`;
- `casepath/web/batch.py:1`;
- `casepath/web/ui/assets/casepath.js:984`;
- `docs/HANDLER_BAR.md:8,32,39,65,81,82`;
- `docs/PARITY.md:4`;
- `docs/history/PLAN.md:3,24,51,89,101`.

**Recommendation:** keep in code. The docs go with item 4.

### A7. Credentials: none

No key shapes and no literal secrets. `deploy/databricks/app.yaml` holds only `FILL-IN` placeholders.

### A8. Assistant and vendor names (62 hits in 15 files)

| File | Hits | What | Recommendation |
|---|---:|---|---|
| `tests/test_chat_model.py` | 10 | connector class and API routes | keep |
| `casepath/agents/azure_model.py` | 9 | the vendor's API routes | keep |
| `tests/test_model_agent.py` | 8 | test endpoints, model ids | keep |
| `casepath/config.py` | 7 | host suffixes, a model-id rule (line 122) | keep |
| `casepath/agents/` messages-API connector (the module named after its vendor) | 5 | connector for a vendor's API | keep |
| `docs/COORDINATION.md` | 5 | **the coding assistant's name** (lines 12, 13, 19, 36, 68) | remove the file |
| `deploy/workspace/env.example` | 3 | endpoint form, model family | keep or remove with item 5 |
| `docs/PARITY.md` | 3 | connector names | keep |
| `casepath/web/app.py` | 2 | connector import | keep |
| `deploy/databricks/app.yaml`, `smoke.py` | 4 | gateway routes | item 5 |
| `docs/DEPLOYMENT.md` | 2 | connector names | item 5 |
| `tests/test_messages_team.py` | 2 | connector | keep |
| `casepath/agents/chat_model.py` | 1 | protocol name | keep |
| `deploy/cloudshell/start.sh` | 1 | endpoint form | item 5 |

The ten most serious are the five lines of `docs/COORDINATION.md`. The rest are functional names.

### A9. Internal systems (195 hits in 39 files)

Most hits are the data platform's connector and settings in code and tests, which are functional. The serious ones:

- `docs/COORDINATION.md:13,65,66` (the remote desktop);
- `docs/DEPLOYMENT.md` (16: the platform, its catalogue volume and gateway);
- `deploy/databricks/app.yaml` (10);
- `README.md:47-56` ("Ship" section and the in-house pipeline files);
- `docs/history/PLAN.md` (6);
- `docs/HANDLER_BAR.md` (5).

**Recommendation:** decide with item 5. Keep the connector code.

## 4. (B) The paper branch: files with counts and the most serious hits

Counts are hits / files by area. Only areas with real problems are listed.

**Insurer and subsidiary names (3,391 / 610):**

- `design-plans/` 3,174 / 484 (item 6);
- `research/tmis2026/runs/product/cache/` 90 / 90: cached model replies that sign "<subsidiary>" because earlier
  development runs used the product's default organisation (item A1.1);
- `research/casepath/` 59 / 9 (37 in `reference_contracts/legal_expenses.json`, 14 in `SOURCE_SUFFICIENCY.md`);
- `casepath-internal/` (older copy) 46;
- `research/tmis2026/paper/figures/ui_used/` 9;
- `casepath/assets/` 4;
- `casepath-api/` 3;
- one each in `CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md`, `casepath-qa/phase1-agentic-browser.mjs`,
  `research/ctes/STATE_CHECKSUM_2026-09-14.md` and `research/tmis2026/WORKLOG.md`.

Not seen by the text search, in compressed files:

- `casepath-qa/fixtures/desk-v3.json.gz` (240 hits) and `presentation-v1.json.gz` (280);
- six `design-plans/documentary-20261025/guided-a1b59cf5/media-evidence/*.txt.gz` files (local paths);
- `research/casepath/iclr2027-integrated/dist/casepath_iclr2027_reproducibility.zip` (7).

The ten most serious in (B):

1. `design-plans/**/evidence-manifest.json`, `narration-receipt.json` and similar: the owner's local paths name
   the employer. Leave the folder out (item 6).
2. `casepath-internal/` (older copy): as A1. Leave it out (item 7).
3. `research/tmis2026/paper/figures/ui_used/MANIFEST.md:69,129`: the earlier screen captures under
   `ui_used/en2/`, `de/` and `source_round1/` show agent text and a reply draft signed with the subsidiary's name.
   The paper's figures use only `ui_used/s4/`. **Recommendation:** leave out the other `ui_used/` subfolders, or
   check every image by eye.
4. `casepath-api/prepare_runtime_v12.py:85`: a synthetic message addressed to an invented mailbox on the
   subsidiary's real domain. Replace by `example.test`.
5. `casepath-api/arena_v1_data/frozen/cases_dev.json:2140`: a synthetic customer asks whether "<insurer>" pays.
   Replace the name.
6. `research/casepath/SOURCE_SUFFICIENCY.md:61-1426`, `reference_contracts/legal_expenses.json`: item 9.
7. `CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md:4058`, `casepath-api/tests/test_arena_v1.py:10`,
   `research/casepath/obligation-control/IMPLEMENTATION.md:5,128`: local paths (item 8).
8. `research/tmis2026/runs/product/cache/*.json` (90 files): replies signed with the subsidiary's name. Keep only
   if the caches are released at all (section 7). They are development runs, not Study 3.
9. `casepath-qa/fixtures/desk-v3.json.gz`, `presentation-v1.json.gz`: 520 occurrences of the subsidiary's name.
   Regenerate with a neutral name.
10. `casepath/assets/autonomous-recorded-heating-v1.json`, `autonomous-saved-history-v1.json`, `app.js:61,311`:
    the subsidiary as the organisation in demo data. Replace by a neutral name.

**People.** The owner's first name appears in 537 lines in 255 files: GitHub URLs of the owner's account, docs and
QA scripts. The local user name in paths appears in 3,417 lines in 523 files, nearly all in `design-plans/`. The
synthetic salutation-plus-surname hits are not people.

The most serious:

- `README.md`, `HANDOFF.md`, `docs/HYBRID_DEVELOPMENT.md`, `docs/PRO_HANDOFF.md` and `docs/setup.md`: the owner's
  Mac and its paths. Keep the GitHub URLs; replace the paths.
- `research/casepath/package_submission.py:18`: an identity pattern list. Keep it private or remove it.
- `research/tmis2026/expert_study/MESSAGE_TO_PRODUCT_SESSION.md:17`: the owner's first name in an internal
  message. Remove the file.
- Intended and fine: `research/tmis2026/paper/main.tex:36,38` (author and address) and `references.bib:1645`
  (co-authors).

**E-mail (79 / 48).** Only `research/tmis2026/paper/main.tex:38` is a real person's address (the author's,
intended). The others:

- `mailbox.ch` addresses in synthetic data;
- property-manager domains invented by a model in three cached replies under `runs/product/cache/`;
- LaTeX style-file authors in `research/casepath/iclr2027*/` (third-party files);
- a test URL (`casepath-api/tests/test_hosted_storage_v1.py:127`).

**Recommendation:** keep, except the cached replies, which follow the decision on the caches.

**Internal hosts and paths (203 / 98).**

- 186 are container paths (`/home/user/...`) in harness code, run manifests and logs. Examples:
  `research/tmis2026/harness/v2/cp4_score.py:17`, `harness/product/compare.py:31`, `compare_theft.py:9-17`,
  `harness/parity_original.py:7`, `harness/v2/build_review_bundle.py:15`, `harness/product/run_product.py:45`.
  They name no organisation, but they make the scripts fail elsewhere. **Recommendation:** replace by paths
  relative to the repository where a released script uses them.
- 3 are local paths of the owner's computer (item 8).
- 2 are the subsidiary's public web page (item 9).
- `research/tmis2026/paper/figures/ui_used/*/source/launch*.sh` name a scratch folder of an agent session.
- No internal company host was found.

**Ids (49 / 33).** Field names (`workspace_id`, "tenant id") in `casepath/tools/`, `casepath/releases/` and run
manifests. No real workspace, subscription or ticket id. Keep.

**Insurer-derived material (35 / 27).**

- `research/tmis2026/expert_study/PREREGISTRATION_DRAFT.md` and `SYNTHETIC_CHECK.md`, and
  `research/tmis2026/paper/sections/app_g_repro.tex`, `s7_experts.tex`, `app_i_protocol.tex`: these describe the
  insurer's requests and catalogue without content, as the paper requires. Keep.
- `research/tmis2026/fresh/README.md`, `fresh/tenancy_fresh.py`, `fresh2/tenancy_fresh2.py`,
  `harness/v2/*`, `analysis/export_prompts.py`: the phrase "insurer's request" in prompts and docs. Keep.
- The older `casepath-internal/` copy: item 7.

**Real case content (9,645 / 182).** None found. 9,514 hits are synthetic claim-number labels in theft stories and
stored runs. Further hits:

- the standard example IBAN and other synthetic IBANs in synthetic attachments;
- "real claims" in the paper and research docs, describing, not quoting.

Also note that the synthetic attachments in `fresh/` and `fresh2/` (base64) name real Swiss property-management
companies (for example in `research/tmis2026/fresh/tenancy/data/claims/fcl_284cb44c9617cba6.json:39`). Keep, or
replace by invented names.

**Credentials (444 / 431).** No real credential:

- 425 hits: random substrings of encrypted model output in `research/tmis2026/runs/product/cache/*.json`;
- 19 hits: test fixtures with fake values in `casepath-api/tests/` (`test_agent_demo_launcher.py`,
  `test_app_v15.py`, `test_autonomous_model_v1.py`, `test_multi_agent_v15.py`),
  `casepath-qa/browser-focused-v20.mjs:10504` and `casepath/assets/agent-desk-v2.js:219` (an idempotency key);
- harness headers: `research/tmis2026/harness/llm.py:70` and `harness/product/run_product.py` send the placeholder
  `Bearer proxy-injected`;
- `paper/figures/ui_used/*/source/launch*.sh:10` set the token variable to the same placeholder.

Keep all. Note for the owner: the real key lived only in the session's proxy, never in the repository.

**Assistant and vendor names (119,411 / 18,900).**

- 114,301 hits in `research/tmis2026/runs/` (model ids in plan keys, ledgers and cached replies). Keep: they are
  the record.
- 2,570 hits name AI assistants. They are in `research/casepath/artifacts/` (1,369), `design-plans/` (983),
  `docs/` (31), `research/casepath/PAPER.md` (26) and, in `research/tmis2026/`:
  - `fresh2/README.md`, `fresh2/BLIND_CHECK.md`, `fresh2/MANIFEST.json`, `fresh2/seal.py`, `dev_probe/README.md`
    and `dev_probe/build.py`: they record which model wrote the data. Keep.
  - `paper/sections/app_g_repro.tex`: the venue requires the disclosure. Keep.
  - `WORKLOG.md` (6), `BRIEF_PRODUCT_SYNC_20261110D.md`,
    `deliverables/EVIDENCE_AND_REMAINING_REQUIREMENTS.md` and `harness/product/README.md`: branch names and
    session notes. Replace or leave out.
- All branch names in this repository start with the coding assistant's name.
  **Recommendation:** release from a neutral tag and branch, for example `tmis2026-release` and
  `casepath-6a72159c`.

**Research text on the insurer's internal systems (in `research/`):**

- `research/tmis2026/expert_study/PREREGISTRATION_DRAFT.md:38,57,300,372`, `CONTRIBUTION.md:7`,
  `EVENT_FIELDS.md:8` and `REVIEW_OF_FEEDBACK_DESIGN.md:15`: the internal hackathon dossiers, the insurer's gateway
  model and exports that stay inside. Keep, with the owner's approval: the paper reports the pre-registration.
- `research/tmis2026/BRIEF_PRODUCT_SYNC_20261110D.md:81,135`: the internal gateway, the deploy files.
  Leave the brief out.
- `research/tmis2026/WORKLOG.md:130-132`: inside and outside the insurer. Keep or leave out with the worklog.
- `research/tmis2026/paper/sections/s4_casepath.tex:80`, `s7_experts.tex:10` and `app_i_protocol.tex:31,96`: paper
  text, anonymous ("the insurer"). Keep.
- `research/casepath/obligation-control/*.md` and `research/ctes/*`: platform names. Review with item 8.

## 5. Large or binary files that should not ship

Total tracked size 1.71 GB. By type: PNG 1,237 files (528 MB), MP4 26 (295 MB), ZIP 5 (99 MB), WebM 9 (56 MB),
gzip 48 (25 MB), PDF 146 (17 MB), JPG 51 (14 MB), EML 165 (9 MB).

| File | Size | Recommendation |
|---|---:|---|
| `paper/CasePath-ICLR-2027-supplement.zip` | 52 MB | leave out (earlier submission; anonymity copy) |
| `research/casepath/iclr2027-integrated/dist/casepath_iclr2027_reproducibility.zip` | 42 MB | leave out; it holds 7 insurer-name hits |
| `design-plans/**/*.mp4`, `*.webm` (35 files) | 351 MB | leave out (item 6) |
| `research/tmis2026/runs/product/ledger_dev_gpt-6-luna.jsonl` | 22 MB | keep: Study 3 costs read it |
| `research/tmis2026/runs/study3/confirm/plans_theft_casepath.json` and other plans of 5–11 MB | 5–11 MB each | keep: they are the stored outputs |
| `research/casepath/artifacts/term_arms.json` | 14 MB | keep only if the earlier study is released |
| `paper/CasePath.pdf`, `paper/CasePath-ICLR-2027-source.zip` | 6 MB, small | leave out (earlier submission) |
| `research/tmis2026/deliverables/CasePath_TMIS.pdf`, `CasePath_TMIS_overleaf.zip` | 0.8 MB | rebuild from the final sources at release |
| `research/tmis2026/runs/product/cache/` (18,089 tracked files) | 148 MB | keep, or drop together with the ignored rest (section 7) |

## 6. Files the analysis and the paper need that are ignored by git

`reproduce.sh` passed in a fresh clone, so no ignored file is needed to reproduce the tables. These are ignored
but the paper says they are released, or a re-run needs them:

| Path | Ignored by | What it is | Effect |
|---|---|---|---|
| `research/tmis2026/runs/product/cache/` | `.gitignore: runs/product/cache/` | product response cache: 79,404 files locally, 18,089 tracked (force-added), 61,315 ignored. All 22,999 cache files that Study 3's stored plans reference are ignored. | `paper/sections/app_g_repro.tex` says the caches are released and that a re-run is answered from them. From a clone this is false. Add them (the whole folder is 0.9 GB), or correct the text. |
| `research/tmis2026/runs/cache/` | `.gitignore: runs/cache/` | the harness model cache: 16,067 files locally; `runs/responses_cache.tar.gz` holds 3,068 | enough for Study 1's re-analysis; the Study 2 and Study 3 baseline responses beyond it are not released |
| `research/tmis2026/paper/figures/ui/` except `ui/s4/source/` and three `ui/s4/*.json` files | `.gitignore: paper/figures/ui/` | full screen captures (94 MB) | not needed: the figures use the tracked `ui_used/` crops |
| `research/tmis2026/paper/*.aux`, `*.log`, `*.bbl`, `*.blg`, `*.out`, `comment.cut` | `.gitignore` | LaTeX build files | not needed |

The tests show the same: `analysis/test_study3.py`'s development test reads
`runs/product/plans_tenancy_gpt-6-luna_fresh_r3b-full.json`, which is tracked. No other analysis input is ignored.

## 7. Checklist for the owner

1. Decide (a) or (b) for the product commit (item 2), and get the insurer's approval in writing if (a).
2. Remove or approve the Knowledge seed (item 3).
3. Remove the five internal product documents and fix the README (item 4).
4. Decide on the deployment files (item 5).
5. Build the public repository from an export: without `design-plans/`, without the paper branch's own
   `casepath-internal/`, without earlier submissions' archives, with neutral branch and tag names (items 1, 6, 7;
   section 5).
6. Replace local paths and container paths in the files that ship (item 8; section 4, hosts).
7. Decide on the response caches: add them or correct `paper/sections/app_g_repro.tex` (section 6).
8. Add licences for the data sets and outputs without one (item 10).
9. Check the remaining screen captures by eye (section 4, insurer names, 3).
10. Delete this report from the export.
