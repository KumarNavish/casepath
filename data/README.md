# Datasets released with CasePath

Two synthetic datasets, each paired with structured reference answers, released
with the paper *CasePath: An Agentic, Process-First Architecture for Determining
Evidence Requirements*.

| Folder | Study | What it holds |
|---|---|---|
| [`casepath-theft-pairs/`](casepath-theft-pairs/) | A | 36 pairs of household-theft claims that differ in one branch-deciding sentence, with the document changes each pair justifies, built from 197 cited passages of law, policy terms, a claim form and model conditions |
| [`casepath-tenancy-claims/`](casepath-tenancy-claims/) | B | 150 tenancy claims as a claims inbox receives them (message, channel, attachments), each with a reference process graph, obligations, document states, next action and sources |

Each folder has its own datasheet (`README.md`), licence files and a
`verify.py` that checks the evaluated files against recorded hashes, including
the commitments made before the evaluation. The synthetic data is released under CC BY 4.0 and the code under
Apache 2.0; quoted third-party passages keep their own terms, as each folder
explains.
