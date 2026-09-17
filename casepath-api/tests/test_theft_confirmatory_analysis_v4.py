import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "research/casepath/theft_confirmatory_analysis_v4.py"
spec = importlib.util.spec_from_file_location("theft_analysis_v4", MODULE_PATH)
analysis = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(analysis)


def pair(pair_id, family, options, context=0):
    return {"pair_id": pair_id, "scenario": family, "context_index": context,
            "acceptable_signed_deltas": options}


def row(pair_id, prediction, arm=None, attributed=None, chainable=None):
    value = {"pair_id": pair_id, "predicted_signed_delta": prediction}
    if arm:
        value["arm"] = arm
    if attributed is not None:
        value["chain_attributed_predicted"] = attributed
    if chainable is not None:
        value["chain_attributable_gold_atoms"] = chainable
    return value


def test_best_realization_accepts_either_route_but_penalizes_both():
    target = pair("p", "f", [["+receipt"], ["+valuation"]])
    selected, one = analysis.best_realization(["+receipt"], target)
    assert selected == {"+receipt"}
    assert one["f1"] == 1.0
    _, both = analysis.best_realization(["+receipt", "+valuation"], target)
    assert both["f1"] == 2 / 3
    assert both["predicted"] == 2 and both["gold"] == 1


def test_route_aware_micro_score_and_exact_rate():
    pairs = {
        "p1": pair("p1", "a", [["+receipt"], ["+valuation"]]),
        "p2": pair("p2", "b", [["+photo"]]),
    }
    result = analysis.score([
        row("p1", ["+valuation"]),
        row("p2", ["+wrong"]),
    ], pairs)
    assert result["tp"] == 1
    assert result["predicted_atoms"] == 2
    assert result["gold_atoms"] == 2
    assert result["micro_f1"] == 0.5
    assert result["exact_rate"] == 0.5
    assert result["selected_gold_realizations"]["p1"] == ["+valuation"]


def test_chain_metrics_use_selected_acceptable_route():
    pairs = {"p": pair("p", "a", [["+receipt"], ["+valuation"]])}
    rows = [row("p", ["+valuation"], attributed=["+valuation"],
                chainable=["+receipt", "+valuation"])]
    rows[0]["all_requests_source_chained"] = True
    result = analysis.chain_metrics(rows, pairs)
    assert result["predicted_attribution_rate"] == 1.0
    assert result["gold_chain_coverage"] == 1.0
    assert result["all_requested_documents_have_source_chains"]


def test_exact_family_swap_uses_route_aware_pair_f1():
    pairs = {
        "p1": pair("p1", "a", [["+receipt"], ["+valuation"]]),
        "p2": pair("p2", "b", [["+photo"]]),
    }
    b5 = [row("p1", ["+receipt"]), row("p2", ["+photo"])]
    baseline = [row("p1", []), row("p2", [])]
    result = analysis.exact_family_swap(b5, baseline, pairs)
    assert result["assignments"] == 4
    assert result["observed_mean_difference"] == 1.0
    assert result["one_sided_p"] == 0.25
