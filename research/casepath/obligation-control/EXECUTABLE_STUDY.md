# Native-150 execution increment — construction only

This document preserves the original V1 construction contract. Its generated
source preparation, 12,000-token ceiling and additive price calculation are
superseded by [the compact V3 contract](COMPACT_CREDIT_CONTRACT_V3.md). Use
`COMPACT_CREDIT_CONFIG_V3.json` for the current prospective comparison; neither
version grants scientific admission or permission to send a provider request.

This increment adds source-only preparation, real model adapters, a shared product
entry point, the complete request DAG, and a durable study reservation journal.
It does not grant admission, spend credits, read target bodies, or run an evaluator.
The earlier $4,164.40 proposal is outside the user's constraint and is NOT approved.
No purchase, top-up, fallback provider, or new paid resource is permitted.

## Commands that are executable now (zero provider)

From the standalone checkout, with the original schema/parser directory available:

```sh
PYTHONPATH=casepath-api CASEPATH_NATIVE_SCHEMA_DIR="$NATIVE_ROOT/contracts" \
  python -m unittest discover -s casepath-api/tests -p 'test_obligation*.py' -v

PYTHONPATH=casepath-api python -m casepath_api.obligation_control.study_v1 \
  write-config --output /absolute/new/STUDY.json

PYTHONPATH=casepath-api python -m casepath_api.obligation_control.study_v1 render \
  --release-root "$NATIVE_ROOT" --config /absolute/new/STUDY.json \
  --output /absolute/new/RENDER
```

`render` writes the complete 150-case / five-learned-arm / two-deterministic-row
matrix, all request templates, the source input, observable projections, identities,
and the total reservation. Exit 3 means the complete reservation exceeds even the
observed $236.81 upper bound. It is NOT permission to spend until the balance runs
out. The full study must be reserved before the first preparation request.

The default projector pin is pypdf 6.10.0, taken from the original frozen reading
contract. The new request view is explicitly not byte-identical to the old model
projection. It preserves all customer text, extracts every PDF page as text, and
keeps JPEGs opaque as in the native text-only track. No text is silently truncated.
Every arm receives the same view and every source-registry entry. A local rendering
with another installed pypdf version must name that version explicitly, receive a
new request identity, and must not be represented as the legacy projection. Do not
install or falsify a version to make a check pass. Neither text extraction nor an
opaque-image record is a claim of complete visual interpretation.

The producer first verifies the exact frozen public manifest and its cohort roster.
Each observable claim, source registry and shared source file is checked against
that manifest before its verified bytes are projected. The resulting input hashes
are retained in the projection receipt and source identity. This check opens no
gold, target or evaluator files; a manifest ID copied into a configuration alone
does not establish release identity.

## What is and is not frozen before generation

One request has an exact initial payload. The other 1,501 requests are bounded
DAG templates because preparation and prior-stage model outputs do not yet exist.
Logical slot identities are fixed. Physical request IDs additionally bind exact
parent-output hashes and the final payload. No placeholder is sent to a provider.
The byte-bound estimator does NOT divide characters by four or assume a tokenizer.
It reserves one token per UTF-8 byte plus a protocol-overhead allowance. This is a
conservative text-byte estimate, not an observed model token count; a canonical
provider/tokenizer bound attestation is still required before a live run. A fully
rendered request that exceeds its reserved input bound fails before sending. Parent
outputs exceeding their declared byte limit are retained as failures, never trimmed.

## Changed prospective inference design

The new control adapter jointly assesses all primitive facts and evidence adequacy
within ONE case, followed by a full review. It then calls the supplied
SourceOnlyRuntime and preserves its full planning object plus native projection.
This is NOT V5's per-guard interpretation and is NOT a measured successor yet.
The change is explicit in the method/configuration identity and requires review.

Four serious independently implemented alternatives receive the identical sources,
claim view, prepared representation, model, two calls and 12,000-output-token caps:
direct reviewed, document-first reviewed, process-context reviewed, and rule-first
reviewed. None is represented as an exact ExIde or old prompt-bundle reproduction.
Order is position-balanced across the five arms separately in each split; it is
not labelled the legacy six-arm Williams schedule. Models never receive scheduling
family/domain/split metadata or a prior case. All original source/template semantics
remain visible; stable short references merely expand back to exact source locators.

