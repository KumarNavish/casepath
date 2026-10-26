# Cold-viewer response

A fresh reviewer, with no task history, received only the 24 evenly spaced
frames listed in [frames.json](frames.json), taken from the 163.2 s cut that
introduced the concept header, the checklist shelf and the knowledge map. Its
brief: a nontechnical insurance executive watching a silent product video. It
was asked what it understood, what it would remember, and what was unclear,
fake, unfinished or inconsistent. Its structured response is kept verbatim
below; the receipt says which points were fixed.

---

## What it understood

CasePath is a case-handling assistant for legal protection insurance. A customer writes in with documents. In the main example, a tenant sends an email, a rent increase form, the lease with the original notice, and a later email from the landlord. CasePath then takes a "checklist" for this kind of case (here, rent increases) from its stock of checklists learned on earlier cases. It turns that checklist into three questions: what did the tenant receive, did the landlord give reasons, and is the increase valid. It goes through each document, highlights the sentence that answers each question, and ticks off the evidence it needed. It then lists five checks with pass or fail. One fails because no reasons were given. From that it suggests "the increase is not valid", flags what is still open, and drafts a reply that a person has to review. Nothing is sent automatically. It can also read a photo: it marked mold spots and read the date the photo was taken. A new, similar case reuses the same checklist. The closing screen claims 3 checklists covering 9 cases and 15 uses.

## What it would remember

Every answer points to the exact highlighted sentence in the customer's own documents that proves it, and a person always makes the final decision. The idea of a checklist that is learned once and reused on later cases is a close second.

## Problems

- **Frame 2 (customer email header: 'Protekta Rechtsberatung <fallaufnahme@protekta.ch>')** (blocker)
  - Problem: The 'made-up' case is addressed to what looks like a real Swiss legal protection insurer's name and domain. That contradicts the 'made-up customers and cases' footer and would worry any insurance viewer, legally and reputationally.
  - Suggested fix: Replace it with an obviously fictional insurer name and domain, for example 'Example Legal Protection <claims@example.ch>'.
- **Top header, all frames (active tab by frame: 1-2 none, 3-5 Process builder, 6-8 Document finder, 9 Process builder, 10-11 Source checker, 12-13 Process builder, 14-16 Result checker, 17-18 Claim reader, 19-23 Process builder, 24 none)** (major)
  - Problem: The five tabs are never explained. The highlighted tab jumps back and forth instead of moving left to right. The same activity, checking a question against a document, sits under three different tabs: Document finder (frames 6-8), Process builder (frames 9, 12-13) and Source checker (frames 10-11). 'Claim reader' is not lit when the customer's message is first read (frame 2) and only lights up for the photo (frames 17-18). The Knowledge screen (frames 21-23) sits under 'Process builder'. I could not tell whether the tabs are steps, assistants or menu pages.
  - Suggested fix: Order the tabs in the story's sequence (read, plan, find, check, answer) and have exactly one tab light up per step, moving left to right. Use one tab per activity, light 'Claim reader' in frame 2, and say once that each tab is one assistant. Otherwise, hide the tab highlighting during the film.
- **Frame 2** (major)
  - Problem: The first real look at the product is a German email that starts mid-sentence ('Nachfrage kam eine E-Mail...'), with a machine timestamp '2025-11-24T12:00:00+01:00'. An English-speaking executive cannot follow it, and there is no caption card to help.
  - Suggested fix: Show an English translation, or a one-line English summary above the original. Start at the beginning of the message, show the date as '24 Nov 2025', and add a caption card.
- **Frames 6-13 (question order) and the progress counters** (major)
  - Problem: The checks run Q2, then Q3, Q1, Q2 and Q3 again, so the film seems to repeat itself. The progress indicators disagree: frame 9 says 'Evidence checklist 3 of 3 checked' while the stepper shows Q1 still 'Checking' and Q2 and Q3 empty. In frames 10-11, three of three are ticked on the left while the right panel shows nothing done.
  - Suggested fix: Check Q1, then Q2, then Q3, once each, and update all three indicators (stepper, left checklist, right panel) together.
- **Frame 6 (caption 'It finds the exact sentence that proves it')** (major)
  - Problem: While checking 'Did the landlord give reasons?', the highlighted sentence is the lease description (address, rent, notice period). It proves nothing about reasons, so the proof claim looks fake at its first appearance. The bottom cards already show 'The documents say yes/no' before the check is done, joined by an unexplained '+'.
  - Suggested fix: Show the lease sentence under Q1, where it belongs, and keep the 'no reasons' sentence from frame 11 for Q2. Reveal the yes/no result cards only after each check completes, and drop the '+' or label it ('and').
- **Frame 10** (major)
  - Problem: A half-faded caption card ('03 · THE CHECKS The key question: did the landlord give reasons? The assistant searches the documents') overlaps the document text. It looks like a rendering glitch.
  - Suggested fix: Fully remove the previous caption before the next scene, or cross-fade over a solid background so text never overlaps text.
