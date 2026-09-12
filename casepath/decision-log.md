# CasePath convergence decision log

This log records decisions for the convergence release. Evidence and status are
updated as implementation and validation progress.

## CPD-001 — Preserve the v20 journey; remove contradictory layers

- **Problem:** The graph-first v20 journey is the clearest product generation,
  but v18, v19, and v20 repeatedly overwrite release state and infer moments by
  polling mutable DOM text.
- **Approaches considered:** add another override layer; rebuild the frontend;
  consolidate ownership inside the current v20/v16 runtime.
- **Decision:** keep the existing visual language and URL, remove competing
  release writes, and make render transitions explicit. Do not create v21.
- **Evidence:** the retained v20 browser journey is coherent; source audit found
  simultaneous 450 ms, 260 ms, and 900 ms ownership loops.
- **Rejected:** another additive layer, because it would deepen the race;
  wholesale redesign, because it would discard the already accepted journey.
- **Affected files:** `casepath/index.html`, `casepath/assets/live-v16.js`,
  `casepath/assets/live-v18.js`, `casepath/assets/live-v18-handoff.js`,
  `casepath/assets/live-v20-focus.js`.
- **Validation:** canonical focused browser journey, console checks, responsive
  states, and immutable release assertion.
- **Implementation status (2026-08-11):** source-converged and deterministically
  checked. The static v20 marker is immutable, the core emits
  `casepath:render`, and the retained enhancement layers no longer poll or
  rewrite release identity. The current Playwright journey and deployed
  verification remain pending.

## CPD-002 — One bounded model call, deterministic downstream authority

- **Problem:** The public pipeline labels deterministic functions as agents and
  contains no verified model-backed understanding step.
- **Approaches considered:** free-form end-to-end graph generation; one model
  call per specialist; one source-linked canonicalization call followed by
  deterministic contracts.
- **Decision:** use OpenRouter model
  `nvidia/nemotron-3-ultra-550b-a55b` only for observable-package
  canonicalization. Keep graph validity, evidence linkage, review authority,
  promotion, versioning, and budget enforcement deterministic.
- **Evidence:** the recovered research release found canonical-state errors
  dominate whole-plan performance; OpenRouter currently exposes structured
  output and reasoning-capable endpoints for the exact model.
- **Rejected:** free-form end-to-end graph generation, because it obscures error
  attribution; many specialist calls, because they increase cost and failure
  surfaces before the canonicalizer is validated.
- **Affected files:** `casepath-api/casepath_api/canonicalizer.py`,
  `casepath-api/casepath_api/pipeline_v15.py`, storage and tests.
- **Validation:** mocked transport/schema/budget tests, one authorized paid smoke,
  source-provenance checks, and a complete call ledger.
- **Implementation status (2026-08-11):** the bounded adapter, exact-model
  request, source-grounding checks, cache/single-flight behavior, cumulative
  cost guard, and sanitized ledger are implemented and covered by mocked
  deterministic tests. One authorized provider attempt is retained as
  failed-closed evidence: the application rejected an exact-private-reference
  mismatch and bound no successful ledger call. It is not accepted model-backed
  release evidence; an accepted retry remains pending.

## CPD-003 — Reviewed memory is immediate; shared knowledge is quarantined

- **Problem:** One public review currently fabricates three supporting cases,
  successful evaluations, and an approved v4 playbook—even for a rejected
  review.
- **Approaches considered:** retain narrative promotion; disable learning;
  separate case memory from shared-rule promotion.
- **Decision:** an accepted demo review may create one explicitly unverified
  reviewed-case memory. A reusable candidate remains quarantined at actual
  support `1/3`, with target and protected evaluations `not_run`; the shared
  playbook does not change. Rejection creates neither memory nor candidate.
- **Evidence:** backend route reproduction showed `decision=reject` returning an
  approved v4 candidate and changing the later claim.
