# Obligation-control increment — construction, not experiment

## Apply scope

Apply only to `/Users/kumar0002/Documents/Die Mobiliar/casepath-obligation-control`,
branch `codex/obligation-control-20260919`, based on
`819679f972733bd63a1278284436ac8b457207ce`. All implementation files are new and
namespaced. Do not modify the frozen theft predecessor, original evaluator,
protected data, authority journals, or existing app routes. No dependency installation.
The old checkout and fresh standalone checkout are distinct: this is a prospective
module addition, not a claim that standalone main already implemented V5.

## Implemented interfaces

| Module | Interface | Meaning |
|---|---|---|
| `obligation_control_v1` | `Graph.parse(obj, registry)`; `evaluate(observations)`; `evaluate_compiled(observations)` | Validated explicit applicability DAG, strong three-valued state, and ordinary flattened-formula control |
| `evidence_demand_v1` | `capabilities(rows, registry)`; `evidence_state(obj, caps, refs)`; `plan(graph, caps, observations, evidence)` | Capability-specific alternative discharge, active/acquisition eligibility, evidence review, requests and separate action readiness |
| `native150_export_v1` | `export(graph, caps, plan, evidence, binding, registry, case_id)` | Deterministic native artifact serialization without target access |
| `source_only_runtime_v1` | `SourceOnlyRuntime.load(path, expected_manifest_sha256)`; `run(case, execution_mode='graph'|'compiled')`; `cost_bound(config)` | Source-only pack loading, pure read-only plan/export, and exact proposed reservation arithmetic |

No model function exists in these modules. Guard and adequacy assessments are
explicit upstream inputs. `origin=model_execution` requires a receipt identity,
which is recorded, not authenticated by these modules. Gateway collection must
verify the actual receipt. No schema or hash check certifies semantic correctness.

### Control JSON

`Graph.parse` accepts exactly `contract`, `variables`, `scopes`, `obligations`,
`actions`. See the complete executable example in `fixture()` in the test file.

* Expressions are exactly `{"const": bool}`, `{"var": name}`, `{"not": expr}`,
  `{"all": [expr, ...]}`, or `{"any": [expr, ...]}`. Empty AND/OR lists are invalid;
  use explicit constants. Integers and strings are not Boolean observations.
* A scope is `{scope_id, when, parents, join, source_refs, display_parent?}`.
  `parents` express applicability dependencies ONLY. All roots declare `join=all`.
  Nonroots declare AND or OR explicitly. Cycles, unknown parents and ambiguous
  joins fail. Display parents cannot affect any obligation or request.
* An obligation is `{obligation_id, scope_id, when, acquire_when, capability_ids,
  source_refs}`. Applicability is scope AND local condition. Acquisition is a
  separate explicit source restriction, never an inferred action-order restriction.
* An action is `{action_id, scope_id, prerequisites, obligation_ids, source_refs}`.
  Its prerequisite state does not gate evidence acquisition. An applicable
  obligation must be satisfied for that action to become ready. An unresolved
  obligation prevents unconditional readiness. An inactive obligation is not due.
* Scope/obligation/action IDs are globally unique. Node count <=256, variable/list
  count <=512, expression depth <=24 and source expression nodes <=256. Expansion
  beyond 65,536 characters fails explicitly. Cyclic processes and unmodelled
  exclusive semantics require a future explicit contract, not implicit assumptions.

### Evidence JSON

A capability is `{capability_id, fact_id, fact_statement, must_show, routes,
source_refs}`. A route is `{route_id, document_ids, source_refs}`. Documents within
one route are jointly required; routes for one capability are alternatives.
Distinct required capabilities remain conjunctive obligations. Empty route lists
are explicit evidence gaps; an empty route is invalid.

Evidence contains `documents`, `slot_assessments`, `joint_assessments`:

* Document observation: `{presence: missing|present|unknown, native_state,
  source_refs}`. Presence is not proof. A decided presence requires an observable
  provenance reference; absent entries remain unknown, not missing.
* Slot assessment: `{capability_id, route_id, document_id, adequate: bool|null,
  source_refs}`. Adequacy is relative to that document's role in that proof route.
* Joint assessment: `{capability_id, route_id, adequate: bool|null, source_refs}`.
  Multi-document completion additionally requires this joint assessment. Combining
  separately plausible documents is not automatically joint proof.