- **Frame 16 (Draft reply)** (major)
  - Problem: The 'reply to the customer' is the internal legal sentence again ('omitted substantive reasons, supporting invalidity under CO 269d(2)(b); the later market reply remains contextual evidence'). It has no greeting and no plain language, and no customer would understand it. The header lines are crammed together without hierarchy: 'Original draft. Not sent — you decide.' and 'Review and complete...' sit on top of 'Draft reply'.
  - Suggested fix: Show a real plain-language customer letter (greeting, what we found, what happens next) and keep the legal citation in a footnote. Lay out the header as a 'Draft reply' title followed by a single 'Not sent – a person reviews first' badge.
- **Frames 21-23 (Knowledge counters)** (major)
  - Problem: The '15 uses' total across 9 cases does not match the picture, which shows 3 checklists each reused twice (6 links). The number looks inflated. Frame 21 also reads '1 cases'.
  - Suggested fix: Make the counters match what is drawn, or explain what a 'use' is (for example 'each question answered'). Fix the plural to '1 case'.
- **Frames 14-15 (Answer list)** (minor)
  - Problem: Each check has an unexplained circled number (2, 2, 2, 3, 3). No check belongs to question 1, even though Q1 was 'answered'. Jargon remains: 'CO 269d(2)(b)', 'contextual evidence', 'staged rent'. In frame 15 the caption hides the 'All documents checked. Please re...' banner.
  - Suggested fix: Label the numbers ('Question 2'), or group the checks under their question and include Q1. Put the plain-language reason first and the law reference in small print. Move the caption so it does not cover the banner.
- **Frame 4** (minor)
  - Problem: The spotlight frames a large, mostly empty white box holding a single pill ('What did the tenant receive?'). The caption says 'Each circle is one question', but no circles are visible yet, and the card covers the 'Learned from...' line.
  - Suggested fix: Show the caption only after all three question circles have drawn, place it so it covers nothing, and shrink the spotlight to the content.
- **Frames 5 and 20 (Evidence this case needs)** (minor)
  - Problem: The lease is listed 'For question 2: Did the landlord give reasons?', which makes no sense to a layperson. No evidence is listed for question 1.
  - Suggested fix: Map the lease to question 1 (what the tenant received), or explain why it matters for question 2.
- **Frames 6-13 (document dates)** (minor)
  - Problem: 'The landlord's later email' is dated 21.11.2025, but the 'Lease and original notice' document is dated 25.11.2025, so the 'later' email appears earlier. The dates are hard to follow.
  - Suggested fix: Show each document's own date (notice 18 Nov, landlord email 21 Nov, customer email 24 Nov) and use one date format throughout.
- **Frames 17-18 (Photo scene)** (minor)
  - Problem: The case switches to mold without any lead-in caption (frame 17). A red bar sits across the top of the photo like a glitch, and the photo is listed with a document icon. The finding, 'Dark spots found', is underwhelming and never connects to an answer or decision. The pink circles look cluttered.
  - Suggested fix: Add a lead-in caption ('Photos too'), remove the red bar or animate it clearly as a scan, and use a photo icon. Say what the finding means for the case, for example 'Mold visible near floor; photo dated before the report'. Use one outline instead of dozens of circles.
- **Frames 19-20 (06 · The next case)** (minor)
  - Problem: The new case is titled 'An increase form and the later email chronology', which is nearly identical to the previous case and uses jargon ('chronology'). The film stops at the checklist and never shows this case getting its own answer, so 'Its facts come from its own documents' is asserted but not shown.
  - Suggested fix: Give the new case a clearly different, plain name, and show its answer card in two or three seconds to prove the reuse produced a result.
- **Frame 22** (minor)
  - Problem: A stray dot and a short dangling line segment appear near 'An increase form with missing original reasons'. These are animation leftovers.
  - Suggested fix: Draw the lines fully before showing the endpoint dots, or hide partial strokes.
- **Frame 23** (minor)
  - Problem: The arcs from 'FIRST CASE' loop over the labels, the double rings crowd the case names (text touches the rings), and the screen feels busy.
  - Suggested fix: Remove the first-case arcs (the dashed line is enough), use single rings, and add spacing between the rings and the text.
- **Overall** (major)
  - Problem: I never learn the business value: time saved per case, how accurate it is, or what it costs. The video answers the tenant's legal question (is the rent increase valid?), but the header says 'Claim reader'. It is unclear whether this decides insurance cover or gives legal advice.
  - Suggested fix: Add one line at the start or end stating the job (for example 'prepares the legal assessment for a legal protection case handler') and one measured benefit (minutes per case or similar).
- **Frames 1, 3-15, 19-20 (grey dimming)** (minor)
  - Problem: Heavy grey dimming covers most of the screen in many frames, so the product looks dull, and the floating caption cards often cover the content being described (frames 7, 11, 12, 14).
  - Suggested fix: Use lighter dimming and anchor the caption cards in empty space or a fixed caption bar.
