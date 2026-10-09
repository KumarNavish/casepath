# Unified frontend implementation — 9 October 2026

The production autonomous controller now presents Cases, Demonstration, the
canonical claim workspace and Knowledge within one internal shell. It uses the
existing native JavaScript/CSS and bundled Instrument Sans identity. The source
base is `17c93a1f8f1c7abe01a3d78da9b66893f99dc251`; the backend contract was
reviewed at `862c6d194411b4626bb7ea2148aeb9496ec8c9e1`.

Cases reads the complete paginated summary collection, searches the original
message excerpt and observable intake metadata, and filters explicit browse-only
domains. The backend supplies the three 50-case domain groups. The frontend never
classifies an original or sends browsing metadata into an investigation. Existing
non-corpus intakes retain their separate identities and accepted histories.
Search, status, domain, claim details, replay cursor and exact knowledge version
links use internal hash routes with back/forward and reload support.

The nine presentation IDs and display labels come from Mac's source-inspected
selection commit `80939f0ec4430402b029a646d60f5bf8b465e9f8`. The frontend stores
only the selected IDs, domain navigation and labels. It neither copies the
packets nor imports selection explanations, expected outcomes or evidence.
Live execution and verified replay are explicit modes, distinct from claim
status. Live controls respect the backend allowance and provider projection.
Replay reads verified accepted prefixes, retains the independently bound live
head and provenance, and has no write controls or live polling. A case without
accepted history stops playback at its honest original intake. Playback does
not substitute an authored graph or silently switch mode.

Every initial claim read and poll first uses the atomic snapshot endpoint.
State, projection, event sequences, resulting state identity and journal cursor
must agree before display. Legacy paired reads are used only when the snapshot
capability returns 404, 405 or 501. Three immediate reads remain bounded; a
transient writer advance recovers on the normal timer even before the first
verified state exists. Navigation epochs abandon stale results. Returning to a visible tab also resumes
an opening that has not yet obtained a matching snapshot; an unknown-claim 404
does not disable atomic reads for subsequent valid claims. Initial reads,
reconnects, hidden pages and reduced-motion views do not replay live motion.

Revision-zero records show the original message and native source names without
a substantive process, checklist or outcome. Original preview and acquired
source text remain separate checks. Preview self-hashes and extracted-text
hashes are verified without an admission receipt. A later supporting file does
not inherit the original corpus binding. Native PDF/image viewing checks the
original bytes and size, then uses a temporary Blob URL; URLs are revoked on
close or disposal. Downloads retain the original filename and media type.
JPEG display does not claim interpretation or evidence sufficiency.

The complete arbitrary DAG remains available in Evidence path. Documents,
Original sources and Recorded work hide the graph above their content, including
at 390px. Graph selection, exact citations, per-claim disclosure state, receipt
identities, native forms and FileLists remain preserved through refresh and
navigation. The original-start command retains its exact idempotency key,
revision-zero guard and body after an uncertain response, including when a
background snapshot observes admission before the response is confirmed.
Retry is explicit and remains available at the new revision; replay hides it.

Knowledge retains recorded definitions, qualification, exact version/hash links,
source-case and receiving-case links and public provenance. The current API
records one publishing source case per version. This change does not establish
additional contributing support, a new qualified definition, or actual reuse
among the nine selected originals.

## Focused validation

These commands completed with zero failures or skips:

```sh
node --test casepath-qa/unified-product-v1.test.cjs \
  casepath-qa/autonomous-workspace-v1.test.cjs
# 90 passed
node --test casepath-qa/autonomous-evidence-identity-v2.test.cjs \
  casepath-qa/sites-autonomous-entry.test.cjs
# 24 passed
node --test casepath-qa/unified-product-browser-v1.test.cjs
# 21 passed
```

The independent Chromium regression uses mocked GET DTOs and a narrowly scoped
explicit Start retry fixture. It covers all 150 original rows, nine canonical
presentation IDs excluding historical packets, live/replay status separation,
read-only source preview, concurrent writer advancement, atomic and legacy
initial recovery, strict fallback statuses, stale navigation, source/document
graph visibility, and uncertain Start admission followed by polling and exact
retry. Prefix provenance, same-revision head identity, every supplied source
descriptor field and original/later-source binding checks are separately tested. The Start fixture also verifies that same-claim replay hides pending
write controls and that polling never resubmits the command.

A separate local Chromium inspection used the production index/assets against
the combined backend's isolated deterministic API on port 4195. It observed
150 original records plus a separately created native intake, 50 rent-domain
records, nine demo links, original-message inspection, verified PDF preview,
zero substantive nodes for an unprocessed case, zero browsing writes, zero page
errors and no page overflow at 390px. Screenshots and the receipt are retained
under `/tmp/casepath-unified-*.png` and
`/tmp/casepath-unified-inspection.json`. This establishes local interaction
mechanics, not Mac visual acceptance or hosted release behavior.

The full deterministic/backend sealing suite, source manifest regeneration,
production provider calls, hosting writes and live execution of the nine
originals were deliberately not performed in this frontend scope. Earlier
in-progress test runs exposed unavailable new helpers, legacy fixture assumptions,
and a pending Start control visible in replay; the final checks above verify the
corrected behavior. Mac owns final integration, source sealing, native PDF visual
inspection, visual acceptance and publication. The hosted 24/24 allowance was
not changed. No substantive nine-case demonstration or qualified cross-case
reuse is claimed.
