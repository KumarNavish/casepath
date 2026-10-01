---
version: alpha
name: CasePath
description: Visual language for the synthetic claims workbench
colors:
  cp-ink: "#1c2430"
  cp-muted: "#5b6675"
  cp-line: "#e3e7ec"
  cp-accent: "#244e72"
  cp-amber: "#9a6b1f"
---

## The screen

CasePath reads the customer message and files, shows where the claim stands, and helps the handler ask for what is missing. The **Claims** screen is a list grouped by who it is waiting for. Each row carries a noticed fact and a next step. Search is visible; the other controls open from **Filter**.

An open claim reads as one document. The next step comes first, followed by **What I noticed**, **The path behind this claim**, **Questions**, **What to request**, and an editable draft when one exists. **Why** opens beneath the next step. **Source review record**, **Timeline**, and **Technical details** sit at the end of the document.

At desktop widths, a 280 px **Sources** rail stays on the right. Selecting a fact, quote, or file opens its source in that rail. At 900 px and below, **Sources** opens as a sheet and the next action stays in a bottom bar.

## Type and color

Use the system sans serif, sentence case, and short handler words. The claim title and next step carry the strongest weight. Source quotes retain the customer's words and language. Links and the primary action use `cp-accent`; unresolved questions and conflicts use `cp-amber`. Text always names the state alongside its color.

Keep the page white. Separate sections with space and the source rail with one thin rule. Source rows are plain text rows. The queue uses list rows with no table headers or chevrons.

## Behaviour

**Review claim** reveals findings in place and highlights the matching source span. The completed review renders from saved evidence. **The path behind this claim** is an executable step-and-dependency view with an adjacent inspector. Selecting a step reveals its condition, current execution state, document origins, connections and granular validation. Readiness, completion, structural validation and source sufficiency remain distinct.

Edits, validations and source reviews always show a server-calculated impact before saving. Show semantic changes even when runtime state stays the same. Preserve entered fields after a failed preview. Keep detailed history and reusable versions in disclosures. A fragment distinguishes the version applied to this claim from the newest available version; upgrades are explicit. Never imply a completed process authorizes a claim outcome.

**Questions** states what each unresolved condition would change. **What to request** groups documents under **Now**, **Later**, and **Not needed**, with a short reason and article where one applies. A held file reads **held, not reviewed**. The draft is a letter edited in place and labelled **Draft, not sent**; Copy and Export follow Save edits. Reviewed memory shows who reviewed it and requires an explicit Apply.

Use native buttons and disclosures with visible keyboard focus. Motion belongs to the live finding and source highlight; reduced-motion preference disables it. Keep candidate deadlines tied to an anchoring date or a question. A source passage becomes an accepted observation only after it is recorded against the claim.

## Screen references

- [Claims list](docs/images/workbench-queue.png)
- [Reviewed claim at 1440 px](docs/images/workbench-review.png)
- [Reviewed claim at 390 px](docs/images/workbench-mobile.png)
