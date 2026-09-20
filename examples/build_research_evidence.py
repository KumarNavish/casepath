#!/usr/bin/env python3
"""Render the public paired-study summary without inference or target access."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "casepath/assets/paired-study-evidence.json"
PAGE = ROOT / "casepath/research.html"
RESULT_SHA256 = "b0609c213e985db423119d6ee498948bea303ae906759abeaa22f863463d1f47"
ARMS = {
    "b5_process_compiled": "CasePath V5",
    "b1_direct": "Direct",
    "b3_representation_then_list": "Graph as context",
    "b6_evidence_first": "Evidence-first",
}


def export_summary(result_path: Path, costs_path: Path) -> dict:
    raw = result_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RESULT_SHA256:
        raise ValueError("Expected the authenticated frozen V5 result; refusing a substitute.")
    result = json.loads(raw)
    costs = json.loads(costs_path.read_text())
    arms = []
    for key, label in ARMS.items():
        score = result["scores"][key]
        arms.append({
            "id": key, "label": label,
            **{k: score[k] for k in ("tp", "spurious_atoms", "missed_atoms", "gold_atoms", "predicted_atoms", "pairs", "precision", "recall", "micro_f1", "exact_rate")},
            "exact_pairs": round(score["exact_rate"] * score["pairs"]),
            "f1_interval": result["cluster_bootstrap"]["arms"][key],
            "calls": costs[key]["receipts"], "cost_usd": costs[key]["cost_usd"],
        })
    return {
        "schema": "casepath.public-paired-evidence/1", "study": "theft-method-freeze/5.0.0",
        "scope": "Signed document changes on 27 held-out pairs within nine known branch concepts. Separate from native150 and the teaching guide.",
        "source_result_sha256": RESULT_SHA256,
        "source_cost_summary_sha256": hashlib.sha256(costs_path.read_bytes()).hexdigest(),
        "historical_archive_sha256": "e3656756d673e66e335ba3137d47b4b6eb765b4bfc4eb6ff7aed61e79905bcd3",
        "analysis_reproduction": "Byte-identical replay of the original analysis; zero new model calls.",
        "arms": arms,
        "bootstrap": {k: result["cluster_bootstrap"][k] for k in ("draws", "seed", "unit")},
        "b5_minus": result["cluster_bootstrap"]["b5_minus"],
        "broad_superiority_gate_passed": result["gate_pass"],
        "positive_claim_gates": result["positive_claim_gates"],
        "native150_performance_included": False,
    }


def render(data: dict) -> str:
    if data["source_result_sha256"] != RESULT_SHA256 or data["native150_performance_included"]:
        raise ValueError("Incompatible evidence scope")
    bars, rows = [], []
    for a in data["arms"]:
        if a["tp"] + a["spurious_atoms"] != a["predicted_atoms"] or a["tp"] + a["missed_atoms"] != a["gold_atoms"]:
            raise ValueError("Inconsistent signed-change counts")
        selected = " selected" if a["id"] == "b5_process_compiled" else ""
        name = html.escape(a["label"])
        bars.append(f'<div class="comparison-row{selected}"><h3>{name}</h3><div class="bar-cell"><span class="bar-track"><span class="bar" style="width:{a["spurious_atoms"]/52*100:.6f}%"></span></span><b>{a["spurious_atoms"]}</b></div><div class="missed"><b>{a["missed_atoms"]}</b><span>missed</span></div></div>')
        ci = a["f1_interval"]
        rows.append(f'<tr class="{selected.strip()}"><th scope="row">{name}</th><td>{a["tp"]}/33</td><td>{a["spurious_atoms"]}</td><td>{a["missed_atoms"]}</td><td>{a["micro_f1"]:.2f} <span class="interval">[{ci["low"]:.2f}, {ci["high"]:.2f}]</span></td><td>{a["exact_pairs"]}/27</td><td>{a["calls"]}</td><td>${float(a["cost_usd"]):.2f}</td></tr>')
    return '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The evidence — CasePath</title><meta name="description" content="The measured paired-study result: fewer spurious document changes, with a recall trade-off. Exact counts, uncertainty and provenance.">
<link rel="icon" href="data:,"><link rel="stylesheet" href="assets/method-guide.css"><link rel="stylesheet" href="assets/research-evidence.css"></head>
<body><a class="skip" href="#comparison">Skip to the comparison</a>
<header><a class="brand" href="/" aria-label="CasePath claims workspace"><span class="mark">C</span>CasePath</a><nav aria-label="Main navigation"><a href="method.html">How it works</a><a href="/" class="workspace-link">Open workspace ↗</a></nav></header>
<main>
<section class="evidence-intro"><p class="eyebrow">The paired study · 27 held-out pairs</p><h1>Fewer spurious changes.<br>A clearer trade-off.</h1><p class="lead">Change one branch-defining fact. Which document requests should change with it? CasePath V5 made fewer unjustified changes than three comparison systems, while missing more required changes than two of them.</p></section>
<section id="comparison" aria-labelledby="comparison-title"><div class="section-heading"><h2 id="comparison-title">12 fewer spurious changes.<br>One fewer required change recovered.</h2><p>CasePath V5 versus Direct · all 27 held-out pairs · 33 reference changes</p></div>
<div class="comparison" role="group" aria-label="Spurious and missed signed document changes"><div class="comparison-heading"><span>Method</span><span>Spurious changes ↓</span><span>Missed changes ↓</span></div>
''' + "\n".join(bars) + '''</div>
<p class="chart-note">A spurious change is an unjustified addition <em>or withdrawal</em>. These counts measure changes between paired checklists, not extra documents requested in complete claims.</p>
</section>
<section class="interpretation"><div><p class="eyebrow">What the result establishes</p><h2>Selective, not universally better.</h2></div><div><p>CasePath recovered 24 of the 33 reference changes; Direct recovered 25. Graph as context recovered 31, but made 41 spurious changes. The useful finding is a trade-off between recovering required changes and avoiding unjustified ones.</p><p>The frozen broad-superiority test failed. CasePath had the highest point F1 and precision, but its paired F1 intervals against Direct and Graph as context include zero. A lower false-positive count is a measured result; universal superiority is not.</p></div></section>
<section aria-labelledby="measurements-title"><div class="section-heading"><h2 id="measurements-title">The complete comparison.</h2><p>Read accuracy and inference cost together. All four conditions are shown.</p></div>
<div class="table-scroll" tabindex="0" role="region" aria-label="Paired-study measurements; horizontally scrollable on small screens"><table><caption>Signed-change accuracy and held-out inference cost</caption><thead><tr class="groups"><th rowspan="2" scope="col">Method</th><th colspan="5" scope="colgroup">Paired change accuracy</th><th colspan="2" scope="colgroup">Inference cost</th></tr><tr><th scope="col">Recovered ↑</th><th scope="col">Spurious ↓</th><th scope="col">Missed ↓</th><th scope="col">F1 [95% interval] ↑</th><th scope="col">Exact pairs ↑</th><th scope="col">Calls</th><th scope="col">USD</th></tr></thead><tbody>
''' + "\n".join(rows) + '''</tbody></table></div>
<p class="chart-note">Intervals use 10,000 bootstrap draws over nine branch concepts. Exact means that the entire signed change set matches a permitted reference. Charges come from preserved provider receipts and exclude source preparation and development.</p>
<details class="evidence-details"><summary>What was — and was not — matched?</summary><p>All arms used the recorded <code>openai/gpt-5.6-terra</code> alias, OpenAI provider restriction and temperature zero. The receipts do not independently attest a dated backend checkpoint. Retrieval, context and computation differed: Direct received sources; Graph as context also received the process and evidence representation; Evidence-first retrieved twelve passages by keyword. CasePath assessed source guards and projected requests in code.</p><p>Direct and Graph as context allowed 14,000 completion tokens per call. Evidence-first allowed 18,000 for extraction and 14,000 for planning; CasePath allowed 10,000 per guard batch. This is a comparison of those implemented pipelines, not an equal-compute test or a reproduction of a named published agent.</p></details>
</section>
<section class="study-scope" aria-labelledby="scope-title"><div class="section-heading"><h2 id="scope-title">Keep the questions distinct.</h2><p>The paper, repository and app use these same evidence boundaries.</p></div>
<div class="scope-grid"><article><span class="eyebrow">Study A · Paired interventions</span><h3>Does a branch change alter the right requests?</h3><p>The result above comes from 27 held-out theft pairs after nine development pairs. Splits share the nine branch concepts. V5 uses local guards and unions mapped document routes; its macrograph does not gate requests.</p></article><article><span class="eyebrow">Study B · Complete native corpus</span><h3>Is the whole evidence plan useful?</h3><p>The separate tenancy benchmark contains 150 claims: 60 development and 90 in family-disjoint protected custody. Its newer controller separates applicability, acquisition permission and evidence adequacy. This page reports no native150 performance.</p></article><article><span class="eyebrow">Interactive method guide</span><h3>What changes when the case state changes?</h3><p>The <a href="method.html">teaching example</a> runs authored repair states through the newer deterministic controller. It explains behavior; it is not a benchmark case or a model-quality result.</p></article></div></section>
<section class="provenance"><h2>Follow the evidence.</h2><p>The original analysis was rerun from preserved outputs and reproduced the frozen result byte for byte. The data below contains all four aggregate results, interval and cost fields, failed gates and source hashes. It contains no current protected labels.</p><a class="button" href="assets/paired-study-evidence.json" download>Download the measured comparison ↓</a><details class="evidence-details"><summary>Inspect the original result identity</summary><code class="digest">''' + RESULT_SHA256 + '''</code><p>SHA-256 of the preserved V5 result. This is the same result used for the manuscript’s paired-study figure and table. Recorded-decision product replay is separate from fresh model inference and deployment parity.</p></details></section>
</main><footer><span>CasePath · Research evidence</span><span>Source → process → obligation → fact → evidence → document → action</span></footer></body></html>
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--costs", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if bool(args.result) != bool(args.costs):
        parser.error("--result and --costs must be supplied together")
    data = export_summary(args.result, args.costs) if args.result else json.loads(DATA.read_text())
    output = render(data)
    if args.check:
        if args.result and data != json.loads(DATA.read_text()):
            raise SystemExit("Measured summary differs from authenticated outputs")
        if output != PAGE.read_text():
            raise SystemExit("Evidence page is stale")
        print("Paired evidence and generated page verified; no provider or target access.")
    else:
        DATA.write_text(json.dumps(data, indent=2) + "\n")
        PAGE.write_text(output)


if __name__ == "__main__":
    main()
