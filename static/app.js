const form = document.querySelector("#export-form");
const submitButton = document.querySelector("#submit-button");
const formError = document.querySelector("#form-error");
const progressPanel = document.querySelector("#progress-panel");
const progressTitle = document.querySelector("#progress-title");
const progressMessage = document.querySelector("#progress-message");
const progressCount = document.querySelector("#progress-count");
const progressCountLabel = document.querySelector("#progress-count-label");
const progressPercent = document.querySelector("#progress-percent");
const progressTrack = document.querySelector("#progress-track");
const progressBar = document.querySelector("#progress-bar");
const progressSpinner = document.querySelector("#progress-spinner");
const elapsedTime = document.querySelector("#elapsed-time");
const keepOpenNote = document.querySelector("#keep-open-note");
const resultActions = document.querySelector("#result-actions");
const jobWarning = document.querySelector("#job-warning");
const guide = document.querySelector("#guide-dialog");
let pollTimer = null;
let elapsedTimer = null;
let exportStartedAt = null;

function formatElapsed(milliseconds) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function startElapsedClock() {
  if (elapsedTimer) window.clearInterval(elapsedTimer);
  exportStartedAt = Date.now();
  elapsedTime.textContent = "0:00";
  elapsedTimer = window.setInterval(() => {
    elapsedTime.textContent = formatElapsed(Date.now() - exportStartedAt);
  }, 1000);
}

function stopElapsedClock() {
  if (elapsedTimer) window.clearInterval(elapsedTimer);
  elapsedTimer = null;
  if (exportStartedAt) elapsedTime.textContent = formatElapsed(Date.now() - exportStartedAt);
}

function showError(message) {
  formError.textContent = message;
  formError.hidden = false;
  formError.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function setBusy(isBusy) {
  submitButton.disabled = isBusy;
  submitButton.querySelector("span").textContent = isBusy ? "Starting…" : "Start export";
}

function resetProgress() {
  if (pollTimer) window.clearTimeout(pollTimer);
  stopElapsedClock();
  pollTimer = null;
  exportStartedAt = null;
  progressPanel.hidden = true;
  resultActions.hidden = true;
  jobWarning.hidden = true;
  keepOpenNote.hidden = false;
  progressSpinner.hidden = false;
  progressBar.className = "progress-bar";
  progressBar.style.width = "0%";
  progressTrack.setAttribute("aria-valuenow", "0");
  form.hidden = false;
  formError.hidden = true;
  setBusy(false);
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updateJob(job) {
  const limit = job.max_results;
  const percentage = limit ? Math.min(100, Math.round((job.fetched / limit) * 100)) : null;
  progressCount.textContent = limit ? `${job.fetched.toLocaleString()} / ${limit.toLocaleString()}` : job.fetched.toLocaleString();
  progressCountLabel.textContent = limit ? "accounts collected · selected maximum" : "accounts collected so far";
  progressPercent.textContent = percentage === null ? "Working" : `${percentage}%`;
  progressMessage.textContent = job.message;

  if (job.status === "queued" || job.status === "running") {
    progressTitle.textContent = job.status === "queued" ? "Waiting to start…" : `Collecting ${job.relationship}`;
    if (limit) {
      progressBar.className = "progress-bar";
      progressBar.style.width = `${percentage}%`;
      progressTrack.setAttribute("aria-valuenow", String(percentage));
    } else {
      progressBar.className = "progress-bar indeterminate";
      progressBar.style.width = "35%";
      progressTrack.removeAttribute("aria-valuenow");
    }
    return false;
  }

  stopElapsedClock();
  keepOpenNote.hidden = true;
  progressSpinner.hidden = true;
  progressBar.className = `progress-bar ${job.status === "failed" ? "failed" : "complete"}`;
  progressBar.style.width = "100%";
  progressTrack.setAttribute("aria-valuenow", "100");

  if (job.status === "failed") {
    progressTitle.textContent = "Export stopped";
    progressPercent.textContent = "Stopped";
    jobWarning.textContent = job.warning || "Check your details and try again.";
    jobWarning.hidden = false;
    resultActions.hidden = false;
    document.querySelector("#download-csv").hidden = true;
    document.querySelector("#download-json").hidden = true;
    return true;
  }

  progressTitle.textContent = "Your files are ready";
  progressPercent.textContent = "Complete";
  document.querySelector("#download-csv").hidden = false;
  document.querySelector("#download-json").hidden = false;
  document.querySelector("#download-csv").href = `/download/${encodeURIComponent(job.id)}/csv`;
  document.querySelector("#download-json").href = `/download/${encodeURIComponent(job.id)}/json`;
  resultActions.hidden = false;
  if (job.warning) {
    jobWarning.textContent = job.warning;
    jobWarning.hidden = false;
  }
  return true;
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Could not read export progress.");
    if (!updateJob(body)) {
      pollTimer = window.setTimeout(() => pollJob(jobId), 900);
    }
  } catch (error) {
    stopElapsedClock();
    progressTitle.textContent = "Connection interrupted";
    progressPercent.textContent = "Interrupted";
    progressMessage.textContent = error.message;
    progressSpinner.hidden = true;
    keepOpenNote.hidden = true;
    jobWarning.textContent = "The local app may have stopped. Return to the terminal and restart it if needed.";
    jobWarning.hidden = false;
    resultActions.hidden = false;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;

  if (!form.reportValidity()) return;
  const data = new FormData(form);
  const payload = {
    sessionid: data.get("sessionid"),
    csrftoken: data.get("csrftoken"),
    username: String(data.get("username") || "").replace(/^@/, ""),
    user_id: data.get("user_id"),
    relationship: data.get("relationship"),
    max_results: data.get("max_results"),
  };

  setBusy(true);
  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Could not start the export.");

    document.querySelector("#sessionid").value = "";
    document.querySelector("#csrftoken").value = "";
    form.hidden = true;
    progressPanel.hidden = false;
    keepOpenNote.hidden = false;
    progressSpinner.hidden = false;
    startElapsedClock();
    progressPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    updateJob(body);
    pollJob(body.id);
  } catch (error) {
    showError(error.message);
    setBusy(false);
  }
});

document.querySelectorAll("[data-toggle-secret]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.toggleSecret);
    const reveal = input.type === "password";
    input.type = reveal ? "text" : "password";
    button.textContent = reveal ? "Hide" : "Show";
    button.setAttribute("aria-label", `${reveal ? "Hide" : "Show"} ${input.name}`);
  });
});

document.querySelectorAll("[data-open-guide]").forEach((button) => {
  button.addEventListener("click", () => {
    guide.showModal();
    if (button.dataset.guideSection === "profile-id") {
      window.setTimeout(() => document.querySelector("#profile-id-guide").scrollIntoView({ block: "start" }), 50);
    }
  });
});

document.querySelector("#close-guide").addEventListener("click", () => guide.close());
guide.addEventListener("click", (event) => {
  if (event.target === guide) guide.close();
});
document.querySelector("#new-export").addEventListener("click", resetProgress);
