const API_BASE = window.location.port === "8014" ? "http://localhost:8004/api" : "/api";
const HEALTH_URL = window.location.port === "8014" ? "http://localhost:8004/health" : "/health";

const els = {
  adminStatus: document.querySelector("#adminStatus"),
  syncPlexButton: document.querySelector("#syncPlexButton"),
  syncStatus: document.querySelector("#syncStatus"),
  scrapeForm: document.querySelector("#scrapeForm"),
  scrapeUrlInput: document.querySelector("#scrapeUrlInput"),
  scrapeNameInput: document.querySelector("#scrapeNameInput"),
  uploadForm: document.querySelector("#uploadForm"),
  uploadInput: document.querySelector("#uploadInput"),
  runMatchButton: document.querySelector("#runMatchButton"),
  reviewList: document.querySelector("#reviewList"),
  toast: document.querySelector("#toast"),
};

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
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
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
        <article class="review-item">
          <strong>${escapeHtml(item.lb_entry.title)} ${escapeHtml(item.lb_entry.year || "")}</strong>
          <span>${escapeHtml(item.confidence)} · ${escapeHtml(item.match_method)}</span>
          <span>${item.plex_movie ? escapeHtml(item.plex_movie.title) : "Unmatched"}</span>
        </article>
      `,
    )
    .join("");
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
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.dataset.originalText ||= button.textContent;
  button.textContent = busy ? "Working" : button.dataset.originalText;
}

function bindEvents() {
  els.syncPlexButton.addEventListener("click", async () => {
    setBusy(els.syncPlexButton, true);
    try {
      await apiFetch("/admin/sync/plex", { method: "POST" });
      showToast("Plex sync complete");
      await refresh();
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
      await apiFetch("/admin/lists/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: els.scrapeUrlInput.value,
          name: els.scrapeNameInput.value || null,
        }),
      });
      els.scrapeForm.reset();
      showToast("List scraped");
      await refresh();
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
      await apiFetch("/admin/lists/upload", {
        method: "POST",
        body: formData,
      });
      els.uploadForm.reset();
      showToast("Export uploaded");
      await refresh();
    } catch (error) {
      showToast(error.message);
    } finally {
      setBusy(button, false);
    }
  });

  els.runMatchButton.addEventListener("click", async () => {
    setBusy(els.runMatchButton, true);
    try {
      await apiFetch("/admin/match/run", { method: "POST" });
      showToast("Matching complete");
      await refresh();
    } catch (error) {
      showToast(error.message);
    } finally {
      setBusy(els.runMatchButton, false);
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
