# Fair-baseline check (step 1)

**Post hoc, on Study 3's data (`fresh2/`), which are development data from now
on. Not a registered result.** All numbers are in `REPORT.json`, produced by
`analyse.py` with Study 3's registered scorers. Prompts and schemas were
hashed before any call on these data (`prompts/SHA256SUMS.json`,
2026-11-12T11:44:19Z). Spend from the ledgers: USD 4.45 (cap 5.00). No output
failed on these data (1,120 outputs).

## Designs

- **A, prompt with hold option.** Rules in context's own prompt with only the
  task replaced: an explicit three-way decision per document (request now;
  hold with a question when its need depends on a fact the file raises and
  leaves open; do not request), and in plain words the stop and silence rules
  the product's workflow encodes. Cost-efficient model, three runs; frontier
  model, one run.
- **B, Model executes rules** on the frontier model, one run. Study 3's design
  unchanged except for the model; it already contained a hold rule.

## Result

Tenancy: strict unsafe errors / all deviations per claim (claim-run means).
Theft: wrong + missed changes per pair. S: every fact stated. O: an open fact
or a denied or open defining event.

| Design | all | S (40) | O: open branch fact (23) | O: denied event (24) | O: open event (9) | Theft |
|---|---|---|---|---|---|---|
| CasePath, cost-efficient | 0.31 / 0.73 | 0.19 / 0.33 | 0.23 / 0.52 | 0.61 / 1.78 | 0.26 / 0.26 | 0.58 |
| CasePath, checklist only, cost-efficient | 0.34 / 0.73 | 0.21 / 0.34 | 0.32 / 0.61 | 0.72 / 1.78 | 0.00 / 0.00 | 0.55 |
| CasePath, checklist only, frontier (one run) | 0.30 / 0.70 | 0.05 / 0.05 | 0.61 / 0.65 | 0.29 / 1.79 | 0.67 / 0.78 | 0.83 |
| A, cost-efficient | 0.35 / 0.89 | 0.41 / 0.73 | 0.48 / 1.25 | 0.21 / 1.10 | 0.11 / 0.11 | 1.68 |
| A, frontier | 0.19 / 0.58 | 0.18 / 0.68 | 0.48 / 1.26 | 0.00 / 0.00 | 0.00 / 0.00 | 1.18 |
| B, frontier | 0.19 / 0.54 | 0.12 / 0.40 | 0.57 / 1.30 | 0.00 / 0.25 | 0.00 / 0.00 | 1.24 |
| Rules in context (Study 3), cost-efficient / frontier | 2.14 / 1.86 strict | 0.39 / 0.19 strict | 0.51 / 0.45 strict | 5.68 / 4.43 strict | 4.63 / 6.07 strict | 1.74 / 0.95 |

## What it shows

1. **Study 3's tenancy lead over the single prompt was largely an effect of
   what the prompt was told.** A prompt told the stop and hold rules makes
   0.35 strict unsafe errors per claim on the same model (CasePath 0.31;
   difference −0.03, p 0.74) and 0.19 on the frontier model (CasePath,
   checklist only, frontier: 0.30; difference +0.11, p 0.39).
2. **On denied defining events CasePath is now the worse design.** The
   hold-capable prompts on the frontier model make no error there; CasePath
   makes 0.61 strict errors and 1.78 deviations per claim, most of them holds
   after its readings disagreed on the denial.
3. **CasePath keeps a lead where a fact is tentatively worded or a supplied
   document is insufficient.** On open branch facts: all deviations 0.52
   against 1.25 to 1.30 (cluster-level p 0.007 to 0.016). The new designs hold
   documents that are required now whenever the wording is tentative, and
   accept an insufficient original as on file. On files that state every
   fact, the frontier core makes 0.05 deviations against 0.68 for the
   hold-capable frontier prompt (p 0.018).
4. **On theft the hold option does not help the prompt.** CasePath 0.58
   against 1.68 on the same model (cluster-level p 0.008); on the frontier
   model 0.83 against 1.18 and 1.24 (p over cases 0.04 and 0.02; over the nine
   clusters 0.10 and 0.15). The best frontier single prompt on theft remains
   Study 3's with the original rules (0.67).

## Irregularities

Theft cost ran 29 to 47% over the estimate (longer output per document). One
format-check output on the older data was truncated at the token limit; no
prompt was changed after the checks. `run.py` was changed after sealing to
send each batch's first case alone, which changes the order of sending only.
The frontier designs ran once per case.
