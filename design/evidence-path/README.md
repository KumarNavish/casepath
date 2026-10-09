# CasePath connected evidence preview

This is an interactive visual direction, not the production application. It uses a captured fictional claim dataset. It cannot save a claim, run inference, or modify a backend.

The user accepted the connected-canvas structure as an improvement, then rejected the first blue/neutral identity as ordinary. The current forest/mineral/vermilion identity is the subsequent revision. It has been inspected locally; do not describe it as user-approved or award-ready.

From the repository root, run:

```sh
python3 design/evidence-path/serve.py
```

Open http://127.0.0.1:4187. Python's standard library is sufficient. The server listens only on localhost, serves captured GET responses, and refuses POST, PUT, PATCH, and DELETE. No credentials, cloud connection, model calls, or package installation are needed. Port 4187 must be free.

The preview imports the production `CasePathAutonomous` validation helpers from `casepath/assets/autonomous-workspace-v1.js`. Claim identity, event cursor, original text hashes, and exact citation spans retain their checks. `recorded-fixtures.json.gz` contains nine saved fictional claims, their source text and events, and qualified knowledge records captured before this design work.

## Identity and interaction

- Instrument Sans; expressive case typography, readable facts, quiet supporting labels.
- Forest text `#183D35` on mineral `#EFF1EC`. Vermilion `#C3422B` identifies the selected junction. Color supplements text and shape.
- Facts and process junctions sit on the field. Sources and requirements use paper shapes.
- The complete saved DAG remains visible above the selected evidence path. Its forks, convergences, excluded routes, and stable identities are preserved.
- The selected graph junction connects to its expanded process step. Selecting a different step reshapes this connection once. This is navigation, never simulated agent work.
- Selecting a fact emphasizes its exact supporting phrases and exposes a link to its full record. It does not create more evidence or expose private reasoning.
- A family-home condition can apply while separate service remains blocked by an earlier step. A missing spouse notice can be a future requirement; neither is presented as completed work.
- Knowledge connects a source claim, an immutable qualified version, and the claims that actually reused it. Reuse does not establish those claims' facts.

Instrument Sans is distributed under the bundled SIL Open Font License. The original font is from the Google Fonts `ofl/instrumentsans` directory.

## Local inspection

`identity-all-claims.json` records a browser check of all nine saved claims: the displayed node and edge counts match each saved graph, with no page-level horizontal overflow. Desktop and knowledge screenshots are included as visual references. Source text verification, exact span highlighting, Escape/focus return, version 2's two receiving claims, an inactive arrears branch, and selected-junction visibility at 390px were exercised locally.

These checks do not establish production readiness. Intake only previews a local file packet. The implementation must retain the production controller's real command behavior, stale-response guards, idempotency, draft/FileList preservation, source verification, accepted-event motion, and authority constraints.

## Integration boundary

Use this as a design reference. Do not replace the production controller with this prototype or copy its read-only assumptions into the application. Its fixture selection, demo-first route, and helper exports are local inspection conveniences. The product must choose focus from verified current state while retaining the user's manual selection.

The full product surface includes Work, intake, live/saved claims, documents, sources, action boundaries, knowledge, qualification, quarantine, and provenance. Important waiting reasons must stay visible. Source and action records remain available through contextual disclosure.
