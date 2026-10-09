# Autonomous claim workspace

Implementation contract for the 8 October 2026 autonomous product brief. This
document describes work in progress; it is not an acceptance receipt.

The product job is to introduce an incoming claim packet once, then observe
agents investigate, construct and execute its process, acquire available
evidence, derive document obligations, and finish with a supported operational
outcome or a precise deferral. Routine handler decisions are absent from this
workflow. An operator may inspect sources or stop work without advancing it.

## State and authority

- Original synthetic corpora and existing handler journals remain immutable
  inputs to their existing paths. Incoming packets use a new operational
  namespace and immutable, hash-addressed source bytes under the local runtime.
- Accepted autonomous claim events use the existing `claim_loop_events` table
  in their own versioned namespace. The current graph, facts, obligations,
  outcomes and projections are reconstructed from that stream. Agent proposals
  and provider receipts remain separate from accepted claim changes.
- Use `causal_process_v1` as the sole graph evaluator. Document associations are
  compiled from persisted evidence obligations, rather than generated in a
  separate checklist. Every obligation links its process node, required facts,
  accepted rule references, document type and available acquisition capability.
- Machine validation is explicitly attributed and includes proposal, independent
  verifier and deterministic-check receipts. It never masquerades as a handler
  correction or human approval. Unknown and contradicted facts stay unresolved.
- The initial verified rule scope is the existing three Swiss tenancy families.
  Other categories, unsupported files, unavailable evidence and unconfigured
  external actions produce named deferrals. This scope is extensible through
  admitted, versioned rule packs; a model cannot grant itself a new capability.
- Local source acquisition, graph progression, document preparation and knowledge
  qualification are authorized operations. Settlement, legal adjudication and
  outbound customer communication have no configured execution capability.

## Execution

The intake endpoint accepts a message and bounded supporting files, publishes
source receipts, appends intake, and starts one durable job. A source arrival
resumes affected deferred work automatically. Same-key retries return the same
intake or action; stale parents and different input under one key are rejected.

The controller retrieves applicable rules and qualified knowledge, reads the
actual source packet, obtains a bounded typed interpretation, and independently
checks it. Deterministic gates verify exact source spans, rule identities, graph
references, acyclicity, obligations, action capability and current revision.
Verified changes are committed before the browser can present them as accepted.
It then executes available local actions, checks their actual results and repeats
only when new evidence or a changed dependency justifies another step.

Provider request intents and conservative cost reservations precede HTTP. Typed
results are persisted before application. Restart reuses a completed result and
idempotent action receipt; unknown requests are never resent automatically.
The persistent base allowance is 18 requests under a USD 0.10 aggregate ceiling,
including prior usage and unknown-cost reserves. A sealed autonomous-mode activation preserves
the original policy and adds no per-run allowance. A workflow reserves at most
USD 0.02 for two independent semantic calls. Request bodies are limited to
64,000 bytes and outputs to 3,500 tokens. Expired catalogue metadata blocks new
requests after 24 hours while saved results remain replayable. Routine mechanics
do not require inference. Cost reservations use the highest applicable input or
cache rate. Supported models use low reasoning effort within the same output
limit; only the typed public result is retained.

The explicit local `run_agent_demo.py --autonomous` profile requires a clean
committed source capsule, a matching normal boot, fresh model and endpoint
snapshots and the existing private credential loader. Its readiness check binds
the autonomous model and sealed shared-budget activation. Normal deterministic
mode saves incoming evidence and reports inference unavailable; it does not
substitute fixture responses. Enabling the configured profile can resume those
unprocessed intakes. Startup may also finish saved deterministic knowledge work.

For the existing prepared checkout, launch the configured model from the
repository root after sealing and a matching normal boot:

```bash
.runtime/casepath-dev-v2/venv/bin/python casepath/tools/run_agent_demo.py --autonomous --model openai/gpt-6-luna --catalogue .runtime/casepath-openrouter-demo/catalogue.json --endpoints .runtime/casepath-openrouter-demo/endpoints-gpt-6-luna.json
```

