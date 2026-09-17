import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "research/casepath/theft_confirmatory_analysis_v3.py"
spec = importlib.util.spec_from_file_location("theft_analysis", MODULE_PATH)
analysis = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(analysis)


def row(pair, family, predicted, gold):
    return {"pair_id": pair, "scenario": family,
            "predicted_signed_delta": predicted, "gold_signed_delta": gold}


def test_symmetric_delta_score():
    result = analysis.score([
        row("p1", "a", ["+x"], ["+x"]),
        row("p2", "b", ["+z"], ["+y"]),
    ])
    assert result["tp"] == 1
    assert result["predicted_atoms"] == 2
    assert result["gold_atoms"] == 2
    assert result["micro_f1"] == 0.5
    assert result["exact_rate"] == 0.5


def test_exact_family_swap_uses_family_as_unit():
    b5 = [row("p1", "a", ["+x"], ["+x"]), row("p2", "b", ["+y"], ["+y"])]
    baseline = [row("p1", "a", [], ["+x"]), row("p2", "b", [], ["+y"])]
    result = analysis.exact_family_swap(b5, baseline)
    assert result["assignments"] == 4
    assert result["observed_mean_difference"] == 1.0
    assert result["one_sided_p"] == 0.25
