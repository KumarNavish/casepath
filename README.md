# CasePath

CasePath helps a claims handler read a claim, see its current step, ask for the right information, and draft the request. The original message and files stay beside the path and the reasons for each need.

The local workbench opens all 150 synthetic intake claims. It keeps source files, recorded observations, proposed work, and accepted handling events separate. Its default review is deterministic and makes no model API calls.

![CasePath workbench showing original sources, claim path, needs, and next step](docs/images/workbench-review.png)

*The synthetic family-home claim after review. The two notices give different end dates. The receipt dates remain a question. This product example is not a benchmark result.*

## See one claim

Open the app and select **Walk through this claim** on the first-run card, or open `#claim=clm_f69b1747447bc221`. Read the message and the two PDFs in **Sources**. Select **Review claim** and follow the anchored lines until the summary appears.

The path then shows **Preserve challenge or extension deadline** as active. **What this claim needs** asks for both receipt dates and shows the two notices as held, not reviewed. Select **What if** beside family-home service and set it false. The sandbox removes the spouse-notice route; leaving the sandbox restores the saved assessment. Select **Draft request** to create a source-bound request labelled **Draft, not sent**. You can edit, copy, or export it. Nothing is sent to the customer.

Use **Reviewer mode** to see provenance labels on the sources, assessment, handler observations, memories, and draft, along with the studies' correspondence table. [About CasePath](casepath/method.html) links into this claim's What if and gathers the [data](casepath/corpus.html) and [research results](casepath/research.html).

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
