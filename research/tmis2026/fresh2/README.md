# Fresh2: unseen data for the Study 3 confirmatory test (sealed 2026-11-10)

These are new held-out cases for a pre-registered confirmatory test of CasePath. They were built and sealed before
any compared design, baseline or scorer ran on them, and no design output was consulted while writing them.
`fresh/` (Study 2) has been development data since its study ran; fresh2 replaces it as the unseen set.

**Rule.** No design, baseline or scorer may run on fresh2 before `research/tmis2026/ANALYSIS_PLAN_STUDY3.md` is
committed. The guard enforces this (`guard.py`): `harness/v2/common.py::data(kind, "fresh2")` and the runners'
`--data fresh2` refuse unless that file exists and is committed unmodified, and both loaders refuse every data
access in a process that has the repository's model client (`llm`) loaded or `TMIS_MODEL` set. The model-free
`check.py` is unaffected. The analysis plan is not part of this folder.

`MANIFEST.json` records the SHA-256 of every file and the statistics; `python3 seal.py` rewrites it and
`python3 check.py` verifies data and hashes.

| | Theft | Tenancy |
|---|---|---|
| Units | 72 changed-fact pairs, 48 unresolved-fact pairs (8 new stories × 9 / × 6) | 96 claims in 24 families of 4 |
| Loader | `theft_fresh2.py` (interface of `fresh/theft_fresh.py`) | `tenancy_fresh2.py` (interface of `fresh/tenancy_fresh.py`) |
| Built by | `theft/build_theft.py` with `theft/stories.py` | `tenancy/build.py` (seeded design) + hand-written messages in `tenancy/authored/` |
| Reference | frozen source contract, BENCHMARK_V3 format, frozen `best_realization` scorer | production engine with exact deferral, under the silence policy |

The runners and scorers read fresh2 with `--data fresh2` (added to `harness/v2/run.py`, `v3.py`, `evolve.py`;
other scripts that take `--data` pass it to `common.data`). Code that imports `tenancy_fresh` directly (for example
`harness/product/`) needs the path changed to `fresh2/tenancy_fresh2.py`.

## Who wrote the texts

All case texts (tenancy messages and attachments, theft story documents) were written by a generative model,
Claude Opus 5.5, working as an agent in this repository, from the design briefs; it is **not among the evaluated
models** (gpt-6-luna, gpt-6.1-terra), and no evaluated model read or wrote any of the data. No model API call was
made through the repository's client. The blind check used a different model of the same family
(`claude-fable-5-2`) in separate sessions (`BLIND_CHECK.md`). Phrasing patterns of one author model are shared
across the whole set.

## Theft: eight new stories (ids 8–15)

**Construction.** `theft/build_theft.py` runs the released construction scripts
(`data/casepath-theft-pairs/construction/`) unchanged except for their list of contexts, which holds the four
original contexts, the four contexts of `fresh/` and one-sentence contexts of the eight new stories. It checks that
the rebuilt original stories reproduce `BENCHMARK_V3.json` (72 texts identical; references identical except where
amendments V2 and V3 changed them), that stories 4–7 reproduce `fresh/` (72 texts identical), that the released
input-free and minimal-edit preflight passes, and that the reference of every condition is the same in all sixteen
stories.

**New settings.** Each story is a different kind of case document, with its own place, objects, people and policy
details: a broker's letter (holiday flat in Chur; skis, coffee machine), an insurer's intake note (nurse's flat in
Sion; drone, handbags), an online form filled in by a daughter (retired couple in Fribourg; kitchen appliances,
silver cutlery), a loss adjuster's report (basement compartments in Thun; camping gear, power tools), a lawyer's
letter (designer's townhouse in Schaffhausen; art prints, drawing tablet), a social worker's e-mail (widow's flat in
Bellinzona; fur coat, porcelain figurines), a call-centre log (family flat in Aarau; projector, vinyl records) and a
handover note between handlers (new flat in Yverdon-les-Bains; gaming PC, sneakers).

**Condition sentences.** Unlike stories 0–7 (a context paragraph and a bulleted list), the nine condition sentences
of the contract are embedded verbatim at different positions in each document (narrative paragraphs, field lists,
log lines, closing remarks); the sentences themselves are those of the released script (`STATE_TEXT`) and of
`harness/theft_data.py` (`UNRESOLVED`). The off text has all nine false; each on text replaces exactly one sentence,
each unresolved text replaces it by the open-condition sentence (checked in code). Surrounding detail is written to
be compatible with both values of every condition (no phone, no closed list of stolen items, no contractor, repair,
insurer demand, decision or recovery). Off texts have 260–320 words (stories 0–7: 152–167).

**Reference.** Each pair carries the V3 reference of its condition with renamed requirement ids, exactly as in
`fresh/`.

## Tenancy: 96 new claims in 24 families

**Families.** Each family is a dispute type × combination of true flags that none of the 150 Study 1 claims and none
of the 72 `fresh/` claims uses (checked in `tenancy/build.py` and `check.py`). Only 16 such combinations remain with
the dispute's defining event true: 13 defect families and 3 termination families (arrears and retaliation with zero,
one or two of extension and family home). The other 8 families are the first in which the **defining event is
false**: the landlord has announced a termination (4 families) or a rent increase (4 families, all four rent
combinations), but the tenant has received nothing in writing. Under the engine every document is then not needed,
whatever the branch flags; these families test whether a design honours an explicit denial of the defining event
and holds documents when that event is left open.

