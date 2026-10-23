# W10 final gate evidence

Tested sealed source: `60d4907ca5c975e288fa3c0973992abd31fcc594`. This directory is added by a later evidence-only commit; it does not change the tested application, fixtures, QA, API or source seal.

`verification.json` binds the successful strict stage in `sequence.json` to the single complete clean walk in `walk/walk.json`. The strict stage passed 2,866 tests with ten known historical shadow-packet skips. All eleven frontend suites were mandatory, and protected Mac tests stayed unchanged. The clean walk runs all seven scripts serially and covers all nine cases with zero errors, writes or overlaps and closed browser resources.

The original sequence keeps its truthful failed status: strict passed, then its first walk stopped at an acceptance-verifier port error. `failed-walk-origin/` and the original controller log retain that attempt. `final-w10r7-walk-r2-diagnosis.json` explains the repair. The hashed `w10-walk-origin-adapter.mjs` replaces only the acceptance verifier's hardcoded base with its existing validated proofOrigin. The original and executed verifier hashes are in `walk/origin-adapter.json`; every assertion and all covered source bytes remain unchanged. The accepted walk starts again at process and completes all seven scripts, rather than combining partial walks.

`failed-before-collection/` preserves the earlier missing-generated-artifact failure. Explicit prepare in the same isolated clone produced the exact sealed artifact hash, recorded in the preparation admission. No failed record is relabelled as passed.

`manifest.json` hashes every packaged receipt, log, screenshot and auxiliary video. Capture, fidelity and fresh cold-viewer evidence are in `../final-proof/`. The cold response is preserved unedited with its comprehension limits. Integration and release remain with the Mac owner; this work grants no spending.
