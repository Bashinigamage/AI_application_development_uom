"""Flask entry point for CampusPulse AI."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from ai_service import FeedbackAnalyzer


BASE_DIR = Path(__file__).resolve().parent


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        MAX_CONTENT_LENGTH=16 * 1024,
        JSON_SORT_KEYS=False,
        MODEL_DATASET=str(BASE_DIR / "data" / "training_data.csv"),
    )
    if test_config:
        app.config.update(test_config)

    analyzer = FeedbackAnalyzer(app.config["MODEL_DATASET"])
    app.extensions["feedback_analyzer"] = analyzer

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            metrics=analyzer.metrics,
            environment="Azure" if os.getenv("WEBSITE_HOSTNAME") else "Local",
        )

    @app.get("/health")
    def health():
        return jsonify(
            status="healthy",
            model="multinomial-naive-bayes-v1",
            training_samples=analyzer.metrics.samples,
        )

    @app.post("/api/analyze")
    def analyze():
        if not request.is_json:
            return jsonify(error="Content-Type must be application/json"), 415
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Request body must be a JSON object"), 400
        text = payload.get("text")
        if not isinstance(text, str):
            return jsonify(error="The 'text' field must be a string"), 400
        if len(text) > 2_000:
            return jsonify(error="Feedback must not exceed 2,000 characters"), 400
        try:
            result = analyzer.analyze(text)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(result)

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error="Request is too large"), 413

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")), debug=False)

