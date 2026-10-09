# Inactive exact-nine allowance preparation

This code prepares a proposed allowance. It does not approve either monetary
option, apply a production grant, start a workflow, or authorize inference.
The fixed input pins come from Mac document commit
`a9adbefa9988d5ca10b25f3b8b3bc0c6bc922071`; its candidate packet explicitly says
`execution_authorized=false`. Direct human approval must be obtained separately.

`casepath/tools/preflight_original_nine.py preflight` reads the exact adopted
selection bytes, resolves all nine canonical originals, extracts through the
existing reader, and constructs the same interpretation request as the model.
It performs no source admission, ledger write, credential read or HTTP request.
The operator supplies optional saved `--budget-readback` and
`--knowledge-context` JSON files. Without a complete budget projection, the
packet is explicitly not ready for a current-budget compare-and-swap. The
documented monetary readback is supplied historical evidence, never a live query.
Both CLI operations require a clean committed checkout; source sealing remains
the integration owner's separate task.

Preflight hashes and interpretation sizes describe that saved knowledge context.
Qualified knowledge can evolve without changing the approved original, sources,
rules or workflow. Its contribution can change the eventual request hash/size.
No verifier output, tokens or provider billing are predicted. Every eventual
request independently retains the 64,000-byte and 3,500-output-token bounds;
the frozen reservation prices give USD `0.009750000` per admissible maximum,
USD `0.175500000` for eighteen maxima, and USD `0.02` per workflow. An eventual
compiled verification input may exceed the byte bound and then sends nothing.

An operator can invoke the separate `apply` subcommand only after direct human
approval, supplying `--apply`, a human approval reference, actor/reason,
idempotency key, acknowledged exact preflight digest, current budget digest and
chosen option. These references are audit identities, never proof of approval.
The command rechecks committed source and extracted context before lazily using
the existing authenticated Turso remote-primary factory. It acquires the
existing hosted generation lease and applies the grant in its fenced SQLite/
Hrana transaction. There is no public endpoint, startup application, local paid
writer fallback, credential discovery, automatic provider call or retry.

The additive immutable receipt preserves the base policy, old grants, historical
external rows, and all prior autonomous workflow/intent/outcome/terminal seals.
It requires the old 24-call allowance and old three-workflow/six-call grant to be
exhausted, no active legacy work, all old workflows terminal, and no pending
provider effect. Exact same command retries return its immutable receipt;
different or reused approval identities and stale snapshots fail closed.

New records belong only to the new epoch, retaining exactly one derived workflow
for each of the nine pinned original bindings/source rosters/rules/configs and
approved stage schemas. The old three-workflow validator receives its unchanged
epoch. At most nine slots/eighteen physical calls are available. Rejection,
abandonment or unknown consumes the original slot permanently. An unknown
blocks all further inference and retains its reserve; an unacknowledged intent
cannot be resent. The historical unknown reserve remains in the old epoch.

`existing_010` keeps effective aggregate USD `0.10`, with conditional completion
and a full USD `0.02` available at each fresh start. `new_018_total_022` permits
at most USD `0.18` of new workflow reservations with effective aggregate USD
`0.22`. Base `total_cost_limit_usd=0.10` and `max_provider_calls=18` stay unchanged;
the effective ceilings and old/new counters are exposed separately. Neither
option is approved by this document or its tests.

Integration must include the separately reviewed hosted repair commit
`2c957b8` before production consideration. Older binaries fail closed once new
epoch records exist. Keep the local paid writer stopped, drain older deployed
writers, refresh the complete remote budget and qualified knowledge snapshot,
regenerate the final source seal, review preflight, and obtain separate approval
before any real application. Migration `/proc/1/maps` checks remain unverified
on Cloud; this preparation changes no migration audit.
