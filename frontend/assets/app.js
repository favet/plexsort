const API_BASE = window.location.port === "8014" ? "http://localhost:8004/api" : "/api";

const state = {
  page: 1,
  perPage: 50,
  sort: "title",
  dir: "asc",
  total: 0,
};

const els = {
  statsStrip: document.querySelector("#statsStrip"),
  moviesBody: document.querySelector("#moviesBody"),
  emptyState: document.querySelector("#emptyState"),
  resultCount: document.querySelector("#resultCount"),
  pageLabel: document.querySelector("#pageLabel"),
  prevPageButton: document.querySelector("#prevPageButton"),
  nextPageButton: document.querySelector("#nextPageButton"),
  filterPanel: document.querySelector(".filter-panel"),
  filterFields: document.querySelector("#filterFields"),
  toggleFiltersButton: document.querySelector("#toggleFiltersButton"),
  searchInput: document.querySelector("#searchInput"),
  yearMinInput: document.querySelector("#yearMinInput"),
  yearMaxInput: document.querySelector("#yearMaxInput"),
  genreInput: document.querySelector("#genreInput"),
  resolutionSelect: document.querySelector("#resolutionSelect"),
  contentRatingInput: document.querySelector("#contentRatingInput"),
  clearFiltersButton: document.querySelector("#clearFiltersButton"),
  listSelect: document.querySelector("#listSelect"),
  coverageSummary: document.querySelector("#coverageSummary"),
  missingPanel: document.querySelector("#missingPanel"),
  missingSummary: document.querySelector("#missingSummary"),
  missingList: document.querySelector("#missingList"),
  toast: document.querySelector("#toast"),
};

function showToast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 3600);
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function debounce(fn, delay = 240) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
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

function posterUrl(value) {
  if (!value || !/^https?:\/\//i.test(value)) {
    return "";
  }
  return value;
}

function filters() {
  const watched = document.querySelector("input[name='watched']:checked")?.value ?? "";
  return {
    q: els.searchInput.value.trim(),
    year_min: els.yearMinInput.value,
    year_max: els.yearMaxInput.value,
    genre: els.genreInput.value.trim(),
    resolution: els.resolutionSelect.value,
    content_rating: els.contentRatingInput.value.trim(),
    watched,
  };
}

function movieParams() {
  const params = new URLSearchParams({
    page: String(state.page),
    per_page: String(state.perPage),
    sort: state.sort,
    dir: state.dir,
  });

  Object.entries(filters()).forEach(([key, value]) => {
    if (value !== "") {
      params.set(key, value);
    }
  });

  return params;
}

function valueOrDash(value) {
  return value === null || value === undefined || value === "" ? "--" : value;
}

function formatRating(value) {
  return value === null || value === undefined ? "--" : Number(value).toFixed(1);
}

function setFiltersCollapsed(collapsed) {
  els.filterPanel.dataset.collapsed = collapsed ? "true" : "false";
  els.filterFields.hidden = collapsed;
  els.toggleFiltersButton.textContent = collapsed ? "Show" : "Hide";
}

