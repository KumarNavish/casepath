# Adversarial audit of the confirmatory design, and what came of it

Six independent lenses were run over the pre-registration, the method, the arms, the evaluator, the
analysis and the episodes, with instructions to attack rather than approve. They returned fifty-six
findings. Every finding below was then checked against the actual files by hand. Nothing here is taken on
the auditor's word; the refutations are as load-bearing as the confirmations.

## Confirmed, and acted on

**H1 was unfalsifiable as written.** Four lenses said independently that `ctes-ablation` cannot record a
hearsay receipt, so the clause "the ablation records at least five" could never be met. The confirmatory
run then produced exactly that: both arms scored zero. H1 is withdrawn as a test and the quantity it was
meant to capture is measured on premature readiness instead, where the two arms differ 6 to 24 with
fifteen families won and none lost. The error was mine — my own earlier splits already showed the ablation
at zero and I did not read them before setting the threshold.

**`channel_cap` is a compound switch.** Verified in `evidential_channel_v1.py`: the flag changes the unit
level, the treatment of party-reported delivery commitments, and — the structural one — whether a
requirement needs the returned artifact **and** an attestation or **either**. `METHOD.md` has been
corrected, and the confirmatory result now describes the ablation as content-based support rather than as
a single-effect ablation of the cap.

**The generator hash in the pre-registration was stale.** Verified and corrected; both generator versions
are now named, and each extension was shown to leave every earlier split byte-identical
(`eee7b0996ecf…`, `5229236adc08…`, `a174da29ddcf…`, and the first confirmatory half `6c54fd6ca72f…`).

**The bootstrap p and the confidence interval are one statistic read twice.** True. The Holm step across
H2 and H3 is therefore decorative, not a second gate, and both are reported as such. Neither H2 nor H3
was close to its threshold under any reading, so nothing turns on it.

**Failed model outputs are scored as zero acquired evidence and zero state accuracy, and the baselines
fail more often than the method.** Verified: `process-only` 11, `full` 6, `ctes` 3 of 246 turn-records
each. A sensitivity analysis dropping the eight episodes in which any arm failed is now reported: the
headline moves from +0.148 to +0.135 [+0.091, +0.181], 34 wins to 6, p = 0.0000. About a tenth of the gap
is the harness.

**`hearsay_receipts` counts `insufficient` as well as `received`.** Verified in `evaluation.py`. The
metric is now described in those words wherever it appears. The broader reading can only raise a count, and
the method scores zero under it, so the narrower reading cannot change the method's side of the contrast.

**The mini writer verbalises the hearsay condition where the Sonnet writer does not.** Verified by direct
search: eight of eighty-two mini-written episodes contain phrases such as "From memory, the notice is
dated…" or "Aus dem Gedächtnis steht in dem Protokoll…"; none of the twenty-six Sonnet-written episodes
does. Disclosed, with its direction: spelling out the provenance helps the arms that read content, so it
shrinks the measured gap rather than widening it.

**H4 had no teeth.** Predicted in the amendment that introduced it and confirmed by the outcome: it flipped
between two null results. The writer question is now answered on the metric that does separate, where the
effect is +0.156 under one writer and +0.139 under the other.

## Refuted by reading the code

**"The baselines run at lower reasoning effort and a smaller token budget than CTES."** False, and this
was the most serious accusation. `arms.py` does set `reasoning: {effort: low}` and `max_tokens: 3000`
inside `build_request`, but `runner.emit_requests` extracts `req["messages"]` and nothing else, and
`run_turn.py` sends every arm through the same call with `max_tokens` 8000, `temperature` 0 and no
reasoning parameter at all. The dead fields never reach the provider. Every arm ran under identical
transport parameters.

**"Twelve of forty episodes contain no live hearsay trap."** False. Counting motif bindings capable of
creating one, every episode in both halves has at least one; the distribution is 1 to 4 per episode with
zero episodes at zero.

**"B2 is unrequestable in all fourteen termination_payment episodes because two requirements share it."**
False as stated. Two packs do share a document between requirements (`A6`, `B2`), which is the intended
role of the authenticated export, and the request planner takes the union over all satisfying options, so
a shared document is requestable through either requirement.

**"The strongest baseline's prompt omits the provenance rule."** False. `SHARED_SYSTEM_PROMPT` states
"Source provenance supports what a paragraph reports, not authenticity, current truth, legal effect, or
another time/version" and "Received requires an exact observed source reference", and the direct baseline
carries the same rule. The baselines are told the rule in words; the method enforces it in code. That is
the comparison the paper is making.

## Standing, unfixed, and disclosed

- No single-effect ablation of the channel cap exists.
- The writer-swap control covers thirteen of forty-one families and one writer pair.
- `U` charges premature readiness and does not reward correct readiness, so a never-deciding arm such as
  `constant` is not penalised for its twenty-nine missed decisions.
- The burden term is capped at four over three turns, which makes "request everything" nearly free.
- The confirmatory run is complete, so every change above is a description or a disclosure. Not one of
  them altered a number, an arm, an episode or a decision rule after the fact; anything that would have
  requires a newly named run under the stopping rule, and none was started.
