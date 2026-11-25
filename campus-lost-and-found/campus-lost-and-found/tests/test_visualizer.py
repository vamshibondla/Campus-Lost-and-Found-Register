"""Tests for chart generation in visualizer.py."""

import os
from visualizer import generate_charts


class TestVisualizer:
    """Tests for generate_charts visualization output."""

    def test_generate_charts_empty_summary(self, tmp_path):
        target = str(tmp_path / "charts.png")
        summary = {"total": 0}
        assert generate_charts(summary, target) is False
        assert not os.path.exists(target)

    def test_generate_charts_valid_summary(self, tmp_path):
        target = str(tmp_path / "charts.png")
        summary = {
            "total": 5,
            "lost": 3,
            "found": 2,
            "claimed": 1,
            "open": 4,
            "by_category": {"Electronics": 3, "Other": 2},
            "by_location": {"Library": 3, "Lab 2": 2},
        }
        res = generate_charts(summary, target)
        assert res is True
        assert os.path.exists(target)
        assert os.path.getsize(target) > 0
