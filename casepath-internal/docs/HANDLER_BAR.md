# The handler bar

**The bar.** A Protekta handler delegates a whole case, watches meaningful work unfold, understands and verifies everything without effort, and steps in only where human judgment matters. Every capability works on the real Hackathon dossiers, not only on the preview.

**The benchmark is the handler**, not a test suite. A feature is done when a handler would recognise its value in the first minute, could check any statement in one click, and could correct it in one more.

## Ground rules

1. **No new model calls.** Everything below is derived from results the runs already produce. If a milestone seems to need a model call, stop and ask.
2. **Handler language on every handler screen.** German, the words of the case ("Mängelrüge", "Frist", "fehlt"), never the words of the machinery ("agent", "tool", "verdict", "routing").
3. **Every statement carries its source.** One click opens the file at the quoted sentence. A statement without a source is shown as unverified, never as fact.
4. **Motion means change.** Something moves only when the case's state changed. Nothing decorative.
5. **Seven things at most** in any list on first sight; the rest behind "+N weitere".
6. **Honest empty states.** "Nichts offen" also says what was checked.
7. Nobody reads the dossiers for this work. Use counts, structure and what is on the handler's own screen. Case content never leaves Mobiliar.
8. Nothing is pushed to GitLab and nobody is notified. Code goes to the private GitHub branch only.

## M0 · What the cases demand (content-free, half a day)

From the stored results of the 11 dossiers, one row per case: pages, scanned pages, recognised documents, parties, timeline events and the days they span, facts established / rejected / conflicting, documents required / found / missing / unusable (and how many by law), deadlines, open points, flagged instructions, run minutes, tokens.

Then five lines: where a handler's time goes in these cases, read from the numbers (long scanned dossiers, documents announced but not enclosed, facts the files contradict, deadlines). These five lines decide the order of M1 to M4. Change the order if the numbers say so, and say why.

## M1 · "Übersicht": the case in thirty seconds, and what needs you

A first tab, shown when a prepared case opens. Two parts.

**Der Fall.** Anliegen in two sentences; Parteien; where the case stands in its process (the step it is on, the next step, why); Fristen with days left; Dokumente as "n vorhanden · n fehlen oder unbrauchbar"; the recommended next action with its draft one click away.

**Braucht Ihr Urteil.** Only the points where a person must decide, most urgent first:
- a fact the two readings disagree on, or that the files contradict;
- a fact that decides the path but has no accepted source;
- a required document that is missing or unusable (action: request it from the customer, draft ready);
- a deadline inside 14 days;
- text in a file that addresses an AI;
- a Knowledge suggestion waiting for a yes or no;
- a page that could not be read.

Each point is one sentence, its evidence one click away, and its decision as buttons right there (bestätigen · korrigieren · nicht nötig). A decided point leaves the list and can be undone. When the list is empty: "Nichts offen. Geprüft: n Fakten, n Dokumente, n Fristen."

Done when, on three real dossiers: every line of Der Fall opens its source in one click; every point in Braucht Ihr Urteil can be decided without leaving the tab; the counts equal those on the detail tabs.

## M2 · A correction changes the case, at once

A handler corrects a fact (value, and optionally the sentence that shows it). The fact is marked "vom Bearbeiter gesetzt". The process, the checklist, the next action and the Übersicht re-evaluate immediately (evaluation needs no model), with a before/after line ("Schritt 4 → Schritt 6; 1 Dokument nicht mehr nötig"). One click undoes it. The same for marking a document "liegt vor" (with the file) or "nicht nötig" (with a reason).

Done when a correction on a real dossier moves the process step and the checklist in under a second, survives a reload, shows in the Fallbericht, and undo restores the exact previous state.

## M3 · Watching the work

The live view already shows the process forming, the quote being read and the documents list growing. Add:
- **Five stages in handler words** across the top (Lesen · Prozess · Fakten · Dokumente · Prüfung), the current one with its real elapsed time and an expected remaining time taken from this deployment's earlier runs of similar size.
- **One sentence per meaningful event**, in handler words, newest on top, each opening its source: "Mängelrüge gefunden: E-Mail vom …, S. 1". Bookkeeping events stay in the Arbeitsprotokoll.
- **Braucht Ihr Urteil fills while the run goes on**, so a handler can already decide a point before the run ends.

Done when a handler who looks away for a minute can tell at one glance what happened meanwhile, and nothing on the screen moved without a reason.

## M4 · The handler's verdict, as the benchmark

At the foot of the Übersicht, six one-tap questions: Zusammenfassung stimmt · Prozessstand stimmt · Fehlendes fehlt wirklich · Fristen stimmen · Entwurf wäre versendbar · Zeit gespart (keine / etwas / viel). Stored with the case. `python -m casepath scorecard` reports them as counts, content-free.

Targets for calling the bar met, over the pilot's cases: each of the first five at 90 % yes or better, "Zeit gespart: viel" on most cases, and every "nein" traceable to the statement the handler corrected.

## How each milestone ships

1. Audit first: list what already exists for the milestone and build only the gap.
2. Build on a clone of the private GitHub branch. `make test` ends "OK". `make preview`, then drive the whole flow in a browser (delegate, watch, verify a statement, correct it, undo, export) and look at every screen at 1440 and 390 wide, German and English, with no console error.
3. Push to GitHub. Patch the DSW copy. One deploy per milestone, with Navish's yes, using the guarded verify-then-swap copy.
4. Check the milestone's "done when" on three real dossiers, by structure and counts only.
5. Report in ten lines: what exists now, what the check showed, what is still not good enough. Say plainly what does not work yet.