- **Rejected:** hard-coded promotion, because it is false governance evidence;
  disabling memory, because one reviewed case is legitimately useful as a
  precedent when its authority is explicit.
- **Affected files:** API request schema, pipeline review/consolidation, storage,
  frontend learning/reuse views, and browser QA.
- **Validation:** rejection, duplicate review, quarantine, later-memory retrieval,
  and no-shared-change regression tests.
- **Implementation status (2026-08-11):** implemented and covered by aligned
  backend tests. Rejection creates no memory or candidate; an accepted generated
  demo edit creates unverified memory and a `1/3` quarantined candidate with
  target/protected tests `not_run`; shared playbook v3 remains unchanged. The
  current browser journey is pending.

## CPD-004 — The complete graph is the product artifact

- **Problem:** The API returns 19 nodes and 22 edges, while the UI renders only
  the 11-node `main_spine`; the current gate encodes that omission as success.
- **Approaches considered:** preserve spine-only rendering; show all nodes at
  once; keep the spine primary with compact inspectable branches and loops.
- **Decision:** retain the spine as the default reading path and expose every
  branch/evidence-loop node and edge through progressive disclosure in the main
  workspace.
- **Evidence:** hidden nodes include scope failure, no dispute, urgent action,
  formal notice, cause outcomes, and the evidence loop—material handling logic.
- **Rejected:** a dense all-at-once graph, because it violates deep minimalism;
  spine-only, because it is not the complete handling process.
- **Affected files:** process renderer, graph styles, decision inspector, QA.
- **Validation:** node/edge coverage against the API graph plus visual and
  keyboard inspection at desktop, 390 px, and 320 px.
- **Implementation status (2026-08-11):** source-converged. The spine remains
  primary while all non-spine nodes, branches, and edges are inspectable in the
  main workspace, and the focused gate asserts API topology coverage. Visual,
  responsive, and keyboard execution of that gate remains pending.

## CPD-005 — Release alignment means source identity, not equal component versions

- **Problem:** frontend 20.0.0, API 15.0.0, release metadata 12.0.2, and source
  manifest 10.0.0 are conflated by a stale requirement that semantic versions
  match.
- **Approaches considered:** rename every component to one version; keep the
  current files; introduce one release identity with distinct component
  versions and a common source commit.
- **Decision:** use one stable release ID/source identity and preserve truthful
  component versions. Deployment passes only when frontend, API, and QA expose
  the same frozen source commit and release ID.
- **Evidence:** live frontend bytes match product commit `a867bb5`; API bytes are
  unchanged from `550c421`, but public endpoints expose no commit, so live
  alignment cannot currently be proven.
- **Rejected:** semantic-version equality, because independently versioned
  components need compatibility rather than identical numbers.
- **Affected files:** release contract, generated source manifest, health
  endpoints, frontend meta, canonical QA.
- **Validation:** generated manifest verification and post-deploy identity gate.
- **Implementation status (2026-08-11):** the release contract, generated
  deployment identity, API identity payload, and QA preflight are implemented.
  Local identity deliberately remains `unknown`/`not_proven`; no current
  frontend/API/QA deployment has yet supplied the same frozen non-unknown
  commit and release ID.

## CPD-006 — Public disclosure and model-visible leakage are separate boundaries

- **Problem:** the public demo must disclose generated data, while evaluated
  source bytes currently expose `generated`, `fictional`, `.example`, `DEMO`,
  and answer-tailored language.
- **Approaches considered:** hide disclosure; let the model see disclosure;
  disclose outside an isolated evaluator package.
- **Decision:** retain an obvious public-shell disclosure, but construct the
  model-visible observable package from leakage-checked artifact bytes and a DTO
  that excludes generation lineage, hidden fact IDs, and semantic descriptions.
- **Evidence:** browser inspection found visible generation text in the lease;
  release audit found generation metadata across PDF and correspondence files.
- **Rejected:** hiding the public warning, because it would misrepresent the
  demo; allowing model-visible clues, because it invalidates the reasoning task.
