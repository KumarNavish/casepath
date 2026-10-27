# Workspace UI: north-star self-review

The internal workspace (`casepath_internal/ui/`) follows the three north-star concepts in `design/northstar/`. Everything on screen comes from the live API: the case store, the agents' recorded events and results, the case process and the Knowledge base. Nothing is replayed or staged.

## Fidelity

| Concept | Implemented | Deliberate differences |
| --- | --- | --- |
| **Shell** | Matched:<br>• 75 px top bar with the wordmark and the five agent tabs; the active tab is crimson with an underline<br>• 262 px sources rail with media icons, received dates and an active-row bar<br>• Mulish font and the north-star colour tokens | • A working agent's tab pulses while a run is live<br>• Rail rows add "Proof for questions …" from accepted findings<br>• Image sources show their thumbnail |
| **01: live decision building** | Matched:<br>• question spine with done, building and waiting rings<br>• source card with e-mail header fields and the body in its own lines; the quote being worked on highlighted<br>• "Building “…”" plan with the agent's latest steps<br>• agent hexagon<br>• fact cards (source + finding) | • The plan rows are the agent's real tool steps, not authored labels<br>• No cursor arrow; the highlight scrolls into view<br>• A "located, being checked" spine state was added |
| **02: completed process** | Matched:<br>• numbered step nodes from the case's evaluation path: done (crimson, check), current (ring), waiting (dashed)<br>• branch boxes with the taken branch<br>• **Edit decision** on the selected node<br>• five-column evidence strip with "Documents N missing"<br>• timeline preview with the cited line on yellow | • Nodes are the process steps from the workflow catalogue, so labels are step names, not authored questions<br>• "Basis" replaces "Law"; it lists the workflow's sources |
| **03: edit and memory payoff** | Matched:<br>• BEFORE → NOW with "Edited by &lt;user&gt;"<br>• the documents the edit added, removed or changed, each with its checked status<br>• "Retrieved N Knowledge item(s)", with the earlier case's quote → the Knowledge item (version, use statistics) → the result in this case<br>• notice bar, shown only when Knowledge was applied | • The notice reads "Qualified review is still required" without claiming expert review, which is not recorded<br>• "Edited by" uses the signed-in user |

## Motion

While a run is live, the page polls the run's events every 1.2 s. It follows the working agent's tab without a navigation, so polling continues. It highlights the latest located quote in its source. After a process edit, the re-check run is followed the same way, and the page then shows BEFORE → NOW. Reduced motion stops the spinner and pulse.

## Real function

A headless Chromium pass at 1440×900 on the synthetic preview (`deploy/preview/preview.py`) covered:
- the cases list;
- case A on every tab;
- case B before, during and after a live team run;
- the edit form, the live re-check, BEFORE → NOW, and the Knowledge page.

It showed zero console or page errors. The preview data is synthetic and the model is scripted. A real-model pass needs the internal runtime.

## Pending

- Photo reading, and page images for scanned PDFs.
- The cold-viewer review, after the first runs on the internal model with synthetic Hackathon-like cases.
- Mobile layout. Desktop at 1440 is the target, as in the north star.
