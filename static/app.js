const feedback = document.querySelector("#feedback");
const count = document.querySelector("#character-count");
const button = document.querySelector("#analyze-button");
const error = document.querySelector("#error");
const emptyState = document.querySelector("#empty-state");
const resultContent = document.querySelector("#result-content");

feedback.addEventListener("input", () => {
  count.textContent = `${feedback.value.length.toLocaleString()} / 2,000`;
  error.textContent = "";
});

document.querySelectorAll("[data-example]").forEach((example) => {
  example.addEventListener("click", () => {
    feedback.value = example.dataset.example;
    feedback.dispatchEvent(new Event("input"));
    feedback.focus();
  });
});

function titleCase(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function displayResult(data) {
  emptyState.hidden = true;
  resultContent.hidden = false;
  const sentiment = document.querySelector("#sentiment");
  sentiment.textContent = titleCase(data.sentiment);
  sentiment.className = data.sentiment;

  const priority = document.querySelector("#priority");
  priority.textContent = `${titleCase(data.priority)} priority`;
  priority.className = `priority ${data.priority}`;

  const confidence = Math.round(data.confidence * 100);
  document.querySelector("#confidence").textContent = `${confidence}%`;
  document.querySelector("#confidence-meter").style.width = `${confidence}%`;
  document.querySelector("#recommendation").textContent = data.recommendation;

  document.querySelector("#probabilities").innerHTML = Object.entries(data.probabilities)
    .map(([label, value]) => `<div><span>${titleCase(label)}</span><strong>${Math.round(value * 100)}%</strong></div>`)
    .join("");
  document.querySelector("#keywords").innerHTML = data.keywords.length
    ? data.keywords.map((keyword) => `<span>${keyword}</span>`).join("")
    : "<span>No strong keywords</span>";
}

button.addEventListener("click", async () => {
  const text = feedback.value.trim();
  if (!text) {
    error.textContent = "Enter some feedback before running the analysis.";
    feedback.focus();
    return;
  }
  button.disabled = true;
  button.querySelector("span").textContent = "Analyzing…";
  error.textContent = "";
  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Analysis failed");
    displayResult(data);
  } catch (requestError) {
    error.textContent = requestError.message;
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Analyze feedback";
  }
});

