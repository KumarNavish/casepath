# Title

Does the Benchmark Require the Input? Falsification Audits for Structured Agent Evaluation

# Abstract

Structured agents are often evaluated with metrics interpreted as evidence that they use an explicit representation to respond to the current instance. We ask a prior question: does the benchmark require the input at all? We operationalize three falsification tests: a scenario-cross-fitted input-independent oracle, a permutation that reassigns outputs to the wrong inputs, and evaluator-independence checks. For a set-retraction metric we also derive the optimal fixed withdrawal policy in closed form under a volume-matched chance correction. On two independently constructed source-grounded legal workflow scopes, the static task has one observed gold checklist and a case-ignoring F1 of 1.000. A paired intervention task designed specifically to escape that degeneracy fails again: cross-fitted constant policies obtain excess withdrawal recall of +0.447 and +0.752, versus +0.118 and +0.018 for the strongest measured agents. Within-scenario output–label permutations leave the apparent leading behavior ordinary or invariant. A preregistered robustness study with three non-OpenAI evaluator families (522 calls) shows that changing the evaluator does not rescue the benchmark: Claude Opus 5 reproduces all 58 reference document sets and all 28 paired release sets exactly, and a family-balanced consensus agrees exactly on every complete common pair. The conclusion is therefore not that one agent fails, but that these evaluations do not identify case-conditioned competence. We release the falsification audit and the full negative record as a reproducible benchmark-validity test.

# Suggested subject area

General machine learning / evaluation and benchmarking / language models and agents.

# Administrative blocker

The exact author list and OpenReview profiles must be confirmed by the human authors before the Sep 18, 2026 abstract deadline; they are intentionally not inferred here.
