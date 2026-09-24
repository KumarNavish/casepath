> Current product scope: the main workspace uses all 150 original intake-only
> claims in `synthetic-150`; the original 60-case package is retained unchanged
> for legacy tests. See [the current packet release](INTAKE_PACKET_150.md).
> Historical 60-case statements below describe the predecessor release.

# Manual Pro implementation handoff

Use this repository for a direct, supervised ChatGPT Pro implementation
session. The current source is:

- Repository: https://github.com/KumarNavish/casepath
- Branch: `main`
- Local product: `http://127.0.0.1:4173/` after `./bin/casepath dev`
- First read: the root `README.md`, then this file and `AGENTS.md`

The repository contains the complete 150-claim intake workspace, source previews,
evidence investigation, hash-chained journal, persisted six-role Agent review
layer, same-origin API, deterministic tests, release tools, and research/evaluation
support files. It contains no private real claims, provider credentials, local
coordinator state, or current hosted deployment handoff.

## Give Pro one bounded implementation task

Open a new Pro conversation manually, provide the repository and branch, and
adapt this prompt to the desired outcome:

```text
Work in https://github.com/KumarNavish/casepath on main. Read README.md,
AGENTS.md, docs/PRO_HANDOFF.md, and the decision-relevant docs before editing.
Own this bounded deliverable: <describe one user-visible outcome>.

Run the current product locally in deterministic mode, preserve the existing
journal and any server already using port 4173, inspect the actual execution
path, implement the change, run focused regressions, and inspect the affected
browser journey. Do not use provider credentials, paid inference, reserved
research data, hosted Render services, or deployment workflows. Follow
CONTRIBUTING.md to seal source changes last. Report changed behavior, exact
checks, failures, and remaining limits.
```

Keep one active writer for overlapping files. A fresh Pro conversation does not
authorize deployment, research work, provider spending, or another writer on
the same surface.

## Product journey to improve

Experience CasePath as a first-time claims handler:

1. Find a claim in the queue.
2. Open the original message or an attachment and inspect its exact source.
3. Review the claim and follow each finding to its source.
4. Read the current step, conditions, questions, and document routes.
5. Try a condition in What if, then return to the saved assessment.
6. Edit the draft request and replay the claim journal.

Make the next action obvious and every decision traceable to admitted source
evidence. Verify loading, empty, error, retry, and recovery states; keyboard
operation; and desktop and mobile layouts when the change touches them.

## Source map

| Concern | Entry points |
| --- | --- |
| Workspace UI | `casepath/assets/claims-workspace-v1.js`, `claims-workspace-v1.css` |
| Page and presentation | `casepath/index.html`, `casepath/assets/claims-workspace-presentation-v1.js` |
| API mounting | `casepath-api/casepath_api/app.py`, `claim_loop_router.py` |
| Workspace state | `claim_workspace_v1.py`, `workspace_claim_loop_v1.py`, `workspace_operational_projection_v1.py` |
| Evidence investigation | `native_live_workspace_v1.py`, `native_workspace_inquiry_v1.py`, `native_claim_loop_bridge_v1.py` |
| Agent review | `agent_work/service.py`, `agent_work/runtime.py`, `agent_work/api.py`, `casepath/assets/agent-work-v1.*` |
| Authority and persistence | `claim_loop_service.py`, `claim_loop_store.py`, `workspace_evidence_authority_v1.py` |
| Operational intake data | `casepath-api/casepath_api/corpora/synthetic-150/manifest.json` |
| Legacy regression data | `casepath-api/casepath_api/corpora/synthetic-dev-60/manifest.json` |
| Launch and release | `bin/casepath`, `casepath/tools/casepath_release.py`, `build_static_site.py` |
| Tests | `casepath-api/tests/`, `casepath/tools/test_*.py`, `casepath-qa/` |

API filenames in the table are relative to `casepath-api/casepath_api/`.

## Authority and limits

The default local runtime uses an explicitly identified deterministic runner:
zero model calls, credential reads, or provider spend. It proves orchestration,
source, journal, and UI mechanics. It does not prove model competence, legal
correctness, real-world claim outcomes, or production readiness.

The six-role Agent review path has been accepted against the actual installed
application in deterministic reference mode, and one bounded external Facts-worker
substitution has also been accepted through the same source tools and gates. The
external proof used OpenRouter with `cohere/north-mini-code:free` for 6 genuine
provider responses, then survived a credential-free restart without another model
call. This establishes the integration path only; keep unknown evidence sufficiency,
deadlines, decisions, and readiness unknown until supported by admitted evidence
and a supported processing cycle. See [AGENT_REVIEW.md](AGENT_REVIEW.md).

The earlier Render frontend and API are suspended. Use a fresh clone of `main`
to judge the product; the [anonymous snapshot](https://anonymous.4open.science/r/casepath-9673/)
is for source inspection. Do not deploy this repository as part of a Pro task.
No recurring Pro task or research restart is required.

## Finish the session

Follow [source sealing](../CONTRIBUTING.md#seal-authored-changes), review the
diff, and leave a concise handoff containing:

- the user-visible behavior that changed;
- the files and authority boundaries affected;
- the exact focused checks and browser paths executed;
- any failed or skipped check and why;
- the final commit, if the task authorized a commit;
- the remaining product or validation limit.

The prior packaging evidence is recorded in [HANDOFF_VALIDATION.md](HANDOFF_VALIDATION.md).