These are local catalogue and endpoint snapshots, not credentials. They must
still pass the freshness and identity checks; their filenames do not establish
that they are current. A new checkout should follow
[demo setup](../setup-demo.md#configure-the-local-inputs) for snapshot acquisition and private Keychain
configuration. No secret belongs in this command or a checked-in packet.

Each workflow freezes its source/rule identity and semantic context, including
the compatible knowledge versions available at admission. Restart therefore
cannot silently change the meaning of a paid request. Pause preserves a saved
interpretation and its unsent verifier allowance; resume can replay it. New
evidence supersedes the old workflow, releases only unsent work, and retains all
completed or uncertain provider charges.

When the base allowance cannot admit another two-call workflow, the stopped local profile can record
one explicit allowance for three further autonomous workflows and at most six
calls. The USD 0.10 aggregate and USD 0.02 workflow ceilings still apply. The
grant requires an exact current budget hash, an actor, a reason and an
idempotency key, with no active workflow and at least USD 0.06 remaining after
existing charges and reservations. This occurs at 17 or 18 used calls; a failed
single-call workflow does not strand the remaining allowance. The separate
`run_agent_demo.py --grant-three-autonomous-workflows` command records the
allowance and starts no inference. New submitted workflows consume its slots;
failed workflows consume a slot too. Existing usage, uncertain charges and
failed claims stay in the ledger. The legacy review allowance is separate.

## Knowledge

Knowledge is organized by category, process, facts, obligations and authority.
Candidates carry source provenance, proposer/verifier receipts and a causal
regression receipt. Claim-specific values, source files and completion states
must never become reusable defaults. Qualified versions are immutable; a later
candidate cannot overwrite an established version silently. Rejected candidates
remain inspectable. Each reuse records the exact version and an applicability
check against the receiving claim. Improvement is reported from observed reuse
and avoided repeated work, not inferred decision accuracy.

The current reusable ID is stable per family: `procedure.<family>`. A qualified
definition may add an evidence-reading recipe only from an independently
verified sufficient supporting file, exact required-field roster and admitted
rule reference. Canonical procedure text enters the reusable definition; case
names, values, citations and proposed narrative remain provenance. New versions
carry `parent_definition_sha256`, `parent_knowledge_sha256`, `change_reason` and
`added_document_types`. An unchanged definition produces no new version. Reuse
records the exact version and `reused_evidence_recipes`; these counts describe
actual stored work avoided, not better legal decisions.

For newly admitted workflows, a versioned compiler adds any omitted recipe
candidate from the interpreter's explicit assessment of a complete original as
sufficient. It copies the admitted field roster and source citations, then sends
the candidate to independent verification. Compilation grants no acceptance;
both the document and recipe must still pass their evidence checks. The saved
receipt binds the untouched model proposal, compiled proposal and derived items.
Historical contexts retain their original request and validation semantics.

[Three public fictional packets](autonomous-demo/README.md) are available for a
qualification, refinement and reuse demonstration through native or API intake.
They are prepared inputs with conditional checks, not precomputed answers or
evidence of a real-provider pass.

## Experience and verification

The working surface is the live process with its derived documents and a quiet
current-action line. Source, required fact, obligation and action are inspectable
at the selected node. Motion follows persisted events and causal changes only;
completed work is labelled as recorded. Reduced motion retains all information.
No private model reasoning transcript is displayed; short cited decision
summaries explain accepted actions and uncertainty.

Acceptance requires three newly introduced packets through the real backend, an
evidence-driven branch/checklist change, actual supporting-file acquisition,
autonomous progression to completion or justified deferral, qualified knowledge
publication, refinement and reuse on later claims, and saved-state agreement after restart.
Also test stale and duplicate requests, source tampering, cross-claim citations,
contradictions, unsupported extraction, invalid knowledge, provider failures,
unknown effects and capability boundaries. Inspect actual events and source
bytes, not only green checks. Browser acceptance covers desktop, tablet and
mobile, keyboard operation, reduced motion and purposeful live transitions.
