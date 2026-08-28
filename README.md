# CampusPulse AI

CampusPulse AI is an end-to-end natural language processing application that turns free-text student feedback into sentiment, priority, keywords, and a recommended follow-up action. It provides a responsive web interface and a JSON API, and is designed to run within the Microsoft Azure App Service free tier.

## 1. Problem statement

Universities receive large volumes of unstructured feedback through surveys, help desks, module evaluations, and informal channels. Reading every response manually is slow, and serious concerns can be buried among routine comments. CampusPulse AI performs a first-pass triage so staff can find feedback that needs attention sooner.

The application supports staff judgement; it does not replace safeguarding procedures or make decisions about students.

## 2. Use case

Student-services teams, course coordinators, and quality-assurance teams can paste an individual comment into the web application or connect an existing feedback form to the API. The output helps them:

- separate positive, neutral, and negative comments;
- identify urgent or high-priority language;
- see representative keywords; and
- route each comment to an appropriate follow-up workflow.

## 3. Solution overview

The application trains a multinomial Naive Bayes text classifier when the service starts. It converts text into unigram and bigram frequency features, calculates a probability for each sentiment class, and combines the negative probability with a small, transparent safety vocabulary to assign a priority. Flask exposes the model through a browser interface and a REST-style endpoint.

No feedback is stored. Each request is analyzed in memory and discarded.

## 4. Dataset

The repository contains `data/training_data.csv`, a balanced, purpose-built teaching dataset of 72 labelled English student-feedback examples:

| Label | Samples | Typical content |
|---|---:|---|
| Positive | 24 | Helpful teaching, reliable systems, useful services |
| Neutral | 24 | Schedules, locations, administrative facts |
| Negative | 24 | Poor support, access failures, unclear assessment |

The dataset was authored for this assignment and is distributed under this repository's MIT license. It contains no personal data. Because it is deliberately small, it demonstrates the complete ML lifecycle but is not suitable for production decisions without expansion, representative sampling, bias analysis, and human review.

## 5. AI/ML approach

- **Model:** multinomial Naive Bayes, implemented in pure Python.
- **Features:** lower-cased word unigrams, adjacent-word bigrams, and transparent domain-lexicon signal features.
- **Smoothing:** Laplace/add-one smoothing for unseen features.
- **Probabilities:** normalized from class log-likelihoods with a stable softmax.
- **Evaluation:** deterministic stratified holdout (25% of each label).
- **Priority layer:** transparent safety and service-failure signals combined with negative-class probability.
- **Explainability:** class probabilities, confidence, and extracted keywords are returned with every result.

The current holdout score is calculated from the bundled data at startup and shown in the web interface. Tests require at least 60% accuracy. A small educational dataset can overstate real-world performance; this score should not be interpreted as production validation.

## 6. Application architecture

```text
Browser / API client
        |
        | HTTPS + JSON
        v
Azure App Service (Linux, F1)
        |
        +-- Flask web UI and /api/analyze
        |
        +-- FeedbackAnalyzer
              |-- tokenization + unigram/bigram features
              |-- multinomial Naive Bayes probabilities
              +-- priority and keyword rules
        |
        +-- bundled, read-only training_data.csv
```

The solution uses no database, paid AI API, storage account, or container registry. This minimizes cost and prevents submitted feedback from being retained.

## 7. Technology stack

| Layer | Technology |
|---|---|
| UI | Semantic HTML, responsive CSS, vanilla JavaScript |
| API | Python 3.12, Flask 3.1, Gunicorn |
| AI/ML | Custom multinomial Naive Bayes NLP classifier |
| Testing | pytest and Flask test client |
| Container | Docker, Python slim base image, non-root user |
| Cloud | Microsoft Azure App Service for Linux |

## 8. Local setup

Python 3.12 or later is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
pytest -q
python app.py
```

Open <http://localhost:8000>. Check service readiness at <http://localhost:8000/health>.

## 9. Deployment details

The target is Azure App Service on Linux using the **F1 free SKU**. The deployment script refuses to fall back to a paid plan. Sign in with Azure CLI, choose a globally unique lowercase app name, and run:

```powershell
az login
.\scripts\deploy-azure.ps1 -AppName "campuspulse-yourname"
```

The script creates:

- resource group `rg-campuspulse-student` in Southeast Asia;
- Linux App Service plan `plan-campuspulse-free` on F1;
- one Python 3.12 web app; and
- a ZIP deployment with cloud-side dependency installation.

Free-tier apps have shared compute and daily quotas, so the first request after an idle period may be slow. If F1 is unavailable for the subscription or region, the script stops instead of creating a chargeable resource.

### Current deployment artifact

Azure CLI access was blocked by the trial tenant's Security Defaults policy, so the assignment's required container fallback was completed. The tested Linux image is publicly available from [Docker Hub](https://hub.docker.com/r/bashinigamage/campuspulse-ai):

```powershell
docker pull bashinigamage/campuspulse-ai:latest
docker run --rm -p 8000:8000 bashinigamage/campuspulse-ai:latest
```

For a reproducible, immutable pull of the verified `linux/amd64` image:

```powershell
docker pull bashinigamage/campuspulse-ai@sha256:5ddd692b0b525fab98fdebe1e53da38ac9ed2ff37eda1f548ac839b2ea32ae79
```

The image was anonymously pulled after publication to confirm that the repository is public. No Azure resources were created by this project's deployment procedure, so it consumed none of the trial credit.

To remove all deployed resources:

```powershell
az group delete --name rg-campuspulse-student --yes --no-wait
```

## 10. Web and API usage

Use the web page to enter up to 2,000 characters of feedback. Example API call:

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"The portal crashed before the deadline and nobody replied."}'
```

Example response:

```json
{
  "confidence": 0.9912,
  "keywords": ["portal", "crashed", "before", "deadline", "nobody"],
  "priority": "high",
  "probabilities": {"negative": 0.9912, "neutral": 0.0049, "positive": 0.0039},
  "recommendation": "Assign an owner today, investigate the issue, and acknowledge the student.",
  "sentiment": "negative"
}
```

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Interactive web application |
| GET | `/health` | Service and model readiness |
| POST | `/api/analyze` | Analyze a JSON `text` field |

## 11. Docker instructions

Docker is included as a portable fallback even though Azure can deploy the source directly.

```powershell
docker build -t campuspulse-ai:latest .
docker run --rm -p 8000:8000 campuspulse-ai:latest
```

Alternatively, run the published image without building it locally:

```powershell
docker run --rm -p 8000:8000 bashinigamage/campuspulse-ai:latest
```

The image runs as an unprivileged user and includes a health check. Open <http://localhost:8000> after the container starts.

## Testing

```powershell
python -m pytest -q
```

The suite covers model evaluation, representative classifications, urgent-term handling, the health route, the browser page, valid API analysis, and malformed requests.

## Responsible use and limitations

- Keep a human reviewer in every routing and safeguarding decision.
- Do not enter names, identifiers, health details, or other sensitive personal data.
- English-only training examples limit performance on other languages and dialects.
- Sarcasm, mixed sentiment, spelling variation, and unfamiliar university terminology can reduce accuracy.
- Expand and re-evaluate the dataset before any operational use.

## Security

Secrets are not required by the application. Azure credentials must never be committed; the local credential filename supplied for deployment is explicitly excluded by `.gitignore` and `.dockerignore`.

## License

MIT. See `LICENSE`.