The preserved kernel source is still unavailable. Before any outcomes, it is
explicitly excluded as unreproduced, with its known relative path, partial hash and
A2 receipt retained. The independently implemented Rule-First and compiled-equivalent
rows are NOT silently called that preserved baseline. No claim of beating the
missing preserved implementation is possible.

COMPILED_EQUIVALENT and LOCAL_SCOPE_ABLATION share the NEW control assessment,
not historical predictions. The latter removes inherited applicability only, while
keeping local guards, acquisition conditions, adequacy and route handling. It is
not named V5. Equality of graph and compiled execution is expected and establishes
no novelty. The original V5 remains an immutable historical predecessor.

## Source-only preparation

Two source-only calls construct and audit the four payloads consumed by the existing
core, plus variable meanings and complete source-accounting records. Inputs include
all three public templates and normative source passages, never claim inputs, gold,
selected paths, historical predictions or answer-bearing demo packs. The source-only
loader and all native output types are exercised against the original schema/parser.
Model-produced source accounting is a checked declaration, not proof of entailment.

## Real inference / product integration

`StudyRunner` uses `BoundExecutor` for preparation and every learned arm. The control
adapter then invokes the existing SourceOnlyRuntime, not a surrogate planner.
`ProductPlanService` and `create_router` call the same `run_cell` implementation.
The existing app can explicitly mount this router with a server-owned service factory;
no network, preparation or configuration occurs on import. There is no change to
claim-authority journals, existing start/ensure gates or evidence admission, and no
fabricated six-role receipt. This is a planning-service integration, not a completed
six-role product release.

The native artifact is a PROJECTION. Full route alternatives, joint adequacy,
observations, state and planning objects remain in immutable cell records. Valid
candidate rows use the original `case_id` + `candidate` JSONL interface. Failed and
missing cells remain explicit sidecars and must receive the original failure-policy
scores in the original evaluator. Scoring only the successful JSONL is a complete-case
sensitivity analysis and cannot become the whole-population result. This package
never imports scorers or opens target files. Engineering fixture submissions are
written to a different directory and cannot be labelled model results.

## Required external admission boundary

There is intentionally NO `--run-paid` or local command that creates authority.
After canonical prospective review/validation/admission, a managed Linux gateway
worker may instantiate BoundExecutor with the existing canonical authorization
checker and OpenRouterOnce with the gateway's existing secret supplier. The callback
is a trusted deployment boundary, not a JSON flag or this package's own validator.
It must verify exact owner, experiment, run/command/code, phase, protected-target
history, effective parameter/price bindings and shared-account credits. It must
return a per-request authorization bound to plan, request and payload identities.
Unbound callbacks, synthetic receipts and a schema PASS are not admission.

Journal.reserve requires that externally verified admission plus a specific
existing-credit allocation, a fresh balance, all outside liabilities, and parameter
and token-bound attestations. It reserves the ENTIRE rendered schedule, including
preparation. It cannot reserve a partial comparison. Multiple reservations in the
shared journal cannot exceed available credit. Canonical account coordination remains
necessary for jobs outside this journal; an absent local record proves nothing.
Unknown charges retain their reservation and block further sends. No top-up is made.
Prices include all three reported input/cache rates additively, conservatively. There
are no tools, web search, redirects, automatic retries or automatic model fallback.
The standard route/model must match. A lower cost can only follow a prospectively
reviewed tighter request/token/price binding, not an edited cheap quote.

## Execution / recovery

A production worker MUST explicitly select `run_all(split='public_dev')` or
`run_all(split='hidden_test')`. It does not automatically proceed from development
to protected execution. The protected phase requires the collected development
phase for the exact same plan and canonical protected-freeze/access-history receipts.
No development-driven change is silently applied to that plan; a change needs a new
identity and review. Preserve already consumed confirmation identities.

`BoundExecutor.recover` reads an exactly completed, journaled request; it sends
nothing. Uncertain or failed requests cannot be replayed. A newly created StudyRunner
can recover completed preparation/stages and resume only never-submitted slots under
the same admitted identity. Definitive failed cell records remain immutable. Unknown
send/charge state stops the worker and requires reconciliation of that exact request.
The original uncertain event remains in the append-only journal after observation.

## Interpretation of this increment

Tests are engineering fixtures. Rendering original inputs is not running CasePath.
The conservative reservation is neither an expected bill nor a proof that every
possible scientifically defensible comparison exceeds the user's credits. An
unreservable configuration is a hard no-send outcome for that exact configuration.
It must not prompt spending on an incomplete comparison or removing protected families.