- **Affected files:** artifact generation, observable DTO, leakage verifier,
  release manifest.
- **Validation:** byte/metadata leakage scan and a pending independent blind
  realism review; no realism claim before that review.
- **Implementation status (2026-08-11):** the observable DTO, application-shell
  disclosure, deterministic artifact generation, byte/text/metadata scan, and
  artifact manifest are implemented and mechanically tested. Independent blind
  realism review is still pending, so no blind-safe or realistic-artifact claim
  is allowed.

## CPD-007 — Treat the later fixture as a temporal holdout and prove causality, not quality

- **Problem:** the comparison fixture was analyzed before review and described
  too close to an unseen/improved claim, while no qualified outcome label exists.
- **Approaches considered:** call the known fixture unseen; delete the comparison;
  preserve a same-input counterfactual but freeze it until after memory creation.
- **Decision:** exclude the later fixture from review and memory construction,
  compute its no-memory counterfactual only after learning is frozen, then run
  the identical observable package with governed unverified memory. Claim only
  the exact causal DTO delta and unchanged shared v3, never quality improvement.
- **Evidence:** semantic eligibility is claim/fact/artifact-ID independent and
  the result is bound to one added node, two edges, three evidence changes, pure
  replay, and ten deterministic checks; qualified usefulness remains absent.
- **Rejected:** “unseen claim” and “improved outcome” copy, because the fixture
  and expected transform are known to the application and have no expert label.
- **Affected files:** flagship journey, browser gate, learning proof tests and KT.
- **Validation:** uninterrupted local journey, temporal-order source regression,
  exact receipt/replay/tamper tests, and same-commit production QA when deployed.

## CPD-008 — Protected regression must bind full output hashes

- **Problem:** candidate governance called nine eligibility classifications a
  protected regression without checking a process or evidence DTO.
- **Approaches considered:** keep the name; build a second mutable benchmark;
  add a stable protected source-claim output control alongside routing tests.
- **Decision:** retain the useful semantic negative matrix and add an independently
  recomputed source-claim control that must be ineligible and preserve the exact
  pre-review result, process, and checklist hashes.
- **Evidence:** case-specific memory excludes its source claim; the persisted
  pre-review result and review-transform input hashes are independent origins.
- **Rejected:** eligibility-only reporting, because it cannot detect output drift.
- **Affected files:** pipeline governance report, backend/browser tests, release evidence.
- **Validation:** origin recomputation, hash equality, candidate tamper rejection,
  and full protected report binding in the browser journey.

## CPD-009 — Logical specialist fan-out uses physical provider single-flight

- **Problem:** the compiled DAG correctly schedules document/source-integrity
  and process-decision specialists as a fan-out, but attempt 14 created their
  provider calls only 4.051 ms apart and exposed no application-wide admission
  limit. Both calls later failed with OpenRouter-boundary 429 responses.
- **Approaches considered:** make the DAG sequential; add inference retries;
  preserve fan-out/join semantics while serializing only provider sends.
- **Decision:** keep `parallel_groups` and the authoritative execution topology
  unchanged as logical scheduling evidence. Gate all physical OpenRouter sends
  with a process-wide `provider_max_in_flight: 1` admission contract. A bounded
  admission timeout occurs before transport and records
  `blocked_provider_concurrency`, `call_count: 0`, null actual cost, no response
  or usage provenance, and no cacheable output.
- **Evidence:** attempt 14 proves application-side overlap was possible. It does
  not prove concurrency caused the 429s; the failed calls retained the expected
  DeepInfra route but no actual failed-call upstream identity.
- **Rejected:** changing the DAG, because topology and transport are different
  concerns; retries, because they would weaken exact-once inference and could
  compound unknown provider charges.
- **Affected files:** shared OpenRouter runtime admission, release/schema pins,
  public health/readiness, browser QA, governance and transfer records.
