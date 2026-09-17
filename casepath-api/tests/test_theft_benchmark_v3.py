import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "research/casepath/theft_benchmark_v3.py"
spec = importlib.util.spec_from_file_location("theft_benchmark_v3", MODULE)
module = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(module)


def test_bicycle_projection_is_source_derived_and_conjunctive():
    benchmark, preflight, amendment = module.build()
    pairs = [p for p in benchmark["pairs"] if p["scenario"] == "PR_bicycle_claimed"]
    expected = {
        "Bicycle purchase voucher (Kaufbeleg des Fahrrads / Originalkaufbeleg)",
        "Detailed cost estimate for the bicycle with an image of the damaged or stolen bicycle or part (Detaillierter Kostenvoranschlag mit Foto)",
    }
    assert pairs
    for pair in pairs:
        assert set(pair["expected_added"]) == expected
        assert pair["acceptable_signed_deltas"] == [sorted("+" + d for d in expected)]
    assert set(amendment["reference_projection"]) == expected


def test_scheduled_valuable_alternatives_survive_v3():
    benchmark, _, _ = module.build()
    pair = next(p for p in benchmark["pairs"]
                if p["scenario"] == "PR_scheduled_valuable_1000")
    assert len(pair["acceptable_signed_deltas"]) == 2
    assert all(len(option) == 1 for option in pair["acceptable_signed_deltas"])


def test_v3_preserves_roster_and_hidden_boundary():
    benchmark, _, amendment = module.build()
    assert len(benchmark["pairs"]) == 36
    assert len(benchmark["units"]) == 72
    assert amendment["development_pairs_opened_before_amendment"] == 9
    assert amendment["hidden_pairs_opened_before_amendment"] == 0
    assert amendment["hidden_units_remaining"] == 54


def test_v3_shortcut_preflight_still_passes():
    _, preflight, _ = module.build()
    assert preflight["admission"]["input_free_control_pass"]
    assert preflight["admission"]["target_diversity_pass"]
    assert preflight["max_held_out_no_input_micro_f1"] <= 0.10
