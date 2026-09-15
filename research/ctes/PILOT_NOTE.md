# Dev pilot (preserved diagnostic, superseded)

A first dev run of the 24-episode arena was executed and then stopped after turn 1 because it exposed an
implementation defect in the CTES extraction parser, not a scientific result. In 5 of 24 episodes the model
named a document id outside the catalogue inside one conditional requirement's satisfying set
(`allocation_statement` / `mixed_demand_allocation` in the termination_payment domain, whose acceptable record
is in fact the manager ledger already in the catalogue). The parser rejected the whole extraction, which killed
those trajectories for both the CTES arm and its ablation.

Repair (development-time, before the freeze, applied identically to the candidate and its ablation):
unknown document ids are filtered out of each satisfying option; options that become empty are dropped; a
requirement left with no option is retained as **unsatisfiable** — it can never be satisfied, never contributes a
request, and permanently blocks readiness. This is the conservative direction: it can only reduce the candidate's
acquired evidence and can never produce a premature readiness. Dropped ids are recorded per call.

Pilot cost: 99 physical calls, USD 9.1285. Pilot state retained in state.json / log.txt.
Turn-0 signature already visible in the pilot: hearsay receipts direct 3, process-only 2, full 2, CTES 0.
