# Reservation-only correction and exact-draft review

Status: prospective configuration, no provider execution, no credit allocation,
no protected scoring, no experiment admission. Existing V5 and study-v1 evidence
are not rescored or overwritten. This delta does not touch validate_journal.py,
test_journal_corpus_restart.py, the product journal, or the original evaluator.

## Pricing

The supplied standard OpenAI endpoint audit (2026-09-19T18:44:40.968940+00:00;
SHA256 7539ceec75f6151b0568b96d401ee297c2ff4058c68f986ebcb8cfca98bd8383)
reports ordinary input $2/M, cache-read $0.20/M, cache-write $2.50/M,
completion $12/M. The official OpenRouter prompt-caching documentation inspected
for this correction describes cache writes at 1.25 times ordinary input for
GPT-5.6 and later, and separate read/write token counts:
https://openrouter.ai/docs/guides/best-practices/prompt-caching
https://openrouter.ai/docs/cookbook/administration/usage-accounting

These are alternative input categories, not three simultaneous charges on every
token. Reserve every input token at max(2, 0.20, 2.50)=$2.50/M. This assumes no
cache hits or discounts. Preserve actual account charges as authoritative; never
replace an unknown charge by a calculated value. Long-context premiums, tools,
web search, storage, and any newly introduced fee cannot be silently ignored.
The existing <272,000 context threshold and no-tools policy remain unchanged.

## Token bounds and feasibility

Count actual message content UTF-8 bytes, roles and the existing 4,096-token
protocol allowance. JSON HTTP wire escaping does not become model text.
The byte bound is NOT an exact native tokenizer count or characters/4 estimate.
The canonical tokenizer/usage-bound attestation remains required.

Source preparation is not generated yet. Its 131,072-byte bound must not be
replaced by a made-up typical token count. Each same-case draft retains its
65,536-byte bound. Financial reservations are clipped at the per-send 200,000
input limit, but a hypothetical future envelope exceeding that limit is reported
separately. A financial ceiling is not proof that future requests will fit.

This correction does not select a smaller output cap merely to obtain a desired
price. All five learned arms retain two calls, 12,000 completion tokens per call,
one sample, singleton cases, the same source/preparation information, model,
route, reasoning effort, and complete native final artifact. Source preparation
retains two 32,768-completion-token calls. Temperature is still omitted and its
effective binding unverified, exactly as in the predecessor configuration.

## Duplicate-free review

Every learned arm may return a complete replacement as before or an explicit
review edit envelope targeting only its own exact generated first-stage draft.
An empty edit list retains the entire draft; it is not an exemption from final
schema/coverage validation. Add/remove/replace operations are deterministic,
bounded, and sequential; no evaluator data or template fills missing fields.
A complete replacement remains permitted. This can reduce actual repeated
output, but does not justify a lower worst-case output reservation.

Raw provider replies, the expanded final object and both source hashes remain
preserved. The native export is a projection. Full CasePath planning objects
still preserve route grouping and joint adequacy. Rule-First is not relabelled
as the unrecovered preserved kernel.

## Estimand

This five-arm comparison is planning/control conditional on an equally supplied
prepared source/process/obligation representation. It cannot establish end-to-end
source-to-process superiority. The all-150 population and original 60/90 split,
family/domain weighting, adverse cells, and evaluator boundary remain unchanged.

## Bound returned by the complete offline render

1,502 request slots; 750 learned cells; 1,050 cells including deterministic rows.
The supplied retained observation-only projection was reused (pypdf 5.9.0).
It is not relabelled as the historical pypdf 6.10.0 projection.

Preparation $1.4569345; development $386.4000000; protected $579.6000000.
Total $967.4569345, rounded UP to $967.46.
Output ceilings alone: $216.786432.
Credit upper bound minus those output ceilings: $20.023568 BEFORE other usage
or reservations. At $2.50/M, that permits at most 8,009,427 input tokens across
all requests, an average of approximately 5,332.51 per slot.

The remaining obstruction is a certified tighter whole-schedule envelope,
including the not-yet-generated preparation and review drafts, or a substantively
justified shared inference budget with preserved complete-output capability.
The byte-bound failure is not a proof that the actual bill or every scientifically
adequate configuration must exceed the balance. No affordable configuration or
allocation is established here. Do not begin an incomplete paid comparison.
