# CasePath

CasePath reads the customer's message and files, shows where the claim stands, and helps the handler ask for what is missing.

![Family-home claim with linked findings, the current path, and sources](docs/images/workbench-review.png)

*The two notices give different end dates; the receipt dates remain a question. This walkthrough uses a synthetic claim.*

## See one claim

The **Claims** list groups work by who CasePath is waiting for. Each row says what it noticed and what to do next. Select **Walk through this claim** above the list, or open `#claim=clm_f69b1747447bc221`.

Select **Review claim**. Findings appear in **What I noticed** as the review runs. The two end dates link to their exact PDF spans, and **Sources** stays beside the claim on desktop. **Where it stands** shows the done step, the current step, and the next step. Expand **+8 later** for the rest of this path. The conditions and their source quotes sit below the steps.

**Questions** asks for the two receipt dates and explains what each unresolved condition would change. **What to request** separates what is needed now, later, and on no active path. Focus family-home service, select **what if**, and set it false to see the spouse-notice request leave the sandbox path. Exit to return to the saved assessment.

Select **Draft request** to open an editable letter with the questions, reasons, and articles. It is labelled **Draft, not sent**; **Copy** and **Export** are beside **Save edits**. [About CasePath](casepath/method.html) has the **Reviewer mode** switch, the [data](casepath/corpus.html), and the [research results](casepath/research.html).

![Claims list with the first-run walk and waiting groups](docs/images/workbench-queue.png)

The paper's Study A method is installed as a separate service. It uses the frozen source pack, guard interpreter and document planner. With recorded guard answers, its [replay matches all 72 paper cases and 36 paired changes](research/casepath/branch-benchmark/parity/PRODUCT_METHOD_PARITY_V5.json). The workbench's assessment and review are separate product behavior. The earlier authored teaching record remains downloadable from [About CasePath](casepath/method.html). The studies' measured results stay separate from the workbench.

## Run it locally

Download or clone the repository, enter its root, then run:

```sh
./bin/casepath prepare
./bin/casepath dev
```

Open the address printed by the server. The first `prepare` installs pinned Python 3.13.9 dependencies, so it needs internet access. Local use after preparation needs no provider account, API key, database service, or paid infrastructure. You also need Git, `uv`, `lsof`, and `lockf` on macOS or `flock` on Linux. Stop the server with Ctrl-C. Saved claim and review state stays in `.runtime/casepath-data-v1`; use a fresh clone for disposable tests. [Setup](docs/setup.md) covers replay, export, safe reset, and platform details.

```sh
./bin/casepath test
./bin/casepath replay <claim-id>
```

## What the release contains

| Start here | What you will find |
| --- | --- |
| [Claims workbench](casepath/README.md) | Claim-specific queue, verified sources, live review, path and needs, What if, drafts, reviewed memories, and replay. |
| [150-claim data card](docs/INTAKE_PACKET_150.md) | Original intake inputs, attachment counts, schema, license, integrity checks, and limits. |
| [About CasePath](docs/method-guide.md) | A live claim walkthrough, data and research links, and the preserved teaching record. |
| [Research evidence](docs/research-evidence.md) | Measured results, adverse findings, costs, and exact provenance. |
| [Paper and reproduction](research/casepath/iclr2027-integrated/README.md) | Manuscript, numerical audit, figures, benchmark outputs, and offline verification. |
| [Developer documentation](docs/README.md) | Setup, source authority, API contracts, recovery, and contribution rules. |

## What was measured

The paired branch study changes one case fact at a time. On 27 held-out pairs, CasePath made 15 unjustified signed document changes, versus 27 for Direct, 41 for Graph as context, and 52 for Evidence-first. It recovered 24 of 33 required changes; Direct recovered 25 and Graph as context 31. This is a selectivity result with a recall trade-off. The registered broad-superiority gate failed, and the historical arms used unequal computation.

The complete 150-claim study preserved its original native graph-interface failure. A separate retrospective current-case comparison found that inherited process scope reduced requests while retaining the same valid requests in the completed development subset. It does not turn the failed registered comparison into a success or establish counterfactual branch correctness. [Read the study definitions and exact results](docs/benchmark-and-baselines.md) before comparing numbers across studies.

Reproduce the released checks offline, without new inference:

```sh
python3 research/casepath/verify_release.py
```

The paper build also needs Tectonic, Matplotlib and SciencePlots. Put `tectonic` on `PATH`, or set `CASEPATH_TECTONIC` to its executable. The verifier reports any missing tool or failed check; it never calls a model.

The local workbench and deterministic review demonstrate product mechanics, not legal correctness or general model quality. The current hosted Render services use an older source line; this repository's verified experience is the local one.

## Go deeper

- [How claim state is authorized](docs/architecture-authority.md)
- [Agent review and its verified external-worker boundary](docs/AGENT_REVIEW.md)
- [Contribution and source-sealing rules](CONTRIBUTING.md)
- [License](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md)
