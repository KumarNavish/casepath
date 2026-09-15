# Fixed-core knowledge-only transfer protocol (frozen before the transfer run)

Development domains: heating_defect, termination_payment (dev + hidden). Transfer domain: rent_increase — never used for any
development decision; its 10 episodes were generated and verified before any model arm ran, and no result on them was inspected
before the freeze.

Frozen core (byte-identical between development and transfer; hashes in REPRODUCIBILITY_MANIFEST.json):
- calculus: casepath_api/evidential_channel_v1.py (levels, cap, availability rule, states, request cover, readiness)
- extraction prompt: arena_v1/runner.py CTES_SYSTEM_PROMPT; baseline prompts: arena_v1/arms.py (verbatim E76 + shape note)
- runner, environment mechanics, evaluator, scoring, primary utility, model id, temperature, token caps, request limit.
Knowledge bindings permitted (data only, no code): the transfer domain's document catalog, governing-instruction texts and
narratives inside the episodes themselves. The CTES arm consumes no domain pack: requirements, standards and document routes
are read from the episode's own instruction paragraphs by the same model call used in development. The domain-compiler control
is the only arm that reads the domain pack; it is a control, not the candidate.
Adaptation cost to report: number of changed code lines (expected 0), changed configuration (expected 0), changed prompts
(expected 0), plus the size of the knowledge binding (catalog rows and instruction sentences per episode).
Success criterion: the CTES − direct and CTES − ablation utility differences on the transfer split have the same sign as on dev
and the hearsay-readiness signature (P1/P2) holds without any change to the core.
