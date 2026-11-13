# Direction for the rebuild (from Navish to the paper session, 2026-11-13)

Kept verbatim in substance; this is the binding brief for everything under `rebuild/`.

The 29-page draft is careful and unreadable. It reports a test; it does not show a mechanism, a superior system or a
useful one. Rebuild the paper around pictures and around evidence that is still missing. Do not edit the draft into
shape; start from the storyboard below.

## The standard
- The graphics do the explaining; the writing is minimal, natural and precise. North stars:
  https://openai.com/index/ai-effect-on-freelance-work/ for clarity and
  https://www.anthropic.com/institute/econ-scenarios for the cinematic flow.
- Figures at the level of https://kumarnavish.github.io/MechanismFigures/assets/gallery.html. Use the
  mechanism-figures method: before drawing, write "The reader should see that ___ because ___"; draw two different
  constructions; keep the one that is truer.
- Lead with discoveries, not metrics. Humble, honest language, which does not mean repeated caveats.

## The thesis, in one sentence
Models read and quote; code decides; what the file leaves open becomes a held request with one question. Everything in
the paper serves this sentence or goes to the supplement.

## Three research questions
1. What happens to a fact the file leaves open, in CasePath and in a prompt?
2. Does CasePath beat the strongest prompt as cases get real: longer files, more rules, more open facts?
3. What does an organisation gain when its rules change, or when it adds a new kind of claim?

## The storyboard: seven figures carry the paper
1. One changed sentence. Two claims, one sentence apart. One line of the checklist turns from request to hold with a
   question; nothing else moves.
2. The journey of one sentence. Quoted words, three readings, admission, the fact's value, the workflow lighting up,
   the checklist. One line across the figure: above it models read, below it code decides.
3. Why "open" needs its own value. The branch-and-rejoin picture, simplified.
4. The fate of 100 open facts. Where each design sends them: held, requested too early, or dropped.
5. As cases get real. Error against file length, number of rules and share of open facts, as small multiples.
6. A rule changes. One edited line, the graph before and after, every stored checklist recomputed with no model call.
   Beside it, what a prompt must do.
7. The price. Error against cost, and the same file run ten times.

Rules for every figure: one claim each, readable without the text. One subtle, distinct palette; no grey, no pink; the
same colour for the same state everywhere. Almost no text inside; a legend that tells at a glance what is what; every
arrow and thickness defined. No panel without its partner.

## Earn the superiority; the draft does not have it yet
A prompt told the hold rules ties CasePath on tenancy and beats it on claims that deny their defining event. The test
files are 77 to 320 words, where a prompt is at its best. The full product costs 20 to 42 times a prompt. Fix the
artefact, then test again.
- Fix first, on development data: the reading of denied events; cost, by reading again only where the first reading
  does not settle a deciding fact; the two over-broad rule conditions.
- Then one registered test (Study 4) on fresh sealed files from the public-rule benchmark, which today supports no
  comparison at all: three regimes, both models; files from short to long with several attachments; rule sets from
  small to large; open-fact share from none to half.
- Baselines at full strength: the prompt that may hold, self-consistency at the same budget, the model executing the
  rules, ReAct. All get the same corrected rules.
- Measures: all deviations, so that needless holds count as errors; agreement across repeated runs; cost.
- Two experiments only CasePath can win, if the mechanism is real. Rule change: apply a set of rule edits; measure
  exact changes, collateral changes and model calls per design. New regime: a fresh session adds a fourth regime from
  public text by the six steps; report effort and its sealed result.
- Integrity: never manufacture evidence. No cell is hidden. If a cell is still lost after honest work, the main table
  shows it and one sentence says why.
- No dependence on the Hackathon dossiers or the expert study anywhere.

## Show what the system is (one figure or listing each, no more)
A workflow is a data file, and a new rule is one line; routing between workflows; files with several attachments and
scans; presumptions; Knowledge from handler corrections, replayed without a model. For product frames on synthetic
cases, ask the product session.

## Writing
At most 18 pages before references, three tables, ASD-STE100 language. Abstract: 150 words, the thesis, the mechanism,
the result, no p-values, no caveat. Introduction: motivation, the three questions, contributions as a numbered list.
Related work by contrast: what was done, what is new here. One number per paragraph at most; the rest live in figures
and tables. Out of the main text: the commit timeline, Studies 1 and 2, dagger marks, "registered" tags in prose, the
deviations list. One "Scope" paragraph of five lines replaces the twelve bullets. The supplement is organised for
insight, not a dumping ground.

## Gates: do not write before these
1. Send, before any run or prose: a one-page claim sheet (thesis, questions, each claim with the evidence that exists
   or must be produced); the seven figures as real drafts, with their "should see that" sentences; a costed plan for
   the fixes and Study 4, in credits. Wait for the answer.
2. Cold-reader test: give a fresh session only the figures and captions. It must state the thesis, the mechanism and
   the main result. If it cannot, redraw.
3. Then write. Before sending the paper, check every sentence against "does this earn its place".