- defect: 13 families, 52 claims; termination: 7 families, 28 claims (3 with the notice received); rent increase:
  4 families, 16 claims (all without a written notification).
- 72 claims have two or more true branch flags (up to five).

**Fact states.** Every true branch flag is stated; a false branch flag is mostly left unmentioned (absent, 139) and
sometimes explicitly denied (50 denials in all, including 24 denied defining events). Each stated or denied fact
carries a designed wording: plain (135), in passing (89) or implied only (48), recorded in the reference
(`expression`). In the 12 claims whose notice was received, the defining event is stated in 6, unmentioned in 5 and
left open in 1.

**Open facts.** 32 claims (one third) raise one fact and leave it open; its true value is recorded (17 true,
15 false). In every family with the defining event true, one or two claims have an open fact (24 claims;
health effects 6, mould 4, heating 3, specialist 3, deposit 3, extension 2, family home 1, retaliation 1, and the
notice itself in 1); in each family with the defining event false, one claim leaves that event open (8 claims), so
that everything the branch flags would require is held. `check.py` confirms that every open fact holds at least one
document and that resolving it changes the plan. 86 documents are held; 53 of them come from the 8 claims with an
open defining event.

**Silence policy and reference.** As in `fresh/`: the policy clause is added to each template
(`tenancy/rules/static-rule-templates-v3-silence.json`, identical to `fresh/`); an unstated branch fact is presumed
absent; the defining event is presumed to have occurred unless the claim denies it; a fact raised and left open is
unresolved. The engine (`harness/casepath_tenancy.py::plan_from_verified_exact`, exact deferral) computes each
document's state from the true flags under that policy: `required_now`, `supplied_insufficient` (both requested),
`held`, `supplied_sufficient`, `not_needed`. The answered plan, with the open fact at its true value, is recorded.
33 claims have an empty request set (the 32 with the defining event false, and one with the notice left open).

**Supplied documents.** 40 claims carry 51 plain-text attachments (lease contracts, defect letters, landlord replies,
repair-deadline letters, payment reminders, termination notices). Each shows every content item its type requires
(`REQUIRED_FIELDS`) or lacks exactly one; 25 are sufficient and 26 insufficient, and the reference marks each. An
attachment is never one held behind the open fact, never one that would reveal an unmentioned notice and never one
that would settle the open fact.

**Messages.** 48 English and 48 Swiss Standard German; channels in Study 1 proportions (45 e-mail, 29 portal, 15 chat,
7 phone notes); 77–220 words (chats and phone notes are shorter). Senders, landlords, places and streets are new lists.

**Blind check.** See `BLIND_CHECK.md`: on first reading 438 of 448 fact judgements agreed literally and 447 were
accepted; 150 of 157 content-item judgements agreed. One claim with an authoring error was corrected and re-read;
seven content-item disagreements are left in place and recorded per claim.

## Known limitations

- **Rule application, not legal correctness.** Tenancy references come from the engine that CasePath itself uses,
  under the silence policy every design receives.
- **Theft reuses Study 1's ingredients.** The nine conditions, their sentences, the frozen contract (two conditions
  contested in Study 1's blind re-derivation) and the 98/99 extracted rules are those of Study 1; only the settings
  and the embedding are new. The rule-review and repair passes were developed with knowledge of these conditions.
- **No unused rent-increase combination with the notice received.** Rent appears only in the denied-notice
  families; with the notice denied the branch flags change no reference.
- **Degenerate references.** 24 claims (defining event denied) have every document not needed; 8 more hold
  everything behind the open defining event. Results should be reported with and without these 32 claims.
- **Unmentioned defining event is weak** (5 claims; 3 were read as stated), as in `fresh/`.
- **Content-item ambiguity.** Four landlord replies marked sufficient were read by the blind reader as lacking the
  proposed work (a caretaker's inspection visit).
- **One author model** wrote all texts; one reader model checked them.
