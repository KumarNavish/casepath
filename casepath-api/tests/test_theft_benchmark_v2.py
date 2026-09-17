import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "research/casepath/theft_benchmark_v2.py"
spec = importlib.util.spec_from_file_location("theft_benchmark_v2", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_either_alternative_receives_full_credit():
    acceptable = [["+receipt"], ["+valuation"]]
    selected, score = module.best_realization({"+receipt"}, acceptable)
    assert selected == {"+receipt"}
    assert score["f1"] == 1.0


def test_predicting_both_alternatives_is_penalized():
    acceptable = [["+receipt"], ["+valuation"]]
    _, score = module.best_realization({"+receipt", "+valuation"}, acceptable)
    assert score["tp"] == 1
    assert score["predicted"] == 2
    assert score["gold"] == 1
    assert score["f1"] == 2 / 3


def test_built_benchmark_preserves_route_alternatives_and_shortcut_gate():
    benchmark, preflight, amendment = module.build()
    pair = next(pair for pair in benchmark["pairs"]
                if pair["scenario"] == "PR_scheduled_valuable_1000")
    assert len(pair["acceptable_signed_deltas"]) == 2
    assert all(len(option) == 1 for option in pair["acceptable_signed_deltas"])
    assert preflight["admission"]["input_free_control_pass"]
    assert preflight["admission"]["target_diversity_pass"]
    assert amendment["hidden_pairs_opened_before_amendment"] == 0