* One adequate route discharges that capability and suppresses redundant alternatives.
  Present-but-unassessed evidence causes review, not a new assertion of sufficiency.
* Deterministic route policy: minimize number of new requests, then unresolved reviews,
  then lexical document/route order, separately for each capability. This is NOT a
  globally minimum-document optimizer. No global optimality claim is permitted.
* Unknown applicability creates a question/conditional plan, not immediate requests.
  Unknown acquisition does not authorize a request. Every immediate request carries
  scope, obligation, fact, capability, route, document and source-reference identities.

### Native export mapping

The preparation producer supplies actual control concepts/relations, symbolic branch
predicates, document bindings, terminal IDs and `decision_by_obligation`. The exporter
may not create missing control nodes, turn steps into decisions, infer a native label
from a target, or convert observed true/false values into constant branch formulas.

Control concepts map to `process_step`, `decision`, or `outcome`; actual capabilities
supply fact/evidence concepts. Actual obligations generate `requires_fact`;
capabilities generate `supported_by`; route members generate `satisfied_by` ending
at document item IDs. Repeated edge triples are consolidated with an OR of their
actual activation expressions, not duplicated under new edge IDs.

`request_mode=now` is EXACTLY the runtime's emitted request set; `conditional` is its
conditional set; remaining documents use `none`. `active_when` remains symbolic.
Native document state is the upstream recorded assessment, not inferred from gold or
request membership. Unknown stays unknown. Contradictory `provided_sufficient` or
`irrelevant` state on an emitted request rejects export. Exact locators are copied
from the source registry. No confidence is invented; the native schema's default
must not become a calibration claim. Terminal IDs must already name outcomes.

This is a concrete native export component. It is not proof that an actual learned
source-preparation producer already supplies all required native bindings.
The native artifact is a projection: its flat relations do not encode proof-route
grouping or joint-adequacy assessments. Preserve the complete planning output
alongside it for those semantics and their audit; do not claim lossless export of
the entire runtime state.

### Source-only loader

Only four payloads: `control.json`, `capabilities.json`, `native_binding.json`,
`source_registry.json`. Manifest identities and roles are checked before payload
access. Unknown roles/paths, traversal, symlinks, changed bytes and duplicate JSON
keys fail. A source record is `{locator, text}`; quote checks are against that
record's passage, not some other source. Registry/pack integrity does not establish
entailment or prevent an authorized producer from misclassifying content. The
model/evaluator vault separation remains the governing boundary.

No BENCHMARK, PREPARED theft pack, HIDDEN_RESULT, DEMO_CASE or old predictions are
accepted loader roles. No endpoint mutates original claim authority. The same
`SourceOnlyRuntime.run` is the intended core for a later source-bound read-only
product adapter and admitted experiment runner. This increment does not claim
six-role integration or fresh provider-backed product parity.

## Focused verification

Run in the worktree with the existing Python environment; do not install packages:

```sh
export PYTHONPATH="$PWD/casepath-api${PYTHONPATH:+:$PYTHONPATH}"
export CASEPATH_NATIVE_SCHEMA_DIR='/Users/kumar0002/Documents/Die Mobiliar/casepath-iclr-eval/casepath-eval/.work/casepath-bench-v3-public-current-20260821l/contracts'
python3 -B -m unittest discover -s casepath-api/tests -p test_obligation_control_increment.py -v
python3 -B -m casepath_api.obligation_control.source_only_runtime_v1 \
  --cost-config research/casepath/obligation-control/COMPARISON.proposed.json
```

The native-schema test loads only the unmodified schema and its expression parser,
not `contracts/__init__.py`, targets or a scorer. If native dependencies are unavailable,
report the exact failure; do not substitute a mocked schema. The other mechanics use
only the standard library. Fixtures are invented, not any of the 150 claims.

## Construction outcome and next allowed operation

The increment should produce newly hashed source and an executor receipt for these
focused tests on the named worktree. It does not enable learned execution. Continue
collecting the existing gateway metadata worker; never duplicate its submission.
Canonical preflight/experiment registration, frozen validation, numeric authority,
real preparation/adapters and protected access history remain required before inference.
No generator, historical benchmark run, provider transport or paid canary may be run
as a consequence of applying this patch.

The preserved kernel remains an explicit unbound comparator. Its missing source
must not be replaced with this increment and called a reproduction.
