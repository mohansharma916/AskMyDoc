from eval.tune_threshold import recommend, sweep

ITEMS = [
    {"id": "a1", "answerable": True},
    {"id": "a2", "answerable": True},
    {"id": "u1", "answerable": False},
    {"id": "u2", "answerable": False},
]
SCORES = {"a1": 0.9, "a2": 0.04, "u1": 0.01, "u2": 0.05}


def test_sweep_uses_midpoints():
    rows = {r["threshold"]: r for r in sweep(ITEMS, SCORES)}
    assert set(rows) == {0.0, 0.025, 0.045, 0.475}
    assert rows[0.025] == {"threshold": 0.025, "correct_abstention": 0.5, "false_abstention": 0.0}
    assert rows[0.475]["false_abstention"] == 0.5


def test_recommend_respects_false_abstention_budget():
    rows = sweep(ITEMS, SCORES)
    assert recommend(rows, 0.0)["threshold"] == 0.025
    assert recommend(rows, 0.5)["threshold"] == 0.475
