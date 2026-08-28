"""Small, dependency-free NLP model used by CampusPulse AI.

The classifier is a multinomial Naive Bayes model trained from the labelled CSV
bundled with the project. It intentionally avoids a heavyweight ML runtime so
the application remains suitable for Azure App Service's constrained free tier.
"""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z']+")
LABELS = ("negative", "neutral", "positive")
STOP_WORDS = {
    "a", "about", "after", "all", "also", "am", "an", "and", "are",
    "as", "at", "be", "because", "been", "but", "by", "can", "could",
    "did", "do", "does", "for", "from", "had", "has", "have", "i",
    "if", "in", "is", "it", "its", "me", "my", "of", "on", "or",
    "our", "so", "that", "the", "their", "there", "they", "this", "to",
    "too", "very", "was", "we", "were", "will", "with", "would", "you",
}

# Domain lexicons become explicit model features. They make the small teaching
# dataset less brittle while keeping every decision signal inspectable.
POSITIVE_TERMS = {
    "appreciate", "balanced", "clear", "clearly", "comfortable", "confidence",
    "constructive", "convenient", "easy", "engaging", "enjoyed", "excellent",
    "fair", "friendly", "helpful", "improved", "modern", "perfectly", "quickly",
    "relevant", "resolved", "rewarding", "satisfied", "smoothly", "useful",
}
NEGATIVE_TERMS = {
    "badly", "blocked", "broken", "cancelled", "confusing", "crashed",
    "difficult", "dismissive", "disappointing", "failed", "fails", "ignored",
    "impossible", "incomplete", "inconsistent", "lost", "missing", "overcharged",
    "overcrowded", "rushed", "slow", "stress", "unclear", "uncomfortable",
    "unfair", "unusable", "vague",
}
NEUTRAL_TERMS = {
    "assigned", "attended", "borrow", "closes", "contains", "duration", "floor",
    "located", "monday", "opens", "published", "registered", "scheduled",
    "starts", "submitted", "takes", "timetable", "yesterday",
}

URGENT_TERMS = {
    "unsafe", "harassment", "threat", "injured", "emergency", "discrimination",
    "abuse", "dangerous", "suicide", "violence", "bullying",
}
HIGH_PRIORITY_TERMS = {
    "failed", "broken", "unfair", "impossible", "missing", "cancelled",
    "overcharged", "blocked", "crash", "deadline", "complaint",
}


def _tokens(text: str) -> list[str]:
    words = [match.group(0).lower().strip("'") for match in TOKEN_RE.finditer(text)]
    features = words[:]
    features.extend(f"{left}_{right}" for left, right in zip(words, words[1:]))
    for lexicon, signal in (
        (POSITIVE_TERMS, "signal:positive"),
        (NEGATIVE_TERMS, "signal:negative"),
        (NEUTRAL_TERMS, "signal:neutral"),
    ):
        # Repetition is equivalent to giving this interpretable feature a
        # little more weight in the multinomial frequency model.
        features.extend([signal] * (3 * sum(word in lexicon for word in words)))
    return features


@dataclass(frozen=True)
class ModelMetrics:
    accuracy: float
    samples: int
    validation_samples: int


class FeedbackAnalyzer:
    """Train and serve a compact sentiment and priority classifier."""

    def __init__(self, dataset_path: str | Path, alpha: float = 1.0) -> None:
        self.dataset_path = Path(dataset_path)
        self.alpha = alpha
        rows = self._read_rows()
        self.metrics = self._evaluate(rows)
        self._fit(rows)

    def _read_rows(self) -> list[tuple[str, str]]:
        with self.dataset_path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            rows = [(row["text"].strip(), row["label"].strip().lower()) for row in reader]
        if not rows or any(label not in LABELS for _, label in rows):
            raise ValueError("Training data must contain text and a supported label")
        return rows

    def _fit(self, rows: Iterable[tuple[str, str]]) -> None:
        self.class_documents: Counter[str] = Counter()
        self.feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.total_features: Counter[str] = Counter()
        self.vocabulary: set[str] = set()

        for text, label in rows:
            features = _tokens(text)
            self.class_documents[label] += 1
            self.feature_counts[label].update(features)
            self.total_features[label] += len(features)
            self.vocabulary.update(features)
        self.document_count = sum(self.class_documents.values())

    def _probabilities(self, text: str) -> dict[str, float]:
        observed = Counter(_tokens(text))
        vocabulary_size = max(1, len(self.vocabulary))
        log_scores: dict[str, float] = {}
        for label in LABELS:
            prior = (self.class_documents[label] + self.alpha) / (
                self.document_count + self.alpha * len(LABELS)
            )
            denominator = self.total_features[label] + self.alpha * vocabulary_size
            score = math.log(prior)
            for feature, count in observed.items():
                likelihood = (self.feature_counts[label][feature] + self.alpha) / denominator
                score += count * math.log(likelihood)
            log_scores[label] = score

        peak = max(log_scores.values())
        exponentials = {label: math.exp(score - peak) for label, score in log_scores.items()}
        normalizer = sum(exponentials.values())
        return {label: value / normalizer for label, value in exponentials.items()}

    def _evaluate(self, rows: list[tuple[str, str]]) -> ModelMetrics:
        # Deterministic stratified holdout: every fourth sample in each label is validation.
        grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for row in rows:
            grouped[row[1]].append(row)
        train: list[tuple[str, str]] = []
        validation: list[tuple[str, str]] = []
        for label in LABELS:
            for index, row in enumerate(grouped[label]):
                (validation if index % 4 == 0 else train).append(row)

        self._fit(train)
        correct = sum(max(self._probabilities(text), key=self._probabilities(text).get) == label
                      for text, label in validation)
        return ModelMetrics(
            accuracy=correct / len(validation),
            samples=len(rows),
            validation_samples=len(validation),
        )

    @staticmethod
    def _keywords(text: str) -> list[str]:
        words = [
            word for word in _tokens(text)
            if "_" not in word and not word.startswith("signal:") and word not in STOP_WORDS
        ]
        counts = Counter(words)
        first_seen = {word: index for index, word in enumerate(words)}
        ranked = sorted(counts, key=lambda word: (-counts[word], first_seen[word]))
        return ranked[:5]

    @staticmethod
    def _priority(text: str, probabilities: dict[str, float]) -> str:
        words = set(_tokens(text))
        if words & URGENT_TERMS:
            return "urgent"
        if words & HIGH_PRIORITY_TERMS or probabilities["negative"] >= 0.72:
            return "high"
        if probabilities["negative"] >= 0.44 or probabilities["neutral"] >= 0.70:
            return "medium"
        return "low"

    @staticmethod
    def _recommendation(sentiment: str, priority: str) -> str:
        if priority == "urgent":
            return "Escalate immediately to the responsible student-support or safety team."
        if priority == "high":
            return "Assign an owner today, investigate the issue, and acknowledge the student."
        if sentiment == "negative":
            return "Review within two working days and follow up with a concrete next step."
        if sentiment == "positive":
            return "Share with the relevant team and record the successful practice."
        return "Route to the relevant service owner for routine review."

    def analyze(self, text: str) -> dict[str, object]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Feedback text cannot be empty")
        probabilities = self._probabilities(cleaned)
        sentiment = max(probabilities, key=probabilities.get)
        priority = self._priority(cleaned, probabilities)
        return {
            "sentiment": sentiment,
            "confidence": round(probabilities[sentiment], 4),
            "probabilities": {label: round(probabilities[label], 4) for label in LABELS},
            "priority": priority,
            "keywords": self._keywords(cleaned),
            "recommendation": self._recommendation(sentiment, priority),
        }
