# The first look: the process owner handles one case

**Before any study session:** set `CASEPATH_SCORECARD_SALT` (a fixed secret that keeps the pseudonyms stable) by filling `SALT` in the deploy notebook's cell before the deploy (the cell writes it into the app's environment; it is never in Git); without it a session refuses to start. Also deploy with no speed trial unless the frozen run names it.

**Purpose.** Before five experts see CasePath, the person who drew Protekta's mould process handles one case in it, exactly as an expert will. What is alien to how Protekta works shows up as his changes and notes, and is put right before the freeze.

**When and what.** Day 7, about forty minutes. One development dossier (D8) as it stood before Protekta's first request, after five minutes on the synthetic practice case. Never a study case (D2, D4, D7) or the reserve (D5).

**How he gives feedback: only through CasePath, with the same three gestures as every expert**
1. He gives his own answer first (process step, documents to request, next action), then CasePath's result appears.
2. He leaves what is right, changes what is not where it stands, with the reason in one tap.
3. He leaves an "Anmerkung" wherever something is unfamiliar: a word, an order, a missing place for something he would write down. One optional line when he closes the case.

His session is also the rehearsal of the experts' session: if anything in the procedure stumbles, it stumbles here.

**What must work by day 6** (dry run with Navish the day before)
- The case is prepared at its decision point and serves only the pages that existed then.
- Own answer first, then the reveal.
- Every point decidable in place; a changed step changes documents, letter and next action at once and says what changed.
- The letter can be edited and copied; the case closed.
- Every statement opens its source; every action and every Anmerkung is recorded.

**What happens with what he leaves**

| His gesture | Becomes |
|---|---|
| a change with "Gilt generell so" | a rule, tied to its process step or legal basis |
| a change with "Steht anders / nicht in den Akten" | a reading or checking fix |
| a change with "Hier nicht relevant" | a process condition |
| an Anmerkung on wording or order | changed, if it is Protekta's way and costs nothing elsewhere |
| an Anmerkung on something missing | added if it belongs to the case's chain; otherwise listed for later |

Changes are made on days 7 to 9; the list of what changed and what deliberately did not goes into the study record. Nothing he notes about this one case becomes a rule unless it holds for the process.

## Measuring time, once, with the person's consent

Nothing so far says how long a handler needs with CasePath or without it. One observed session can show it or refute it; this is its protocol, fixed before the session so the result cannot be read to taste.

**What is measured.** The person's active time on a case, by CasePath itself: the case opened, a minute without input or the window hidden or the case left (idle), the return (`quality/auswertung.py`, «handling_seconds»). And the share of each approved letter that is the person's own wording, counted by word at the approval («letter_changed_ratio»). The measurement runs only where the deployment allows it (`CASEPATH_TIME_MEASURE=session`; the default is off, and then the server refuses the events) and only while the person has switched it on for the browser session («Zeit messen» in the top bar, which then reads «● Zeitmessung läuft»). It is not a monitoring of work: it is for this session, agreed with the person beforehand, and switched off afterwards.

**The comparison.** Two tasks of the same kind on synthetic or redacted files the person has not seen: one done the way it is done today, timed by the observer with a stopwatch from opening the file to the letter being ready to send and the note written; one done with CasePath, timed by CasePath from opening the case to «Versandt am». Which task is done which way is decided by a coin before the session; a second person gets the other order. Reading time counts on both sides. Waiting for a preparation is noted separately (the person may do something else meanwhile) and reported beside the active time, not hidden in it.

**The rule, fixed in advance.** CasePath counts as faster on a task only if its active time is below the time of today's way on the task of the same kind, for both persons. A letter of which more than a fifth is the person's own wording counts as not prepared: its time is reported, and the task counts against CasePath. One session with two persons shows a direction, not a saving: the numbers are reported as they are, with the two tasks named, and no percentage is derived from them.

**What is not claimed.** Nothing about cases of other legal areas, nothing about a whole working day, and nothing about quality: a letter's legal content is judged by a jurist, not by a stopwatch.
