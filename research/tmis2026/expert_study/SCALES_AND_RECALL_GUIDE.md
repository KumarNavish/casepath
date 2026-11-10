# Scales and the stimulated-recall guide

No item wording is reproduced here: I did not have the source text of either scale in front of me. Each wording must
be copied from the source named below, in German, and the copy checked by a second person against that source.

## 1. Recommendation: raw NASA-TLX (five items) and FOST (five items)

| | Workload | Trust |
|---|---|---|
| Instrument | NASA Task Load Index, raw (unweighted) form | Facets of System Trustworthiness (FOST) |
| Original source | Hart, S. G. & Staveland, L. E. (1988). Development of NASA-TLX (Task Load Index): Results of empirical and theoretical research. In P. A. Hancock & N. Meshkati (Eds.), *Human Mental Workload* (pp. 139–183). North-Holland. **Not opened**; cited from standard references. | Franke, T., Trantow, M., Günther, M., Krems, J. F., Zott, V. & Keinath, A. (2015). Advancing electric vehicle range displays for enhanced user experience: the relevance of trust and adaptability. *Proc. AutomotiveUI 2015*. **Verified as citation** (several citing papers); **full text not opened**. |
| Raw form | Hart, S. G. (2006). NASA-Task Load Index (NASA-TLX); 20 years later. *Proc. HFES Annual Meeting*. Reviews the raw (unweighted) use and lists early translations, including a German one. **Verified as existing** (search); **not opened**. A validation of the raw form in clinical monitoring: Said et al. (2020), *JMIR* 22(9):e19472 (**verified as citation**). | — |
| German version | A German translation evaluated in general practice (University of Lübeck record; α = 0.84, one-factor structure). **Authors and year not verified**; the record must be opened before citing. | The developers distribute a German and an English version (stated by citing papers). Copy the German items from that distribution. |
| Items used | Mental demand, temporal demand, performance, effort, frustration. Physical demand is dropped. | All five items. |
| Response format | As in the source (0–100 in steps of 5 in the usual raw form; check the German source) | As in the source (a six-point agreement scale, per citing papers; check the source) |
| When | After each of the three study cases (three times) | After the practice case, and after case 3 before the recall conversation (twice) |
| Time | about 1 minute each | about 1 minute each |

**How the ten-item limit is met.** Ten distinct items: five TLX items and five FOST items. Dropping physical demand
is a **deviation** from the instrument, disclosed in the paper with its reason (reviewing a case on screen has no
physical demand; the item would add noise and time). Scores are the mean of the five TLX items (0–100) and the FOST
mean (or sum, as the source specifies). Total time for all scales: about five minutes.

**Why FOST rather than the Trust in Automation questionnaire.** Körber, M. (2019), "Theoretical considerations and
development of a questionnaire to measure trust in automation", *Proc. IEA 2018*, Springer (**verified as
citation**; German and English versions in the author's public repository, **not opened**) has 19 items in six
subscales. It does not fit ten items without taking a subset of subscales, which breaks its validation, and its
author advises against a total score. FOST has five items, was designed for trust in information displays, which is
what CasePath's result is, and has a German version.

**Not claimed.** With five experts, no psychometric property of either scale is estimated here; values are reported
per case and per expert (unlabelled), descriptively.

## 2. Stimulated-recall guide (twenty minutes)

### 2.1 What is shown

Selection, fixed in advance and computed from the record when case 3 closes:

1. **All of the expert's own corrections, dismissals and additions** on the three cases, in the order made. If there are more than twelve, the twelve are drawn at random, stratified by reason, with a recorded seed.
2. **Three kept items** (never changed by this expert): every kept chain item that gold labels incorrect, ordered by total on-screen time (longest first), then kept correct chain items with the longest on-screen time until there are three. The kept items are mixed among the corrections and shown the same way.

**Whether the expert is told which kept items were wrong.** Not during the conversation, because it would turn the
remaining explanations into justifications. At the end the researcher says: "Some of the statements you kept were
judged incorrect by the reference. Would you like to know which?" and shows them only if the expert says yes. This
keeps the explanations unbiased and respects the expert's interest in their own work. Whether the expert asked is
recorded.

Each item is shown on the expert's own screen state as it was when they acted (from the event log): the item, its
evidence, and the before and after values. The tapped reason is **hidden** from the researcher's view and from the
expert.

### 2.2 Fixed opening (read aloud)

> "Thank you. We will now look at some places in the three cases where you did something, or left something as it
> was. There are no right or wrong answers here; we want to understand how you work, so that CasePath can be improved.
> For each place, please tell me what you were thinking at that moment. If you do not remember, say so; that is also
> useful."

### 2.3 Neutral prompts

Use only these, in this order, and no others:

1. "What were you thinking here?"
2. "What did you look at to decide?"
3. "What would have had to be different for you to decide otherwise?"
4. (only for a correction) "Where does the right information come from?"

Do not: name a reason category, say whether CasePath or the expert was right, praise, or ask "why didn't you…".
Silence of up to ten seconds is allowed before moving on.

### 2.4 What is recorded

- Audio, inside the insurer only; transcribed inside; the transcript belongs to the content export.
- Per item: `event_id` (or `item_id` for a kept item), start and end of the segment (relative time), whether the expert remembered, whether at the end they asked to see which kept items were wrong.
- No video, no screen recording beyond what the event log already holds.

### 2.5 Coding (blind)

1. A researcher who did not run the session codes each explanation with one of the six reasons (1 Steht anders in den Akten; 2 Steht nicht in den Akten; 3 Hier nicht relevant; 4 Gilt generell so; 5 Weiss ich von ausserhalb der Akten; 6 Formulierung) or "not codable", from the transcript only, without the tapped reason, the item's gold label or the expert's identity.
2. A short coding manual is written before the first session: one paragraph per reason with the remedy it points to, and a rule for ties (the reason pointing to the earliest stage of the chain: reading before checking before process condition before rule before wording).
3. Agreement with the tapped reason: Cohen's kappa with a bootstrap interval, on corrections where both exist; the confusion table; the share "ohne Angabe" among tapped reasons, and how those were coded.
4. A second coder codes a random 30 % for coder agreement (exploratory).
5. For kept items, the explanation is coded as: checked and agreed; did not check; trusted CasePath; not relevant to the task; other (exploratory).