function renderStats(stats) {
  const values = [
    ["Total", stats.total_movies],
    ["Watched", stats.total_watched],
    ["Lists", stats.lists_loaded],
  ];

  els.statsStrip.innerHTML = values
    .map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderMovies(page) {
  state.total = page.total;
  const totalPages = Math.max(1, Math.ceil(page.total / page.per_page));
  els.pageLabel.textContent = `${page.page} / ${totalPages}`;
  els.resultCount.textContent = `${page.total} result${page.total === 1 ? "" : "s"}`;
  els.prevPageButton.disabled = page.page <= 1;
  els.nextPageButton.disabled = page.page >= totalPages;
  els.emptyState.hidden = page.items.length > 0;

  els.moviesBody.innerHTML = page.items
    .map((movie) => {
      const thumb = posterUrl(movie.thumb_url);
      const genres = movie.genres?.length
        ? movie.genres
            .slice(0, 3)
            .map(
              (genre) =>
                `<button class="pill" data-filter-genre="${escapeHtml(genre)}">${escapeHtml(
                  genre,
                )}</button>`,
            )
            .join("")
        : '<span class="pill">--</span>';
      const watched = movie.view_count > 0;
      return `
        <tr>
          <td>
            <div class="movie-title">
              ${
                thumb
                  ? `<img class="poster-thumb" src="${escapeHtml(thumb)}" alt="" loading="lazy" />`
                  : '<span class="poster-thumb" aria-hidden="true"></span>'
              }
              <div>
                <strong>${escapeHtml(movie.title)}</strong>
                <div class="muted">${escapeHtml(valueOrDash(movie.content_rating))}</div>
              </div>
            </div>
          </td>
          <td data-label="Year">${escapeHtml(valueOrDash(movie.year))}</td>
          <td data-label="Genres"><div class="pill-row">${genres}</div></td>
          <td data-label="Rating">${escapeHtml(formatRating(movie.rating))}</td>
          <td data-label="Resolution">${escapeHtml(valueOrDash(movie.resolution))}</td>
          <td data-label="Watched" class="${watched ? "status-good" : "status-bad"}">${
            watched ? "Yes" : "No"
          }</td>
        </tr>
      `;
    })
    .join("");
}

function renderLists(lists) {
  if (!lists.length) {
    els.listSelect.innerHTML = '<option value="">None loaded</option>';
    return;
  }

  els.listSelect.innerHTML = [
    '<option value="">Select list</option>',
    ...lists.map((list) => `<option value="${list.id}">${escapeHtml(list.name)}</option>`),
  ].join("");
}

function renderCoverage(result) {
  const rows = [
    ["Coverage", `${result.coverage_pct}%`],
    ["In both", result.in_both.length],
    ["Missing", result.lb_only.length],
  ];
  els.coverageSummary.innerHTML = rows
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
}

function renderMissing(result) {
  if (!els.listSelect.value) {
    els.missingPanel.hidden = false;
    els.missingSummary.textContent = "Choose a Letterboxd list to see what Plex is missing.";
    els.missingList.innerHTML = "";
    return;
  }

  els.missingPanel.hidden = false;
  const missing = result.lb_only || [];
  els.missingSummary.textContent = missing.length
    ? `${missing.length} title${missing.length === 1 ? "" : "s"} to add for full coverage.`
    : "Full coverage for this list.";

  if (!missing.length) {
    els.missingList.innerHTML = '<div class="empty-state compact"><strong>Nothing missing</strong></div>';
    return;
  }

  els.missingList.innerHTML = missing
    .map(
      (entry) => `
        <article class="missing-item">
          <div>
            <strong>${escapeHtml(entry.title)}</strong>
            <span>${escapeHtml(valueOrDash(entry.year))}</span>
          </div>
          ${
            entry.lb_film_url
              ? `<a class="ghost-button" href="${escapeHtml(entry.lb_film_url)}" target="_blank" rel="noreferrer">Letterboxd</a>`
              : ""
          }
        </article>
      `,
    )
    .join("");
}

async function loadStats() {
  renderStats(await apiFetch("/stats"));
}

async function loadMovies() {
  const page = await apiFetch(`/movies?${movieParams().toString()}`);
  renderMovies(page);
}

async function loadLists() {
  renderLists(await apiFetch("/lists"));
}

async function loadCoverage() {
  const id = els.listSelect.value;
  if (!id) {
    renderCoverage({ coverage_pct: "--", in_both: [], lb_only: [] });
    renderMissing({ lb_only: [] });
    return;
  }
  const comparison = await apiFetch(`/lists/${id}/compare`);
  renderCoverage(comparison);
  renderMissing(comparison);
}

async function refreshMovies() {
  try {
    await loadMovies();
  } catch (error) {
    showToast(error.message);
  }
}

function bindEvents() {
  const debouncedRefresh = debounce(() => {
    state.page = 1;
    refreshMovies();
  });

  [
    els.searchInput,
    els.yearMinInput,
    els.yearMaxInput,
    els.genreInput,
    els.resolutionSelect,
    els.contentRatingInput,
  ].forEach((input) => input.addEventListener("input", debouncedRefresh));

  document.querySelectorAll("input[name='watched']").forEach((input) => {
    input.addEventListener("change", debouncedRefresh);
  });

  document.querySelectorAll("th button[data-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      const sort = button.dataset.sort;
      if (state.sort === sort) {
        state.dir = state.dir === "asc" ? "desc" : "asc";
      } else {
        state.sort = sort;
        state.dir = "asc";
      }
      refreshMovies();
    });
  });

  els.moviesBody.addEventListener("click", (event) => {
    const target = event.target.closest("[data-filter-genre]");
    if (!target) {
      return;
    }
    els.genreInput.value = target.dataset.filterGenre;
    state.page = 1;
    refreshMovies();
  });

  els.prevPageButton.addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    refreshMovies();
  });

  els.nextPageButton.addEventListener("click", () => {
    state.page += 1;
    refreshMovies();
  });

  els.clearFiltersButton.addEventListener("click", () => {
    els.searchInput.value = "";
    els.yearMinInput.value = "";
    els.yearMaxInput.value = "";
    els.genreInput.value = "";
    els.resolutionSelect.value = "";
    els.contentRatingInput.value = "";
    document.querySelector("input[name='watched'][value='']").checked = true;
    state.page = 1;
    refreshMovies();
  });

  els.toggleFiltersButton.addEventListener("click", () => {
    setFiltersCollapsed(els.filterPanel.dataset.collapsed !== "true");
  });

  els.listSelect.addEventListener("change", () => {
    loadCoverage().catch((error) => showToast(error.message));
  });
}

async function init() {
  if (window.matchMedia("(max-width: 880px)").matches) {
    setFiltersCollapsed(true);
  }
  bindEvents();
  try {
    await Promise.all([loadStats(), loadMovies(), loadLists()]);
    await loadCoverage();
  } catch (error) {
    showToast(error.message);
  }
}

init();
