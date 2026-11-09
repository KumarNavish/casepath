# Fresh data for Study 2 (sealed 2026-11-09)

These are the held-out data for the confirmatory second study (`STUDY2_DESIGN.md`, "Fresh data"). They were built and sealed before any compared design ran on them, and no method output was consulted while authoring them. `MANIFEST.json` records the SHA-256 hash of every file, the counts and the generator model; `python3 seal.py` recomputes the statistics, reruns the oracle check and rewrites the manifest.

| | Theft | Tenancy |
|---|---|---|
| Units | 36 changed-fact pairs, 24 unresolved-fact pairs (4 new stories × 9 / × 6) | 72 claims in 18 families of 4 |
| Loader | `theft_fresh.py` (interface of `harness/theft_data.py`) | `tenancy_fresh.py` (interface of `harness/tenancy_data.py`) |
| Built by | `theft/build_theft.py` (released construction scripts) | `tenancy/generate.py` (seeded generator, one writer model) |
| Reference | frozen source contract, BENCHMARK_V3 format | production engine with exact deferral, under the silence policy |

## Theft: four new stories

The released construction script `data/casepath-theft-pairs/construction/theft_causal_benchmark.py` is run unchanged except for its list of story contexts. The list holds the four original contexts followed by four new ones, written for this study:

- St. Gallen, a couple in a terraced house after a weekend away; jewellery and binoculars.
- Lucerne, a student in a shared flat; a games console and headphones.
- Lugano, a retired teacher after a hospital stay; a coin collection and a television.
- Winterthur, a family in a detached house at night; musical instruments and a sewing machine.

`theft_branch_diagnostic.py` derives the branch-document projection from the frozen reference contract. The build checks four things:

- The rebuilt original stories reproduce `BENCHMARK_V3.json`: all 72 texts are identical, and every reference is identical except where amendments V2 and V3 changed it.
- The released input-free and minimal-edit preflight passes.
- Every condition has the same reference in all eight stories.
- Each new pair and unit has the same keys as the V3 records.

New pairs carry the V3 reference of their condition, with alternatives and requirement ids renamed. They use the nine Study 1 condition sentences and the six open-condition sentences from `harness/theft_data.py`. Stories are numbered 4–7, and the texts run from 157 to 167 words (Study 1: 152–158).

## Tenancy: 72 new claims

**Flag combinations.** Each family is one dispute type × true-flag combination that none of the 150 Study 1 claims uses (checked in code):

- rent increase: 1 family (reference rate + renovation, the only unused rent combination);
- lease termination: 8 families;
- defect: 9 families.

52 of the 72 claims have two or three active branch conditions.

**Fact states.**
- Every active branch fact is stated; every inactive one is left unmentioned (absent).
- In 18 claims (one per family, 25 %), one branch fact is raised and explicitly left open. Its true value is recorded: true in 9 claims, false in 9.
- The routing fact (termination notice received, rent-increase notification received) is stated in 18 of the 36 claims that have one and left unmentioned in the other 18.

**Silence policy.** The policy is added as a clause to each template (`tenancy/rules/static-rule-templates-v3-silence.json`; the process catalogues are unchanged) and applied in the reference:
- an unstated branch fact is presumed absent;
- the dispute's defining event is presumed to have occurred;
- a fact raised and left open is unresolved.

**Reference.** The production engine computes each document's state from the true flags under that policy (`harness/casepath_tenancy.py::plan_from_verified_exact`, with supervaluation for the open fact). The possible states are:
- `required_now` (requested);
- `supplied_insufficient` (requested);
- `held` (depends on the open fact);
- `supplied_sufficient`;
- `not_needed`.

The answered plan, with the open fact at its true value, is recorded too, so both the hold and the eventual answer can be scored. `tenancy/oracle_check.py` rebuilds every reference independently from the true states and reproduces all 72.

**Supplied documents.** 29 claims (40 %) carry 38 plain-text attachments: lease contracts, termination notices, payment reminders, defect letters, landlord replies and rent statements. Each attachment either shows every content item the pack requires of its type (`REQUIRED_FIELDS`) or lacks one. 18 are sufficient and 20 insufficient, and the reference marks each one accordingly. An attachment is never one held behind the open fact, never one that would state an unmentioned routing fact, and never one that would settle the open fact.

**Messages.** 36 English and 36 Swiss Standard German, 142–219 words. Channels follow Study 1's proportions: 34 e-mail, 22 portal, 11 chat, 5 phone notes.
- The writer is `anthropic/claude-haiku-5.5`, which is not one of the evaluated models.
- It receives only the scenario: dispute, facts to state, the open fact, topics to avoid, persona details and attachment contents. It never sees rules or document lists.

**Blind check.** The same model, in a fresh context without the scenario, reads each message and its attachments. It reports, for every flag, stated true / stated false / open / not mentioned, and, for each attachment, which required content items it shows.
- A draft that disagrees is rewritten at most twice, with feedback naming the fact or item, never a rule.
- A claim that still disagrees is replaced by a new claim with the same design.
- In the final generation run, 87 claims were written for the 72 slots. 15 were replaced; 52 were accepted on the first draft, 11 on the second and 9 on the third.
- Agreement over all 146 checked drafts was 90 % on facts and 96 % on content items. On first drafts it was 91 % and 97 %.

Two readings are accepted because they leave the reference unchanged under the policy. Both are recorded per claim in `blind_check_reading`:
- an absent branch fact read as "stated false" (6 of 159 absent facts in accepted claims);
- an unmentioned routing fact read as "stated true" (14 of 18 unmentioned routing facts).

**Spend.** Generation and checking cost USD 0.47 in total (ledger tag `exp="fresh_generation"`, `runs/ledger.jsonl`). This includes two interrupted or superseded runs while the acceptance rule was fixed; their drafts were not used.

## Known limitations

- **Rule application, not legal correctness.** The tenancy references are computed by the engine that CasePath itself uses. This regime tests whether a design applies the given rules under the stated silence policy, not whether those rules are legally correct.
- **Theft reuses Study 1's ingredients.** The theft stories reuse the nine Study 1 conditions, their sentences, the frozen contract and its known reference choices (two conditions were contested in Study 1's blind re-derivation). Only the story settings are new.
- **Rent increase is thin.** It has a single family (4 claims), because only one unused flag combination exists.
- **The routing fact is mostly implied.** Most messages that leave it unmentioned still imply it (14 of 18 were read as stating it). The "unmentioned routing fact" condition is therefore weak, and the reference is the same either way.
- **Small and narrow.** Held documents arise only from the 18 open facts (22 held documents in all).
- **Model-written text.** The messages come from one writer model and were accepted by the same model's blind check. Phrasing patterns of that model are shared across the whole set.
