const API_BASE = window.location.port === "8014" ? "http://localhost:8004/api" : "/api";
const HEALTH_URL = window.location.port === "8014" ? "http://localhost:8004/health" : "/health";

const els = {
  adminStatus: document.querySelector("#adminStatus"),
  syncPlexButton: document.querySelector("#syncPlexButton"),
  syncStatus: document.querySelector("#syncStatus"),
  activeJob: document.querySelector("#activeJob"),
  jobList: document.querySelector("#jobList"),
  scrapeForm: document.querySelector("#scrapeForm"),
  scrapeUrlInput: document.querySelector("#scrapeUrlInput"),
  scrapeNameInput: document.querySelector("#scrapeNameInput"),
  uploadForm: document.querySelector("#uploadForm"),
  uploadInput: document.querySelector("#uploadInput"),
  runMatchButton: document.querySelector("#runMatchButton"),
  reviewList: document.querySelector("#reviewList"),
  toast: document.querySelector("#toast"),
};

let activeJobTimer = null;

function showToast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 4200);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[char];
  });
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function formatDate(value) {
  if (!value) {
    return "--";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function renderSyncStatus(status) {
  const rows = [
    ["Last sync", formatDate(status.last_sync_time)],
    ["Movies", status.movie_count],
    ["Error", status.last_error || "--"],
  ];
  els.syncStatus.innerHTML = rows
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

function renderReview(items) {
  if (!items.length) {
    els.reviewList.innerHTML = '<div class="empty-state"><strong>No review items</strong></div>';
    return;
  }

  els.reviewList.innerHTML = items
    .map(
      (item) => `
        <article class="review-item" data-match-id="${item.match_id}">
          <strong>${escapeHtml(item.lb_entry.title)} ${escapeHtml(item.lb_entry.year || "")}</strong>
          <span>${escapeHtml(item.confidence)} - ${escapeHtml(item.match_method)}</span>
          <span>${item.plex_movie ? escapeHtml(item.plex_movie.title) : "Unmatched"}</span>
          <div class="review-actions">
            <input
              type="search"
              value="${escapeHtml(item.lb_entry.title)}"
              aria-label="Search Plex movies"
              data-role="review-query"
            />
            <button class="ghost-button" type="button" data-action="search-match">Search</button>
            <button class="ghost-button" type="button" data-action="mark-unmatched">Skip</button>
          </div>
          <div class="candidate-list" data-role="candidate-list"></div>
        </article>
      `,
    )
    .join("");
}

function jobProgressText(job) {
  if (job.total === null || job.total === undefined) {
    return `${job.current}`;
  }
  return `${job.current} / ${job.total}`;
}

function renderActiveJob(job) {
  if (!job) {
    els.activeJob.innerHTML = "<strong>No active job</strong><span>Recent work will appear here.</span>";
    return;
  }
  const percent =
    job.total && job.total > 0 ? Math.min(100, Math.round((job.current / job.total) * 100)) : 0;
  const progress = job.total
    ? `<progress value="${job.current}" max="${job.total}"></progress>`
    : "<progress></progress>";
  els.activeJob.innerHTML = `
    <strong>${escapeHtml(job.job_type)} - ${escapeHtml(job.status)}</strong>
    <span>${escapeHtml(job.message || job.phase || "")}</span>
    ${progress}
    <span>${escapeHtml(jobProgressText(job))}${job.total ? ` - ${percent}%` : ""}</span>
  `;
}

function renderJobs(jobs) {
  if (!jobs.length) {
    els.jobList.innerHTML = '<div class="empty-state"><strong>No jobs yet</strong></div>';
    return;
  }
  els.jobList.innerHTML = jobs
    .slice(0, 6)
    .map(
      (job) => `
        <article class="review-item">
          <strong>${escapeHtml(job.job_type)} - ${escapeHtml(job.status)}</strong>
          <span>${escapeHtml(job.message || job.phase || "")}</span>
          <span>${escapeHtml(jobProgressText(job))}</span>
        </article>
      `,
    )
    .join("");
}

async function refreshJobs() {
  const jobs = await apiFetch("/admin/jobs");
  renderJobs(jobs);
  const active = jobs.find((job) => job.status === "queued" || job.status === "running");
  renderActiveJob(active || null);
  return active;
}

async function refresh() {
  const [health, syncStatus, reviewItems] = await Promise.all([
    fetch(HEALTH_URL).then((response) => response.json()),
    apiFetch("/admin/sync/status"),
    apiFetch("/admin/matches/review"),
  ]);
  els.adminStatus.textContent = health.status === "ok" ? "Backend online" : "Backend unavailable";
  renderSyncStatus(syncStatus);
  renderReview(reviewItems);
  await refreshJobs();
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.dataset.originalText ||= button.textContent;
  button.textContent = busy ? "Working" : button.dataset.originalText;
}

async function patchMatch(matchId, payload) {
  await apiFetch(`/admin/matches/${matchId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  showToast("Review saved");
  await refresh();
}

function renderCandidates(container, matchId, movies) {
  if (!movies.length) {
    container.innerHTML = '<span class="muted">No Plex candidates found.</span>';
    return;
  }

  els.reviewList.querySelectorAll(".candidate-list").forEach((list) => {
    if (list !== container) {
      list.innerHTML = "";
    }
  });

  container.innerHTML = movies
    .map(
      (movie) => `
        <button
          class="candidate-button"
          type="button"
          data-action="confirm-match"
          data-movie-id="${movie.id}"
          data-match-id="${matchId}"
        >
          <span>${escapeHtml(movie.title)}</span>
          <small>${escapeHtml(movie.year || "--")} - ${escapeHtml(movie.resolution || "--")}</small>
        </button>
      `,
    )
    .join("");
}

async function trackJob(jobId) {
  window.clearInterval(activeJobTimer);
  async function poll() {
    const job = await apiFetch(`/admin/jobs/${jobId}`);
    renderActiveJob(job);
    await refreshJobs();
    if (job.status === "completed" || job.status === "failed") {
      window.clearInterval(activeJobTimer);
      activeJobTimer = null;
      showToast(job.status === "completed" ? "Job complete" : `Job failed: ${job.error || ""}`);
      await refresh();
    }
  }
  await poll();
  activeJobTimer = window.setInterval(() => {
    poll().catch((error) => showToast(error.message));
  }, 1600);
}

function bindEvents() {
  els.syncPlexButton.addEventListener("click", async () => {
    setBusy(els.syncPlexButton, true);
    try {
      const job = await apiFetch("/admin/sync/plex", { method: "POST" });
      showToast("Plex sync queued");
      await trackJob(job.job_id);
    } catch (error) {
      showToast(error.message);
    } finally {
      setBusy(els.syncPlexButton, false);
    }
  });

  els.scrapeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = els.scrapeForm.querySelector("button");
    setBusy(button, true);
    try {
      const job = await apiFetch("/admin/lists/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: els.scrapeUrlInput.value,
          name: els.scrapeNameInput.value || null,
        }),
      });
      els.scrapeForm.reset();
      showToast("Scrape queued");
      await trackJob(job.job_id);
    } catch (error) {
      showToast(error.message);
    } finally {
      setBusy(button, false);
    }
  });

  els.uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = els.uploadInput.files[0];
    if (!file) {
      return;
    }
    const button = els.uploadForm.querySelector("button");
    const formData = new FormData();
    formData.set("file", file);
    setBusy(button, true);
    try {
      const job = await apiFetch("/admin/lists/upload", {
        method: "POST",
        body: formData,
      });
      els.uploadForm.reset();
      showToast("Import queued");
      await trackJob(job.job_id);
    } catch (error) {
      showToast(error.message);
    } finally {
      setBusy(button, false);
    }
  });

  els.runMatchButton.addEventListener("click", async () => {
    setBusy(els.runMatchButton, true);
    try {
      const job = await apiFetch("/admin/match/run", { method: "POST" });
      showToast("Matching queued");
      await trackJob(job.job_id);
    } catch (error) {
      showToast(error.message);
    } finally {
      setBusy(els.runMatchButton, false);
    }
  });

  els.reviewList.addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) {
      return;
    }

    const item = button.closest("[data-match-id]");
    const matchId = button.dataset.matchId || item?.dataset.matchId;
    if (!matchId) {
      return;
    }

    if (button.dataset.action === "search-match") {
      const query = item.querySelector("[data-role='review-query']").value.trim();
      const container = item.querySelector("[data-role='candidate-list']");
      if (!query) {
        return;
      }
      button.disabled = true;
      try {
        const movies = await apiFetch(
          `/admin/movies/search?q=${encodeURIComponent(query)}&limit=8`,
        );
        renderCandidates(container, matchId, movies);
      } catch (error) {
        showToast(error.message);
      } finally {
        button.disabled = false;
      }
      return;
    }

    if (button.dataset.action === "confirm-match") {
      await patchMatch(matchId, {
        plex_movie_id: Number(button.dataset.movieId),
        confidence: "high",
        match_method: "manual",
        reviewed: true,
      });
      return;
    }

    if (button.dataset.action === "mark-unmatched") {
      await patchMatch(matchId, {
        plex_movie_id: null,
        confidence: "none",
        match_method: "manual_unmatched",
        reviewed: true,
      });
    }
  });
}

async function init() {
  bindEvents();
  try {
    await refresh();
  } catch (error) {
    els.adminStatus.textContent = "Backend unavailable";
    showToast(error.message);
  }
}

init();
