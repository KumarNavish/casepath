# CasePath tenancy claims (Study B)

150 synthetic tenancy claims, each paired with a structured reference answer, for
training, prototyping and evaluating agents that handle claims. This is the
dataset of Study B in the paper *CasePath: An Agentic, Process-First Architecture
for Determining Evidence Requirements*.

Data: CC BY 4.0 (`LICENSE-DATA`). Code: Apache 2.0 (`LICENSE-CODE`).

## What a claim contains

An agent sees two files per claim.

- **Intake packet** (`benchmark/data/{dev,test}/claims/<id>.json`): what a claims
  inbox receives. The submission's channel (email, portal, chat or phone note),
  date and language (English or Swiss Standard German), the customer message as
  sent, and any attachments (termination notices, payment demands, rent forms,
  photos), embedded so that each file stands alone. The raw files are also in
  `benchmark/data/{dev,test}/sources/<id>/`.
- **Source registry** (`benchmark/data/{dev,test}/source-registry/<id>.json`): the
  136 to 140 units an agent may cite: the entries of the three shared process
  templates, 19 passages of the Swiss Code of Obligations on tenancy, the
  proposition-sized spans of the message and an inventory of the attachments.

The **reference** is the answer an agent should reach. It was generated with the
case, and no system output was used to write it. It records:

- the dispute type (a defect, a lease termination or a rent increase);
- the scenario flags that decide each branch of the process;
- a process graph whose typed relations link decisions, facts, evidence
  capabilities, documents, steps and outcomes, including elements an output must
  not contain;
- the order of the steps;
- the evidence obligations, each from decision to fact, evidence and document,
  with the expected state of every document (missing, conditional, or provided
  but insufficient);
- the process state at intake and the next action, including escalation to an
  external specialist;
- three or four source locators for every grounded concept.

## Where things are

```
benchmark/                         the benchmark package exactly as evaluated
  data/dev/{claims,sources,source-registry,gold}   60 development claims and references
  data/test/{claims,sources,source-registry}       90 held-out claims
  rules/                           process templates and the 19 legal passages
  state-stress/                    48 one-update variants; 24 development references
  scorers/ runners/ schema/ ...    evaluator, schemas and baselines
heldout-references/                references of the 90 held-out claims
heldout-state-stress-references/   references of the 24 held-out variants
release-records/                   release grant and index for the held-out references
verify.py                          checks the evaluated files and references against recorded hashes
```

## Composition

| | |
|---|---|
| Claims | 150: 60 development, 90 held out |
| Dispute types | defects, lease terminations and rent increases, 50 each |
| Families | 28 (11 development, 17 held out); no family crosses the split |
| Language | English 75, Swiss Standard German (de-CH) 75 |
| Channel | email 70, portal 46, chat 24, phone note 10 |
| Attachments | 57 in 45 claims: 47 PDF notices, demands and forms, 10 photos |
| Customer message | 138 to 209 words (median 179) |
| Process graph | 7,800 concepts and 8,100 relations, each total including 600 an output must not contain |
| Branch conditions | 750 (3 to 7 per claim) |
| Obligation chains | 1,397 (8 to 10 per claim) |
| Order constraints | 3,450 (20 to 25 per claim) |
| Document states | missing 961, conditional 395, provided but insufficient 41 |
| Next action | process step 100, document request 35, escalation to an external specialist 15 |

## Using it

- **Train and prototype** on the 60 development claims, whose references ship in
  `benchmark/data/dev/gold/`.
- **Evaluate end to end** on the 90 held-out claims. Keep them out of training
  and tuning; no family crosses the split. The evaluator scores 33 metrics over
  process structure, evidence, grounding and calibration, and accepts an output
  only if it passes eight gates. Every reference output passes, and empty and
  request-everything outputs fail. An output must state its branch conditions in
  the scenario flags that the templates name. See `benchmark/README.md` for the
  commands and `benchmark/schema/submission-v3.schema.json` for the format.
- **Test state changes** with the 48 variants in `benchmark/state-stress/`. Each
  applies one update to one of 12 base claims (a sufficient document arrives, a
  branch fact becomes false or unresolved, or every active fact is resolved), and
  nine endpoints score how the requests and the active graph should change.

## Held-out references and verification

The benchmark package in `benchmark/` is unchanged from the version the paper
evaluated, so its own `README.md` and `LEADERBOARD.md` still describe the
original protocol, in which the held-out references were sealed. After the
evaluation, all 90 held-out references were released under CC BY 4.0
(`release-records/TARGET_RELEASE_GRANT.json`). Each file in
`heldout-references/` is byte-identical to the container whose SHA-256 was
committed in `benchmark/cohort.json` (`hidden_contract_commitment_sha256`) before
the evaluation. The 24 references in `heldout-state-stress-references/` were
regenerated with `benchmark/runners/state_stress_v3.py` from the held-out
references, and each matches the commitment in
`benchmark/state-stress/manifest.json`.

```
python3 verify.py
```

The held-out split is therefore public: it is a clean test split only for work
that keeps it out of training and tuning. Some development references carry a
legacy `metadata.split` label from the source corpus ("hidden" or "pilot"); the
release split is the one in `benchmark/cohort.json`.

## What it does not cover

The claims, messages, parties, images, process templates and references are
synthetic. Three kinds of real material appear: the 19 legal passages, quoted
from the Swiss Code of Obligations (SR 220, Fedlex, version in force on 1
January 2026); the official Canton of Zurich forms (amtliche Formulare) on
which 34 of the 47 PDF attachments are filled in; and the intake address of a
real legal-expenses insurer, used in every message as a fictional recipient. No
real claim, person or correspondence is included. All claims are set in one
canton. The mapping from law to process is for research and is
not legal advice. The reference captures each case at intake; change over time
appears only in the one-update variants. The next action, including escalation to
a specialist, is labelled but not scored by the released evaluator, and it varies
only among defect claims. Each obligation has one acceptable document, so route
choice is not tested. Images carry no labelled regions, and no field records
amounts, liability or coverage.

## Licence

The claims, documents, images, process templates, references and documentation
are released under CC BY 4.0 (`LICENSE-DATA`); the code under Apache 2.0
(`LICENSE-CODE`). The legal passages are official Swiss enactments, which
Article 5 of the Swiss Copyright Act excludes from copyright protection. The
text of the cantonal form templates remains with the Canton of Zurich and is
excluded from the CC BY 4.0 grant; the synthetic entries filled into them are
included.
