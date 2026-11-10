# Blind check of the fresh2 tenancy claims

Question: does each message (with its attachments) imply the fact states of its design, and does each attachment
show exactly the content items the design gives it? The answer is reported as it came out; no message was replaced
because it was misread, and only an objective authoring error was corrected.

## Reader and procedure

- **Reader.** `claude-fable-5-2`, in four separate Claude Code Remote sessions (one per quarter of the claims) and
  one more session for a re-read. The sessions had no repository and no files; each saw only its prompt. The reader
  is not one of the evaluated models (gpt-6-luna, gpt-6.1-terra). It belongs to the same model family as the
  author of the messages (see `README.md`), so it is not an independent human judgement.
- **What it saw.** The instructions (`tenancy/build/blind_check/INSTRUCTIONS.md`), the glossary of fact and
  content-item meanings (`GLOSSARY.txt`) and, per claim, the channel, subject, body, attachment texts, the list of
  fact ids and the list of content items per attachment (`part_1.txt` … `part_4.txt`; claims shuffled with a fixed
  seed). It never saw a flag, a fact state, a design value, a sufficiency mark or a reference.
- **What it returned.** For every fact: stated_true / stated_false / open / not_mentioned with a quote; for every
  content item: shown or not (`reading_part_*.json`, copied verbatim from the session results; session ids in
  `sessions.json`). All 314 non-empty quotes of the first reading occur in the texts as read (one of them, from
  the claim corrected below, no longer occurs in the sealed text); all quotes of the final readings occur in the
  sealed texts.
- **Comparison.** `tenancy/blind_compare.py` (no model) compares each reading with the design
  (`comparison_first_reading.json`, `comparison.json`). Two readings are accepted although not literal because
  they leave the reference unchanged under the silence policy: an unmentioned (absent) branch fact read as stated
  false, and an unmentioned defining event read as stated true. A denied branch fact read as not mentioned would
  also be accepted (it did not occur).
- **Transcription.** The parts were pasted into the session prompts. The prompt of part 4 contains one stray line
  `--- ` between the two attachments of claim `f2cl_6c0beb4edcdc571d`; nothing else differs from `part_4.txt`.
- **Cost.** The five reader sessions reported USD 3.63 in total (outside the repository's model client and ledger).

## Results

First reading of all 96 claims (448 fact judgements, 157 content-item judgements):

| | Judgements | Literal agreement | Accepted |
|---|---|---|---|
| Facts, all | 448 | 438 (97.8 %) | 447 (99.8 %) |
| Stated true | 222 | 222 | 222 |
| Stated false (denied) | 50 | 50 | 50 |
| Raised and left open | 32 | 32 | 32 |
| Absent branch fact | 139 | 132 | 138 (6 read as stated false; 1 read as stated true) |
| Unmentioned defining event | 5 | 2 | 5 (3 read as stated true) |
| Content items | 157 | 150 (95.5 %) | – |

How explicitly the 272 stated facts (true or denied) are worded, and how they were read:

| Wording (design) | Facts | Read correctly |
|---|---|---|
| plain | 135 | 135 |
| in passing | 89 | 89 |
| implied only | 48 | 48 |

Claims read entirely as designed: 80 of 96 literally, 88 of 96 with the accepted readings (first reading); 89 of 96
after the correction below. The remaining 7 claims differ only in content items.

## Changes

**After the blind reading (1 claim, 1 fact).** `f2cl_7850a89c062dfd72` (termination, family 15): the design leaves
`family_home` unmentioned (absent, presumed false), but the message spoke of "my husband's business" and "a flat for
five people", which implies a married couple living in the flat. The reader marked `family_home` stated true. This is
an authoring error against the design; the two phrases were changed to "my business" and "a flat for four people".
A fresh session re-read the corrected claim and returned family_home = stated false (accepted: false either way);
all other facts as before (`reading_reread_f2cl_7850a89c062dfd72.json`).

**Before any reading (author's self-review against the briefs, recorded for completeness).**

| Claim | Change | Reason |
|---|---|---|
| `f2cl_440d59612c87d177` | landlord's letter: removed "left without proper ventilation of the stairwell" | could suggest damp; mould is absent |
| `f2cl_753a10b9d25479c6` | "I'm inclined to do that" → "I intend to do that" | deposit is stated, not open |
| `f2cl_9d9b9e6660448586` | removed "Ich lebe allein" | family_home is absent, not denied |
| `f2cl_45158e0185bd82b6` | removed "Mein Mann hat die Kündigung nicht separat erhalten" | an extra legally relevant fact outside the design |
| `f2cl_8da32c6cda5795f7` | removed "My wife is due to give birth" (replaced by care for a parent) | implied a family home that is absent |
| `f2cl_201a01ca1e26f323` | the landlord's quoted reason no longer names the reference rate | the design wants this fact implied, not plain |
| `f2cl_fb68d264129b3c97` | removed "in heavy rain water comes in onto the sill" | a moisture problem; mould is absent. Made after part 1 had been sent and before part 2 (which contains this claim) was read |

## Disagreements left in place (7 content items, 0 facts)

| Claim | Attachment | Item | Design | Reader |
|---|---|---|---|---|
| `f2cl_a5d873ad4151b24e` | landlord's reply (sufficient) | proposed_work = "a visit by the caretaker to assess the problem" | shown | not shown |
| `f2cl_3daad3eb95ae2c15` | landlord's reply (sufficient) | same | shown | not shown |
| `f2cl_ac669bf78a141b38` | landlord's reply (sufficient) | same | shown | not shown |
| `f2cl_be3f0eb859b33907` | landlord's reply (sufficient) | same | shown | not shown |
| `f2cl_6c0beb4edcdc571d` | landlord's reply (insufficient: no position) | same | shown | not shown |
| `f2cl_fb68d264129b3c97` | landlord's reply (insufficient: no position) | same | shown | not shown |
| `f2cl_ac851a27a08a4047` | landlord's reply (insufficient: no proposed work) | landlord_response = "a contractor has been informed" | shown | not shown |

Each attachment contains the content item exactly as the design specifies it (the design values come from the same
list as in `fresh/`), so these are not authoring errors. The reader does not count a caretaker's inspection visit as
"work the landlord proposes" (6 of 6 such letters; letters proposing repairs or a part replacement were read as
showing it), and once did not count "we have informed the contractor" as a position (it did in a similar German
letter, `f2cl_d39619540633db7d`). For four attachments the reference says *supplied sufficient* while the reader
would call them insufficient; a design that reads them the same way will request `landlord_response_history` in
those four claims and be scored with an unnecessary request. The readings are recorded per claim in the reference
(`blind_check_reading`, `blind_check_fields`) so that analyses can stratify by them.

## What this says about explicitness

Every stated, denied or open fact was read as designed, including the 48 that are only implied and the 89 stated
in passing; the claims are therefore explicit for a careful reader even where a real claimant would not spell the
fact out. Silence is less clear-cut: 7 of 139 absent facts were read as denied, and 3 of the 5 unmentioned defining
events were read as stated (the notice is implied by the dispute), as in `fresh/`. The unmentioned-defining-event
condition is therefore weak (5 claims) and does not change any reference.

## Theft

The theft texts were not given to a reader: the condition sentences are fixed verbatim by the source contract, and
`theft/build_theft.py` checks in code that each occurs exactly once and that each changed text differs from its
story's base text by that sentence only.
