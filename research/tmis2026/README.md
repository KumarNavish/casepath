# CasePath for ACM TMIS: experiments and paper (Paper A)

This folder holds the technical paper that revises the ICLR 2027 submission
(57404) for ACM Transactions on Management Information Systems, and every
experiment run for it. It is built on the latest CasePath agent
(`claude/casepath-internal-20261027` at `aa4fb25`): typed interpretation,
independent verification, deterministic admission gates and the causal process
engine (`casepath-api/casepath_api/causal_process_v1.py`).

The separate professional-usefulness study (Paper B, IJHCS) is out of scope.

| Path | Contents |
| --- | --- |
| `WORKLOG.md` | Chronological record of what was done, decided and spent |
| `ANALYSIS_PLAN.md` | Hypotheses, metrics and contrasts, fixed before the main runs |
| `harness/` | Model client, methods, planners and scorers |
| `inputs/` | Prepared case inputs, including the new unresolved-fact variants |
| `runs/` | Raw model responses and the cost ledger |
| `analysis/` | Analysis scripts and their outputs |
| `scicore/` | sciCORE job scripts and results |
| `paper/` | The LaTeX source of the paper |

Nothing here changes the product, the released datasets or the frozen ICLR evidence.
