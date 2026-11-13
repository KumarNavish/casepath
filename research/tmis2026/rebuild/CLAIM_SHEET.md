# Claim sheet (gate 1, draft for Navish, 2026-11-13)

**Thesis.** Models read and quote; code decides; what the file leaves open becomes a held request with one question.

Every claim below names its figure, the evidence that exists today, and the evidence that must be produced. "Exists"
means stored and reproducible; the numbers come from the figure drafts' data files. Study 3's figures are for
its 96 sealed tenancy claims unless theft is named.

## Question 1. What happens to a fact the file leaves open?

| # | Claim | Figure | Exists today | Must be produced |
|---|---|---|---|---|
| 1 | With only "true" and "false", a reading must take one branch: it asks for that branch's documents too early or drops the other's. A third value lets code request what both branches need and hold the rest. | 3 | Formal: follows from the definition of the workflow; shown on a real fragment of a public rule set. | Nothing. |
| 2 | One sentence in the file decides one line of the checklist, and the line can be followed back to the quoted words. | 1, 2 | One stored pair of claims, drawn as it is. **Not true in general yet:** in 144 stored theft pair-runs the core changed only the governed line in 12; in 130 another line moved too, because readings of other facts differ between runs. | A fix that makes the same text give the same checklist. Then sealed twins in Study 4: two files one sentence apart, exact and collateral changes counted for every design. |
| 3 | Of 100 requests that depend on an open fact, CasePath holds almost all, each with the right question. A prompt that is not told to hold asks for half of them too early. A prompt that is told holds them too, but then also holds or drops requests the file settles. | 4 | On the cost-efficient model the core holds 99.6 of 100, the plain prompt 48, the prompt that may hold 97 (86 documents in 32 claims). Of 100 settled requests the core gets 96 right, the prompt that may hold 90 (481 documents). **Lost today:** on the frontier model the core holds 87, the prompt that may hold 98. The prompt that may hold ran after the test. | Study 4, with needless holds counted as errors. |

## Question 2. Does CasePath beat the strongest prompt as cases get real?

| # | Claim | Figure | Exists today | Must be produced |
|---|---|---|---|---|
| 4 | CasePath's error holds its level as files get longer, rule catalogues larger and open facts more frequent; the strongest prompt's error rises. | 5, main table | **Nothing that supports this.** Study 3's files have 77 to 320 words. The public-rule benchmark has run no baseline. Today a prompt told the hold rules ties CasePath on tenancy (0.35 against 0.31 strict errors per claim) and beats it on claims that deny their defining event (0.00 against 0.61 on the frontier model). | Three fixes on development data, then Study 4 on fresh sealed files. Every cell is shown, won or lost. |
| 5 | The lead does not cost many times a prompt, and the same file gives the same checklist when run again. | 7 | The core costs about 4 times the prompt that may hold on the same model (USD 0.0030 against 0.0007 per claim) for 0.73 against 0.89 errors; on the frontier model it costs 3.4 times as much and errs more (0.70 against 0.58). As tested it would cost about 40 times that prompt on a 2,500-word file (extrapolated). The same checklist in all three stored runs: 70 of 96 claims for the core. | Fixes to cost (the file read once and reused; supplied documents judged in one call; one reading where it settles the fact). Ten runs of the same file in Study 4. |

## Question 3. What does an organisation gain when its rules change, or when it adds a kind of claim?

| # | Claim | Figure | Exists today | Must be produced |
|---|---|---|---|---|
| 6 | After a rule edit, code recomputes every stored checklist with no model call and changes only the lines the edit reaches. A prompt must read every file again. | 6 | Replay of stored readings under one edited rule: 15 of 421 lines changed in 56 theft files, 14 as the edit requires, no model call. The prompt's side is not measured. | Rule-change experiment: a set of edits; exact changes, collateral changes and model calls for every design. An edit that adds a new fact costs CasePath readings of that fact only; this is measured too. |
| 7 | A new kind of claim is added from public text in six steps by a session that has not seen the system. | table | Three regimes were built this way (177 cited rules); effort was not recorded; first use found 39 wording errors, since repaired. | A fresh session adds a fourth regime; effort is recorded; its sealed result enters Study 4. |
| 8 | The system is small: a workflow is a data file and a new rule is one line; routing; several attachments and scans; presumptions; Knowledge from handler corrections, replayed without a model. | one listing or frame each | In the product at the tested commit. | Frames on synthetic cases, requested from the product session. |

## What the paper does not claim
No claim rests on the hackathon dossiers or the expert study. Studies 1 and 2, the commit timeline and the deviations
list go to the supplement. If a cell of the main table is lost after the fixes, the table shows it and one sentence
says why.
