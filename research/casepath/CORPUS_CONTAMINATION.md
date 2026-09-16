# The case bucket was contaminated, and the corpus is larger and better structured than it looked

Found while checking why some branch interventions produced implausibly large cascades.

## The contamination

`clm_393285577dcb12c4` cascaded from a single added sentence to eight settled decisions. Reading it explained
why: its subject is *"per E-Mail erklärte Kündigung mit fehlendem amtlichem Formular"* — an **email termination**
without the official form. It is not a rent-increase case at all.

Auditing the working bucket of 15 found **5 termination cases (33%)**. The bucket had been built by keyword match,
and Swiss tenancy termination and rent increase share the phrase *amtliches Formular* — both require a
cantonally approved form, one under OR 266l, the other under OR 269d. The keyword could not tell them apart.

## What the contamination was doing to the numbers

It inflated the appearance of uniformity. Asked to evaluate a termination narrative against a rent-increase
contract, adjudicators correctly answer `unknown` almost everywhere, because the contract's decisions are about a
rent increase and the case has none. `unknown` keeps a decision open, so an out-of-scope case produces the *full*
document list — the same modal ten that in-scope cases produce. Four of the five contaminated cases landed exactly
there.

So the saturation measurement was partly an artifact of its own bucket: a third of the sample was being scored
against a contract that did not describe it, and was scoring as the majority. The saturation finding has to be
re-measured on clean cases before it can be reported.

## What the corpus actually contains

`static_template_sha256` is identical across all 150 claims — it identifies the hand-authored static rule
template, not the scenario, and is useless as a grouping key. The scenario is the part of the subject after the
colon, and it is generated in German and English twins.

Grouping on the raw subject would have split scenarios across the evaluation: *"formell zweifelhafte
Mietzinserhöhung"* and *"formally questionable rent increase"* are the same generated scenario in two languages.
Assigning them independently would have put a scenario's German cases in development and its English twins in the
held-out set — a leak that a family-paired bootstrap is specifically meant to prevent, introduced by the family
key itself.

Merged on scenario rather than subject, the rent-increase portion is:

| | |
|---|---|
| scenarios | **10** |
| cases per scenario | **5** (exactly, all ten) |
| total clean cases | **50** |
| contaminated cases removed | 5 |
| in-scope cases previously missed | 40 |

The working bucket held 10 of these 50. The experiment had been running on a fifth of the available data, a third
of which was the wrong domain.

## The frozen split

`splits/rent_increase_scenario_split.json`, frozen before any confirmatory case was read.

- **Development — 4 scenarios, 20 cases.** S1 form defective, S2 form without reason, S3 retroactive start are
  burned to development because cases from them have already been run and read. S10 grant allocation joins them,
  chosen by sha256 of the scenario identifier rather than by anything about its content.
- **Confirmatory — 6 scenarios, 30 cases.** S4 miscalculated, S5 reference-rate inconsistent, S6 reference-rate
  double-counted, S7 renovation unclear, S8 ancillary-charge reclassification, S9 provisional budget. Unread, and
  to be read once, after the method is frozen.

Scenario is the resampling unit for every interval reported. Five cases of one scenario are five variations on one
fact pattern, not five independent observations, and treating them as independent would shrink every confidence
interval by roughly the square root of five for no reason but the corpus generator's choices.
