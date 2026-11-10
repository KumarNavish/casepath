# Brief to the product session: paper-sync branch of 2026-11-10

From the paper session, through the study lead. Brief first, separate branch,
no force-push, as agreed. You or the study lead merge; I do not push to
`claude/casepath-internal-20261027`.

## What I ask

Fast-forward the product branch to
`claude/casepath-internal-paper-sync-20261110d` at `NEW_HEAD`
(source-tree hash `NEW_HASH`), or tell me before the merge which behaviour
you will not take. The branch is your tip `abe968b5` plus 63 commits. All
tests pass (`NEW_TESTS`), yours included.

**Why a fast-forward matters.** The paper's confirmatory test runs on exactly
this tree. If the product takes it unchanged, `python -m casepath parity`
gives the same `source_tree_sha256` inside and outside, and the paper can say
the tested system is the deployed system. Each behaviour you change after the
merge is a difference I must report.

## What the branch does, in one paragraph

It makes the checklist depend on facts that several independent readings
agree on and can quote, and it closes the ways a single agent, a presumption
or a stopped step could change a checklist unnoticed. Two independent code
reviews (about 40 findings) are fixed, each with a test that fails without
the fix. `docs/PARITY.md` lists every behaviour change; its section
"Behaviour changes that both deployments must approve" is the authoritative
list. The main ones:

1. **Three readings, all must agree** (`CASEPATH_READINGS`, default 3, at
   least 2). Every reading judges every condition, in the same order.
2. **Four answers per condition:** true, false, open (the file itself says it
   is not known; the words are quoted), not stated. Only an open answer makes
   a fact "raised and left open".
3. **No presumption over a stated doubt.** If any reading quotes a doubt from
   the file, the fact stays open and its documents are held, the defining
   event included (`OPEN_RULE = "any"`).
4. **After the readings no single agent can set a deciding or routing fact.**
5. **Routing can be corrected once.** When all readings contradict the route,
   the case is routed again on their value; otherwise it is handed over with
   the conflict recorded.
6. **A document counts as present only after a second, independent
   judgment.** When the finder stops early, unchecked needs stay requested
   and are marked not checked.
7. **Quotation matching** folds typography by an explicit list only.
8. **The parity manifest prints the effective settings** (`readings`,
   `open_rule`, `run_scope`, `model_reasoning`).

## What it buys (development data, cost-efficient model; not test evidence)

| | Product, this branch | Single prompt, same model | Single prompt, frontier model |
|---|---|---|---|
| Theft, wrong or missed changes per pair (stories 4–5 / 6–7) | 0.43 / 0.57 | 1.33 / 1.41 | 0.54–0.67 |
| Tenancy, strict errors per claim (72 claims) | 0.18 | 0.20 | 0.16 |
| Probe: defining event denied, unsafe errors per claim | 1.2 | 6.6 | 6.0 |
| Probe: defining event left open, unsafe errors per claim | 0 | 3.3 | 6.5 |

As merged before this branch (7ff7af64) the product stood at 1.83 on theft
and about 1.05 on tenancy.

## Decisions that are yours

| # | Decision | Default on the branch | How to change |
|---|---|---|---|
| 1 | Three readings instead of two: one more model call per run, fewer wrong values | 3 | `CASEPATH_READINGS=2` |
| 2 | A doubt quoted by any reading blocks a presumption (more holds, no request over a stated doubt) | any | `OPEN_RULE` in `process/workflows.py` |
| 3 | A need the process builder adds stays a suggestion until a workflow, Knowledge or a handler confirms it | on | revert commit "A need the process builder adds stays a suggestion…" |
| 4 | Checklist-only run (`CASEPATH_RUN_SCOPE=checklist`): skips the brief, the result checker and the fact checks. In every measured run these steps changed no checklist and cost about three quarters of the run | off | revert the checklist-only commit and its fixup together |
| 5 | Reroute after the readings: a second full team run when it happens | on | — |

Changing 1, 2 or 5 changes what the paper tested. 3 and 4 do not affect the
test.

## To check inside before turning the branch on

- **Model reasoning must be on** (`CASEPATH_MODEL_REASONING=true`, as your
  deployment files already set). With it off and temperature 0 the three
  readings are near-identical requests and the agreement rule is weak.
- **The gateway must accept `reasoning_effort` together with `max_tokens`**
  on the chat connector; some endpoints expect `max_completion_tokens`.
- **Readings go at low effort** on every deployment.
- **Cases over 40,000 characters** take the agent path for facts and
  keyword passages for the second judgments; deciding facts will more often
  stay open there. None of my measurements covers such cases.

## Interface: left for you, not changed by me

The interface commits on this branch have not had your design self-review
(`docs/product/NORTHSTAR.md`); please run it or drop them.

- A reroute and a contradiction hand-over are in the journal, the result and
  the text report, but the interface does not show them.
- `casepath.js` reads `c.added`, which no longer exists ("undefined found
  only now").
- A stop warning without `agent` is dropped silently.
- The stop notes for the claim reader and the document finder in
  `casepath.js` differ from the corrected ones in `report.py`.
- The warning kind `routing_contradicted` is not shown.

## Names already in the product (not from this branch)

`config.py` ("gpt-5" deployment-name rule), the connector file names
`anthropic_model.py` and `azure_model.py`, `deploy/workspace/env.example`,
the Databricks deploy files, `docs/COORDINATION.md`, and the organisation
name in `team.py` (`DEFAULT_VOICE`), `mining.py` and `HANDLER_BAR.md`. No
commit message on the branch names a model, a vendor or an assistant.

## What I need back

After the merge: the commit and the `source_tree_sha256` from
`python -m casepath parity` inside. If they equal the values above, parity
is shown; if not, the list of what you changed.
