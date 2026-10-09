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

## Bounded UX and recovery followup

This followup starts at frontend commit
`6851b41ec280abbc8326b8fe584ad4b4d2c2023f`. The default collection now shows
only the API's `canonical_original` records. An internal **Added cases** scope
shows native intakes with their separate identities and histories; missing
legacy origin metadata is disclosed as unrecorded instead of inferred from IDs.
The scope is encoded in the collection hash and survives reload and browser
Back/Forward. A confirmed native intake is remembered from its explicit intake
route and cannot enter the original collection.

Completed handling displays **Investigation complete** for the existing
`completed`, `complete` and `resolved` lifecycle codes. Metrics, searches and
status filters use that label without changing saved codes, journal identities
or recorded legal outcome titles and summaries.

Unprocessed correspondence keeps its exact full subject and body. The compact
subject and readable message column place original files beside the message on
desktop and before it on mobile. The 390px header places New claim beside the
brand and the three primary destinations on a second row. The native PDF/image
Blob viewer and its byte/hash checks are unchanged. Unsupported image previews
show one capability statement; exact source identity, preview admission flags,
extraction coverage and limitations remain under a technical disclosure. A
failed native byte check cannot advertise an available image preview.

Opening and polling reads share a generation guard and enforce monotonic
verified revisions. Superseded responses and errors cannot replace a newer
saved state or its forms and disclosures. Live Play resumes an automatically
recovered, verified opening only for the same active session, navigation epoch,
canonical case and selection index. It attempts original Start once; an
unconfirmed admission stops automatic progression and retains explicit retry
with the original request key. Selecting a linked process node from Documents
also synchronizes the visible detail hash for reload. A normal visibility
refresh no longer reports a restored connection unless a prior poll failed.

Final focused commands passed with zero failures, skips or cancellations:

```sh
node --test casepath-qa/unified-product-v1.test.cjs \
  casepath-qa/autonomous-workspace-v1.test.cjs
# 92 passed
node --test casepath-qa/autonomous-evidence-identity-v2.test.cjs \
  casepath-qa/sites-autonomous-entry.test.cjs
# 24 passed
node --test casepath-qa/unified-product-browser-v1.test.cjs
# 34 passed
```

The browser fixture now separates the real 150 original IDs from the nine
recorded native histories. Both complete timed presentations use explicitly
mocked accepted histories and a virtual clock. They visit the nine canonical
IDs in order without manual advancement, pause during modal inspection and
hidden tabs, and stop on navigation. Replay issues zero POSTs; live issues one
guarded Start per unprocessed original. Separate regressions cover recovered
initial GETs, uncertain terminal admission with explicit exact-key retry,
overlapping reads and conflicting same-revision hashes, linked-node reload,
original/added scope reload and history, exact full correspondence, two-row
mobile navigation, JPEG disclosure/focus and corrupted native bytes.

Local screenshot and bounds inspection retains the exact long original
`clm_e262801f9368bc12` at 1440px and 390×844px. The mobile header is 106px high,
the full subject is 165px high, and its JPEG source button begins at y=633px,
before the original body. Desktop sources align alongside the message at
y=281px. The message is 16px and constrained to 72ch; neither viewport overflows
horizontally. The exact subject and complete original body remain present.
Receipts and screenshots are under
`/tmp/casepath-original-clm_e262801f9368bc12-{1440,390}.{json,png}`; a separate
actual corpus JPEG inspection is under
`/tmp/casepath-original-jpeg-dialog-390.{json,png}`. Native viewer identity
verification and Escape focus return passed.

These are isolated mechanical checks, not visual acceptance, provider
execution, nine-case qualification or hosted publication. No provider or
production mutation was performed, and the source manifest remains unchanged.

## Separate presentation and inspection followup

This followup starts at `6badec6e69ba03e28d8fb6b72593c6b410c98c14` and
remains separate from the original/added collection and recovery fixes.

The nine-case itinerary now has global 01–09 numbering and three domain columns
on desktop. Its labels describe presentation order across independent cases.
Full original subjects remain in the DOM, title and accessible name, with a
single-line preview in the compact overview and the exact full subject in claim
context. Active presentation position comes from the matching session index;
its current row uses the verified current state ahead of an older collection
summary. A disclosure keeps that itinerary available while inspecting a case.
The desktop fixture measured every row within a 1440×900 viewport, at
y=570–860px, rather than requiring a scroll past the first domain.

Mobile graph controls show **Step X of Y · Inspection position**. Previous and
Next select and center actual nodes in the complete saved graph's display
order. They preserve forks, convergence, excluded routes, free pan, page scroll
and enabled-button focus. This position is unrelated to execution completion.
Normal and reduced-motion checks inspect all 11 actual nodes of the recorded
forked fixture. Individual completed nodes and recorded actions again say
**Completed**, while claim lifecycle surfaces retain **Investigation complete**.
A running claim cannot inherit its completed step's handling label.

Graph and evidence connectors now meet 3:1 against their effective background,
including computed path, stroke and ancestor opacity. The recorded minima at
1440px and 390px were 3.528:1 for inactive dashed graph routes, 3.961:1 for normal
graph/evidence lines and endpoint circles, and 4.782:1 for coral selection and
tether paths. Dashed exclusions and coral selection remain distinct. Search
retains a persistent underline and subtle inset with its existing focus outline.

Pending hash navigation is checked before automatic Start, presentation
advancement and post-await route replacement. Held initial or replay reads
cannot overwrite a newly selected Cases destination before its hash event is
handled. Exact explicit retries and read-only replay identities are preserved.

Local mechanical screenshots and bounds are under
`/tmp/casepath-visual-itinerary-1440.{png,json}`,
`/tmp/casepath-visual-itinerary-390.png`,
`/tmp/casepath-visual-inspection-390-{no-preference,reduce}.png`,
`/tmp/casepath-visual-search-{1440,390}.png` and
`/tmp/casepath-visual-contrast-{1440,390}.json`. The itinerary screenshots use
explicitly mocked accepted histories; their completed labels do not establish
actual execution of the nine originals. This followup does not claim visual
acceptance, qualification, hosting changes or provider execution.

Final focused results for this separate followup: **93 Node**, **24 existing
browser/Sites**, and **42 product browser** checks passed, with zero failures,
skips or cancellations. Commands are the same three focused commands above.
The 42 browser checks preserve all prior 34, including both complete nine-case
mocked sequences, and add the eight presentation, inspection, effective
contrast, search, lifecycle-label and pending-navigation regressions. A separate
read-only review independently passed the eight new cases with no findings.
The entry's JS and CSS SHA-256 query values match their final bytes. No source
manifest, backend, allowance, provider or hosting change is included.
