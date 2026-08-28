from pathlib import Path

import pytest

from ai_service import FeedbackAnalyzer


@pytest.fixture(scope="module")
def analyzer():
    return FeedbackAnalyzer(Path(__file__).parents[1] / "data" / "training_data.csv")


def test_model_reports_real_holdout_metrics(analyzer):
    assert analyzer.metrics.samples == 72
    assert analyzer.metrics.validation_samples == 18
    assert 0.6 <= analyzer.metrics.accuracy <= 1.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The tutor was excellent and explained everything clearly", "positive"),
        ("The system is broken and support ignored my complaint", "negative"),
        ("The next lecture is scheduled for Monday", "neutral"),
    ],
)
def test_sentiment_examples(analyzer, text, expected):
    assert analyzer.analyze(text)["sentiment"] == expected


def test_safety_language_is_urgent(analyzer):
    result = analyzer.analyze("I feel unsafe because of bullying in my class")
    assert result["priority"] == "urgent"


def test_internal_model_features_are_not_exposed_as_keywords(analyzer):
    result = analyzer.analyze("The tutor was excellent and very helpful")
    assert all(not keyword.startswith("signal:") for keyword in result["keywords"])


def test_empty_feedback_is_rejected(analyzer):
    with pytest.raises(ValueError, match="cannot be empty"):
        analyzer.analyze("  ")