- **Validation:** static cap tamper tests, concurrent admission tests, exact
  zero-call receipt/ledger tests, QA positive/tamper fixtures, and unchanged
  logical `parallel_groups` assertions. Same-commit production acceptance is
  still required.

## CPD-010 — Publish only the active v20 static runtime closure

- **Problem:** Render previously published the entire authored `casepath/`
  source tree. Unreferenced legacy scripts and obsolete QA programs therefore
  remained reachable at the product origin even though the v20 page never
  loaded them; some retained superseded v10/v15 wording.
- **Approaches considered:** rewrite every historical asset; delete source
  history; publish an exact generated runtime closure.
- **Decision:** build ignored `casepath-public/` through
  `casepath/tools/build_static_site.py` and point Render only at that directory.
  The builder copies an exact allowlist containing the v20 shell, its direct
  and recursively injected assets, `_headers`, `release.json`, and a freshly
  generated known-commit `deployment.json`.
- **Rejected:** broad source-root publication, because dormant executable code
  is not part of the flagship product contract; piecemeal legacy copy edits,
  because they do not prevent later obsolete assets from becoming public.
- **Validation:** exact 20-file inventory, recursive asset-closure equality,
  stale-file removal, no tools/docs/releases/legacy assets, known-commit
  fail-before-mutation behavior, and release-verifier pins for both the build
  command and publish path.

## CPD-011 — Gate paid QA behind the complete deterministic browser lifecycle

- **Problem:** multiple production QA attempts completed six paid model roles
  before encountering deterministic presentation assertions in later browser
  states. The assertions were valuable, but their placement made provider work
  the prerequisite for discovering ordinary UI drift.
- **Approaches considered:** keep retrying the hosted journey; weaken late UI
  assertions; split model and presentation validation into an enforced two-phase
  gate that executes the same browser program.
- **Decision:** the definitive QA build must first build the curated frontend,
  launch an isolated deterministic-reference API with no provider credential,
  and execute the full browser lifecycle. Only a passed temporary report plus
  an exactly empty model ledger may unlock the production URL phase. Both Node
  and Python are pinned, and the runner rejects a Python version other than
  3.13.9 before dependency installation or browser execution. It also rebuilds
  and checks every ignored deterministic runtime artifact from tracked sources,
  so a clean Render checkout cannot inherit local-only evidence bytes. The
  production phase also requires the global model ledger to be exactly empty
  before caller reset or run creation; reset is not treated as ledger cleanup.
  The paid
  phase remains one uninterrupted cold/warm production journey and retains the
  only publishable acceptance evidence.
- **Rejected:** paid-first QA, because deterministic UI defects do not require a
  model call to reproduce; weakening the browser contract, because that would
  hide inspectability and authority regressions rather than prevent them.
- **Affected files:** definitive QA runner, browser output isolation, Render
  Blueprint/verifier, release tests, governance and transfer record.
- **Validation:** shell and source-order tests, exact Blueprint tamper rejection,
  full deterministic browser report, zero-record/zero-network/zero-cost ledger,
  then one separately aligned production journey.

## CPD-012 — Pin the current run to Together after DeepInfra rejection

- **Problem:** a fresh exact-model call failed closed at the first role with an
  external DeepInfra 429 even though the OpenRouter account and local admission
  controls were healthy.
- **Decision:** pin the current exact Nemotron route to OpenRouter endpoint tag
  `together`, require upstream identity `Together`, and retain parameter,
  privacy, single-flight, no-retry, and no-fallback guards unchanged.
- **Evidence:** OpenRouter's endpoint metadata lists Together as the only current
  non-DeepInfra route for this model that advertises both `response_format` and
  `structured_outputs` together with the active reasoning parameters.
- **Rejected:** generic provider fallback, because it weakens route provenance;
  BaseTen and Venice, because their advertised parameter sets do not satisfy the
  strict structured-output contract.
- **Validation:** exact wire-body and provider-metadata tests, current health and
  release-contract checks, deterministic browser self-test, then one separately
  authorized fresh six-call acceptance run.
