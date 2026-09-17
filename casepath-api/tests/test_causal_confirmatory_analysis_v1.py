import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "research/casepath/causal_confirmatory_analysis_v1.py"
spec = importlib.util.spec_from_file_location("causal_analysis", MODULE)
analysis = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(analysis)


def row(pair, family, predicted, gold):
    return {
        "pair_id": pair,
        "scenario": family,
        "predicted_signed_delta": predicted,
        "gold_signed_delta": gold,
    }


def test_signed_delta_scoring_is_symmetric():
    result = analysis.score([
        row("p1", "a", ["+x"], ["+x"]),
        row("p2", "b", ["-z"], ["-y"]),
    ])
    assert result["tp"] == 1
    assert result["predicted_atoms"] == result["gold_atoms"] == 2
    assert result["precision"] == result["recall"] == result["micro_f1"] == 0.5
    assert result["exact_rate"] == 0.5


def test_exact_family_swap_uses_family_as_randomization_unit():
    b5 = [row("p1", "a", ["+x"], ["+x"]), row("p2", "b", ["+y"], ["+y"])]
    baseline = [row("p1", "a", [], ["+x"]), row("p2", "b", [], ["+y"])]
    result = analysis.exact_family_swap(b5, baseline)
    assert result["assignments"] == 4
    assert result["observed_mean_difference"] == 1.0
    assert result["one_sided_p"] == 0.25


def test_holm_adjustment_is_monotone_in_sorted_order():
    adjusted = analysis.holm_adjust({"a": 0.01, "b": 0.03, "c": 0.2})
    assert adjusted["a"] == 0.03
    assert adjusted["b"] == 0.06
    assert adjusted["c"] == 0.2


def test_wrong_pairing_is_deterministic_for_equal_family_sizes():
    rows = [
        row("a1", "a", ["+a"], ["+a"]), row("a2", "a", ["+b"], ["+b"]),
        row("b1", "b", ["+c"], ["+c"]), row("b2", "b", ["+d"], ["+d"]),
        row("c1", "c", ["+e"], ["+e"]), row("c2", "c", ["+f"], ["+f"]),
    ]
    first = analysis.wrong_pairing(rows)
    second = analysis.wrong_pairing(rows)
    assert first == second
    assert first["observed_micro_f1"] == 1.0


def test_alternative_gold_route_gets_full_credit_without_rewarding_both():
    alternative = row("p", "a", ["+receipt"], ["+receipt", "+valuation"])
    alternative["acceptable_signed_deltas"] = [["+receipt"], ["+valuation"]]
    result = analysis.score([alternative])
    assert result["micro_f1"] == 1.0
    assert result["precision"] == result["recall"] == 1.0

    over = row("p", "a", ["+receipt", "+valuation"], ["+receipt", "+valuation"])
    over["acceptable_signed_deltas"] = [["+receipt"], ["+valuation"]]
    result = analysis.score([over])
    assert result["micro_f1"] == 2 / 3
    assert result["precision"] == 0.5
    assert result["recall"] == 1.0


def test_benchmark_binding_overrides_legacy_flattened_gold():
    rows = [row("p1", "wrong", ["+valuation"], ["+receipt", "+valuation"])]
    benchmark = {"pairs": [{"pair_id": "p1", "scenario": "branch",
                             "acceptable_signed_deltas": [["+receipt"], ["+valuation"]]}]}
    bound = analysis.bind_benchmark(rows, benchmark)
    assert bound[0]["scenario"] == "branch"
    assert analysis.score(bound)["micro_f1"] == 1.0
