# Data card

## What this is

A synthetic benchmark of multi-turn evidence acquisition for insurance-style claim handling. Each episode
gives an agent a customer's account, a catalogue of documents that might be obtained, governing handling
instructions, and, across three turns, whatever documents actually come back. The agent must hold a correct
state for every catalogue document, request at most two per turn, and decide when the case may proceed.

It is **not** a dataset of real claims. No real person, claim, document or insurer appears in it.

## How an episode is built

Latent-first, in four stages, so that the gold labels never depend on the wording.

1. **Latent specification.** A seeded sampler fixes, per episode: which documents exist, which are
   obtainable and when, which requirement each satisfies, whether a conditional requirement is live, the
   language, and a set of *motifs* — the epistemic situations under test, such as a customer reporting they
   hold a document, quoting its contents from memory, relaying what a third party said, or a party
   promising delivery.
2. **Paragraph brief.** The latent is turned into a semantic brief: for each paragraph, what it must
   convey and what it must not. The brief carries no evaluator labels and no document identifiers.
3. **Rendering.** A writer model turns each brief into prose. The writer sees the brief, never the gold.
4. **Assembly and validation.** The prose is reattached to the latent. Gold comes from the latent and from
   which documents were actually returned — never from the text.

Because of this order, a writer can make an episode better or worse *written* without changing what the
correct answer is.

## Splits

| split | families | episodes | purpose | read |
|---|---|---|---|---|
| development | 20 | 46 | building the method; read many times | many |
| confirmatory | 41 | 82 | first pre-registered endpoint | once |
| decisive | 21 | 42 | pre-registered state accuracy | once |
| writer-swap | 21 | 42 | the decisive latents, rewritten by a second writer | once |
| submission | 30 | 60 | actor-model generalization and the obvious-fix comparison | once per actor |

Families never overlap between splits. A *family* is a scenario theme within a domain; episodes within a
family share the theme and differ in latent draw, so family is the unit of statistical analysis
throughout. The three domains are a heating defect in a rented flat, a lease termination with disputed
payment timing, and a rent increase.

**Terminology is used exactly.** No split is called hidden. The development split was inspected repeatedly
and is labelled as such. Every other split states how many times it was read.

## Writer models

| split | writer |
|---|---|
| development, confirmatory | Claude models in-session, then `openai/gpt-5.4-mini` |
| decisive | `openai/gpt-5.4-mini` |
| writer-swap | `anthropic/claude-sonnet-5`, identical latents |
| submission | both, assigned per family by seed before any actor ran |

On the submission split the writer is deliberately decoupled from the actor: every actor model sees the
same fifteen-and-fifteen mixture, and writer is carried in the analysis as a nuisance variable.

## Known benchmark artifacts, stated plainly

- **Episode-verifier disagreement.** Two independent verifier families check each episode against the
  decisive semantic properties. They agree on almost nothing outside the motif rule — Jaccard 0.14 there,
  0.00 on return scopes. Only the motif rule carries cross-verifier signal, and only it is used.
- **Residual motif violations.** About 0.31 per episode by the verifier that flags them, similar across
  writers (0.333 for the cheap writer, 0.310 for the expensive one on identical latents). Episodes were not
  removed for this; the rate is reported instead.
- **Constraint verbalisation.** In roughly one episode in ten the prose states the hearsay condition
  explicitly ("from memory…"). This makes provenance easier for content-reading arms and therefore biases
  against the proposed method.
- **Three turns, two requests.** A short horizon makes "request everything" nearly free under any
  acquisition-weighted score. This is a property of the harness and is why such an arm is included as a
  control and why the composite utility was abandoned.
- **One language pair.** English and Swiss Standard German only.

## Leakage controls

Every split passes a shortcut audit before any model arm runs: five zero-model controls (random, a static
checklist, a constant policy, a keyword router, and a domain compiler that knows the requirement routes but
reads nothing) must all fall below a fixed utility and turn-0 state-accuracy threshold. A split that a
model-free policy could solve is rejected. Returned-document identifiers are opaque hashes, and per-episode
intake attachments vary turn-0 state within a family so family membership alone predicts little.

## Excluded

Real claim text; personal data; any document not generated for this benchmark; any episode hand-edited
after its gold was fixed.

## Licence and cost

See `LICENSES.md`. Generating and verifying every episode in every split cost under twelve dollars of model
time in total; the figure per split is in `COST_ACCOUNTING_FINAL.json`.
