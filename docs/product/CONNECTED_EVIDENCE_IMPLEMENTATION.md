# Connected evidence implementation

Implementation base: `8887ce1c2b6d693ae83f743764d1c26f8d4834d6` on
`codex/casepath-causal-experience-integration-20261009`. The presentation follows
`design/evidence-path/README.md`; its visual identity remains subject to Mac
inspection. This supersedes the earlier permanent rail and report composition,
while retaining the causal-experience authority and motion rules.

The production autonomous controller now presents compact navigation, the complete
saved DAG, and an attached original passage → fact/condition → selected step →
evaluated requirement path. Full operational records remain in contextual
disclosures. Selection and viewport changes reveal the junction within its own
graph scroller. Initial focus comes from verified state; manual selection persists.

Document timing remains the recorded process-wide evaluation, distinct from the
selected step's prerequisites and execution authority. Knowledge receiving links
require exact ID/version and, when supplied, the immutable hash. Reuse establishes
no facts in a receiving claim. Native forms, FileLists, drafts, exact retries,
source verification, journal acceptance and stale-response guards are retained.

Instrument Sans is bundled as lossless WOFF inside the autonomous stylesheet,
together with its full copyright and SIL Open Font License. Original TTF/license
assets are retained under `casepath/assets/fonts/`. Embedding keeps the existing
public-build allowlist unchanged; reviewed-workspace fonts are unchanged.

Focused checks:

```sh
node --test casepath-qa/autonomous-workspace-v1.test.cjs \
  casepath-qa/autonomous-evidence-identity-v2.test.cjs \
  casepath-qa/sites-autonomous-entry.test.cjs
```

The browser cases use the existing locked Playwright QA dependency, installed
Chromium where available, or Playwright's browser. Cloud validation passed all
107 tests with no failures or skips. Separate production-page Chromium checks
passed 27 cases at 1440px and 390px; the static build and embedded font/license
bytes were verified. These checks do not establish visual acceptance.

The captured fictional fixtures contain nine existing autonomous claims, including
three deferred single-node investigations. They are QA records, not a corpus
import or a replacement demonstration set.

To inspect the actual production page/controller with those captured GETs:

```sh
python3 casepath-qa/serve-autonomous-evidence-fixture-v2.py --port 4188
```

Use the local address printed by the helper. All mutations are refused; this
checks frontend interaction, not live API command execution. Add `--built` to
inspect `casepath-public` after the ordinary static build. The capture contains
verified extracted text, not downloadable original bytes; inspect original
downloads and actual write commands against an isolated deterministic API.

This worker branch deliberately leaves the release manifest untouched. Mac owns
integration, final source sealing, visual acceptance and any publication. Normal
`./bin/casepath prepare` / `dev` require that final seal; do not bypass source
verification. No backend, allowance, provider, journal, corpus or hosting changes
are part of this implementation.
