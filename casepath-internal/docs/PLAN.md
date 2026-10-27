# Build plan: the CasePath of the demo film, inside Mobiliar

The goal is a CasePath that the Protekta team finds genuinely useful on real cases, running on Mobiliar's internal resources. This plan maps each of Navish's five requirements to how it is built and how it is proven.

## 1. The product of the demo film

The internal application has the film's workspace:
- the five-role header;
- a case opener with the problem;
- a file rail with file-type icons, previews and "proof for question N";
- the question checklist and document checks, each with its exact sentence highlighted;
- rule checks, a plain answer and a reply draft that is never sent;
- photo reading;
- the Knowledge shelf and map.

The difference from the film: everything shown is live work on the case at hand, not a replay.

**Proof:** a case worker uses it in internal Edge on a Hackathon case.

## 2. Synthetic cases you cannot tell from real ones

The real Hackathon cases stay inside Mobiliar, so the synthetic cases are made there:

1. **Generate.** For each real case, the internal model writes a new case of the same family with:
   - the same kinds of documents, length, register, timeline shape and messiness;
   - new people, places, dates and amounts.

   Documents are rendered as PDFs with realistic layouts, including scan effects and redaction bars where the real ones have them.
2. **Copy guard.** It rejects any synthetic case that shares long passages, names or numbers with its reference.
3. **Blind judge.** The internal model sees real and synthetic documents in random pairs and guesses which is real. A scorecard reports its accuracy. The target is chance (about 50%).

Only synthetic cases and the judge's scorecard leave Mobiliar. They then serve development, tests and demonstrations anywhere.

**Proof:** the judge's accuracy stays near 50% across families, and a Protekta reviewer cannot tell them apart either.

## 3. Real agents, one model

One deployment, the most capable available, runs every agent. Each agent has its own instructions, its own tools and a fresh context:

| Agent | Does |
| --- | --- |
| **Lead** | Decides who works next. It sends work back when a check fails or a question stays open. |
| **Claim reader** | Reads every file, writes the case brief and records each fact the workflow asks about, with exact quotes. |
| **Process builder** | Builds this case's process: the base workflow from the Hackathon diagrams plus the Knowledge that applies. |
| **Document finder** | Matches each document need to a file and the sentence that proves it, or marks it missing. |
| **Source checker** | Locates every quote word for word, then judges independently whether the quoted text supports the claim. It never sees the other agents' reasoning. |
| **Result checker** | Evaluates the process, gives the answer, the open points and the reply draft, and proposes what should be learned. |

Deterministic code decides what is accepted. A quote must be found in its file. A claim the Source checker does not support is not used. Nothing is sent.

**Proof:** recorded runs on synthetic cases show each agent's work. Content-free scorecards on the real cases show the same behaviour.

## 4. Knowledge that is reused and keeps evolving

Knowledge items are learned document needs, questions and notes for a case family. Each item records:
- its condition;
- its evidence (case, file, quote);
- a version history;
- use statistics: used, confirmed, contradicted.

The Process builder applies active items to every new case where their condition holds, and the case shows which item added what. After each case, the Result checker proposes:
- new items;
- refinements, as a new version;
- contradictions, when a reused rule did not hold.

A person activates them. Items that keep being contradicted are flagged for retirement. The Knowledge map shows this history from real data.

**Proof:** a later case of the same family gets a document need learned from an earlier one. The item's statistics and version history change over a sequence of cases.

## 5. Process graph edits with real consequences

A Protekta employee can edit a node in the case's process:
- add or remove a document need;
- change when a document is required;
- add a question;
- redirect a branch.

The edit is validated, recorded with its author and reason, and can be undone. The case is evaluated again at once:
- the checklist changes;
- a new document need is checked against the existing files by the Document finder and Source checker.

The employee can also choose **Use for similar cases**. The edit then becomes a Knowledge item, which reaches the next cases of that family.

**Proof:** after an edit, the case's document checklist and next actions change. After **Use for similar cases**, the next case of that family shows the same need, attributed to the edit.

## How the work is split

- **Cloud build session.** Writes all code and tests, using synthetic fixtures and scripted model turns.
- **Internal workspace.** Real model runs, synthetic-case generation, the blind judge and evaluation on the real cases.
- **Mac bridge.** Only internal reads, and the few steps that need Navish's sign-in or approval.

See [COORDINATION.md](COORDINATION.md).

## Order

1. **Agents.** Real agents with the lead, plus the case graph with edits and evolving Knowledge. Cloud; tested with scripted turns.
2. **Workflows.** The workflow catalogue from the Hackathon diagrams, kept inside Mobiliar.
3. **Internal runtime and first runs.** The workspace or another approved internal runtime, a model check, then first real-model runs on synthetic cases.
4. **Synthetic pipeline.** Generation, the copy guard and the blind judge, run inside Mobiliar.
5. **UI.** The film's workspace UI on this API.
6. **Review.** Evaluation on the real cases, and review with Protekta experts.
7. **Operated hosting.** Hosting with Mobiliar sign-in, after approval.
