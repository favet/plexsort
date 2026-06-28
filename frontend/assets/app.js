const API_BASE = window.location.port === "8014" ? "http://localhost:8004/api" : "/api";

const state = {
  page: 1,
  perPage: 50,
  sort: "title",
  dir: "asc",
  total: 0,
  listFilter: null,
  missingSort: "position",
  missingDir: "asc",
};

let lastComparison = null;
let currentPageMovies = [];
let matchedPlexKeys = new Set();

const els = {
  totalMovies: document.querySelector("#totalMovies"),
  moviesBody: document.querySelector("#moviesBody"),
  emptyState: document.querySelector("#emptyState"),
  resultCount: document.querySelector("#resultCount"),
  exportFilteredLink: document.querySelector("#exportFilteredLink"),
  pageLabel: document.querySelector("#pageLabel"),
  prevPageButton: document.querySelector("#prevPageButton"),
  nextPageButton: document.querySelector("#nextPageButton"),
  sortSelect: document.querySelector("#sortSelect"),
  sortDirButton: document.querySelector("#sortDirButton"),
  perPageSelect: document.querySelector("#perPageSelect"),
  activeFilters: document.querySelector("#activeFilters"),
  sidebar: document.querySelector("#sidebar"),
  sidebarToggleButton: document.querySelector("#sidebarToggleButton"),
  filterPanel: document.querySelector(".filter-panel"),
  filterFields: document.querySelector("#filterFields"),
  toggleFiltersButton: document.querySelector("#toggleFiltersButton"),
  searchInput: document.querySelector("#searchInput"),
  yearMinInput: document.querySelector("#yearMinInput"),
  yearMaxInput: document.querySelector("#yearMaxInput"),
  genreInput: document.querySelector("#genreInput"),
  genreDatalist: document.querySelector("#genreOptions"),
  resolutionSelect: document.querySelector("#resolutionSelect"),
  contentRatingInput: document.querySelector("#contentRatingInput"),
  clearFiltersButton: document.querySelector("#clearFiltersButton"),
  listSelect: document.querySelector("#listSelect"),
  coverageSummary: document.querySelector("#coverageSummary"),
  exportLinks: document.querySelector("#exportLinks"),
  diffCsvLink: document.querySelector("#diffCsvLink"),
  tableFrame: document.querySelector("#tableFrame"),
  missingView: document.querySelector("#missingView"),
  missingViewTitle: document.querySelector("#missingViewTitle"),
  closeMissingViewButton: document.querySelector("#closeMissingViewButton"),
  missingList: document.querySelector("#missingList"),
  movieDetail: document.querySelector("#movieDetail"),
  movieDetailBackdrop: document.querySelector("#movieDetailBackdrop"),
  movieDetailContent: document.querySelector("#movieDetailContent"),
  closeMovieDetailButton: document.querySelector("#closeMovieDetailButton"),
  settingsButton: document.querySelector("#settingsButton"),
  closeSettingsButton: document.querySelector("#closeSettingsButton"),
  settingsPanel: document.querySelector("#settingsPanel"),
  healthGrid: document.querySelector("#healthGrid"),
  healthLists: document.querySelector("#healthLists"),
  toast: document.querySelector("#toast"),
};

// ── Toast ──────────────────────────────────────────────────────────────────

function showToast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => { els.toast.hidden = true; }, 3600);
}

// ── Utilities ──────────────────────────────────────────────────────────────

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
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function posterUrl(movie) {
  if (!movie.thumb_url) return "";
  if (/^https?:\/\//i.test(movie.thumb_url)) return movie.thumb_url;
  return `${API_BASE}/posters/${encodeURIComponent(movie.plex_rating_key)}`;
}

function valueOrDash(v) {
  return v === null || v === undefined || v === "" ? "--" : v;
}

function formatRating(v) {
  return v === null || v === undefined ? "--" : Number(v).toFixed(1);
}

function formatPercent(v) {
  return `${Number(v || 0).toFixed(1)}%`;
}

function formatResolution(v) {
  if (!v) return "--";
  const s = String(v).toLowerCase();
  if (s === "4k") return "4K";
  if (s === "sd") return "SD";
  if (/^\d+$/.test(s)) return `${s}p`;
  return v;
}

function formatDuration(ms) {
  if (!ms) return "--";
  const m = Math.round(ms / 60000);
  const h = Math.floor(m / 60);
  return h > 0 ? `${h}h ${m % 60}m` : `${m}m`;
}

function formatBitrate(kbps) {
  if (!kbps) return "--";
  return kbps >= 1000 ? `${(kbps / 1000).toFixed(1)} Mbps` : `${kbps} kbps`;
}

function formatDate(iso) {
  if (!iso) return "--";
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function cleanValue(v) {
  return v === null || v === undefined || v === "" || v === "N/A" || v === "--" ? "" : String(v);
}

function detailStat(label, value) {
  const clean = cleanValue(value);
  if (!clean) return "";
  return `<div class="detail-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(clean)}</strong></div>`;
}

function detailText(title, body) {
  const clean = cleanValue(body);
  if (!clean) return "";
  return `
    <section class="detail-section">
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(clean)}</p>
    </section>`;
}

function detailGroup(title, inner) {
  if (!inner.trim()) return "";
  return `
    <section class="detail-group">
      <h3>${escapeHtml(title)}</h3>
      <div class="detail-group-body">${inner}</div>
    </section>`;
}

function inInput() {
  return ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName);
}

// ── Filter state ───────────────────────────────────────────────────────────

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
  Object.entries(filters()).forEach(([k, v]) => { if (v !== "") params.set(k, v); });
  if (state.listFilter && els.listSelect.value) {
    params.set("list_id", els.listSelect.value);
    params.set("in_list", state.listFilter === "in_list" ? "true" : "false");
  }
  return params;
}

function buildExportUrl() {
  const params = new URLSearchParams({ sort: state.sort, dir: state.dir });
  const f = filters();
  Object.entries(f).forEach(([k, v]) => { if (v !== "") params.set(k, v); });
  if (state.listFilter && els.listSelect.value) {
    params.set("list_id", els.listSelect.value);
    params.set("in_list", state.listFilter === "in_list" ? "true" : "false");
  }
  return `/api/export/movies-csv?${params}`;
}

// ── URL state ──────────────────────────────────────────────────────────────

function pushUrlState() {
  const params = new URLSearchParams();
  const f = filters();
  if (f.q) params.set("q", f.q);
  if (f.genre) params.set("genre", f.genre);
  if (f.year_min) params.set("year_min", f.year_min);
  if (f.year_max) params.set("year_max", f.year_max);
  if (f.resolution) params.set("resolution", f.resolution);
  if (f.content_rating) params.set("content_rating", f.content_rating);
  if (f.watched) params.set("watched", f.watched);
  if (state.sort !== "title") params.set("sort", state.sort);
  if (state.dir !== "asc") params.set("dir", state.dir);
  if (state.page > 1) params.set("page", String(state.page));
  if (state.perPage !== 50) params.set("per_page", String(state.perPage));
  if (els.listSelect.value) params.set("list_id", els.listSelect.value);
  if (state.listFilter) params.set("list_filter", state.listFilter);
  const qs = params.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function parseUrlState() {
  const p = new URLSearchParams(location.search);
  if (p.get("q")) els.searchInput.value = p.get("q");
  if (p.get("genre")) els.genreInput.value = p.get("genre");
  if (p.get("year_min")) els.yearMinInput.value = p.get("year_min");
  if (p.get("year_max")) els.yearMaxInput.value = p.get("year_max");
  if (p.get("resolution")) els.resolutionSelect.value = p.get("resolution");
  if (p.get("content_rating")) els.contentRatingInput.value = p.get("content_rating");
  if (p.get("watched")) {
    const el = document.querySelector(`input[name='watched'][value='${p.get("watched")}']`);
    if (el) el.checked = true;
  }
  if (p.get("sort")) state.sort = p.get("sort");
  if (p.get("dir")) state.dir = p.get("dir");
  if (p.get("page")) state.page = parseInt(p.get("page"), 10) || 1;
  if (p.get("per_page")) {
    const pp = parseInt(p.get("per_page"), 10);
    if ([25, 50, 100].includes(pp)) { state.perPage = pp; els.perPageSelect.value = String(pp); }
  }
  if (p.get("list_filter")) state.listFilter = p.get("list_filter");
  return { listId: p.get("list_id") };
}

// ── Sort & filter UI ───────────────────────────────────────────────────────

function updateSortDropdown() {
  els.sortSelect.value = state.sort;
  els.sortDirButton.textContent = state.dir === "asc" ? "↑" : "↓";
  els.sortDirButton.title = state.dir === "asc" ? "Ascending — click to reverse" : "Descending — click to reverse";
}

function updateSortIndicators() {
  document.querySelectorAll("th button[data-sort]").forEach((btn) => {
    btn.dataset.sortDir = btn.dataset.sort === state.sort ? state.dir : "";
  });
}

function clearFilter(name) {
  switch (name) {
    case "q": els.searchInput.value = ""; break;
    case "genre": els.genreInput.value = ""; break;
    case "year": els.yearMinInput.value = ""; els.yearMaxInput.value = ""; break;
    case "year_min": els.yearMinInput.value = ""; break;
    case "year_max": els.yearMaxInput.value = ""; break;
    case "resolution": els.resolutionSelect.value = ""; break;
    case "content_rating": els.contentRatingInput.value = ""; break;
    case "watched": document.querySelector("input[name='watched'][value='']").checked = true; break;
  }
}

function renderActiveFilters() {
  const f = filters();
  const chips = [];

  if (f.q) chips.push({ label: `"${f.q}"`, key: "q" });
  if (f.genre) chips.push({ label: `Genre: ${f.genre}`, key: "genre" });
  if (f.year_min && f.year_max) chips.push({ label: `${f.year_min}–${f.year_max}`, key: "year" });
  else if (f.year_min) chips.push({ label: `From ${f.year_min}`, key: "year_min" });
  else if (f.year_max) chips.push({ label: `To ${f.year_max}`, key: "year_max" });
  if (f.resolution) chips.push({ label: formatResolution(f.resolution), key: "resolution" });
  if (f.content_rating) chips.push({ label: `Rating: ${f.content_rating}`, key: "content_rating" });
  if (f.watched === "true") chips.push({ label: "Watched", key: "watched" });
  if (f.watched === "false") chips.push({ label: "Unwatched", key: "watched" });
  if (state.listFilter && els.listSelect.value) {
    const listName = els.listSelect.options[els.listSelect.selectedIndex]?.text || "";
    const label = state.listFilter === "in_list" ? `In list: ${listName}` : `Not in list: ${listName}`;
    chips.push({ label, key: "list_filter", type: "list" });
  }

  if (!chips.length) { els.activeFilters.hidden = true; return; }
  els.activeFilters.hidden = false;
  els.activeFilters.innerHTML = chips
    .map((c) => `<button class="filter-chip" data-clear-filter="${c.key}" data-chip-type="${c.type || "filter"}">${escapeHtml(c.label)} ×</button>`)
    .join("");
}

// ── Layout toggles ─────────────────────────────────────────────────────────

function setFiltersCollapsed(collapsed) {
  els.filterPanel.dataset.collapsed = collapsed ? "true" : "false";
  els.filterFields.hidden = collapsed;
  els.toggleFiltersButton.textContent = collapsed ? "Show" : "Hide";
}

function setSidebarOpen(open) {
  els.sidebar.dataset.open = open ? "true" : "false";
  els.sidebarToggleButton.setAttribute("aria-expanded", open ? "true" : "false");
}

function showMissingView() { els.tableFrame.hidden = true; els.missingView.hidden = false; }
function closeMissingView() { els.missingView.hidden = true; els.tableFrame.hidden = false; }

// ── List filter ────────────────────────────────────────────────────────────

function setListFilter(filter) {
  state.listFilter = filter;
  state.page = 1;
  if (lastComparison) renderCoverage(lastComparison);
  closeMissingView();
  refreshMovies();
}

// ── Movie detail panel ─────────────────────────────────────────────────────

function showMovieDetail(movie) {
  const thumb = posterUrl(movie);
  const genres = (movie.genres || []).map((g) =>
    `<button class="genre-btn" data-filter-genre="${escapeHtml(g)}">${escapeHtml(g)}</button>`
  ).join('<span class="genre-sep">&middot;</span>');
  const directors = (movie.directors || []).join(", ") || "--";
  const watched = movie.view_count > 0;
  const ratings = (movie.omdb_ratings || []).map((r) => detailStat(r.Source, r.Value)).join("");
  const overviewStats = [
    detailStat("Released", movie.omdb_released),
    detailStat("Rated", movie.omdb_rated || movie.content_rating),
    detailStat("Runtime", movie.omdb_runtime || formatDuration(movie.duration_ms)),
    detailStat("Country", movie.omdb_country),
    detailStat("Language", movie.omdb_language),
    detailStat("Studio", movie.studio),
  ].join("");
  const ratingStats = [
    detailStat("Plex critic", formatRating(movie.rating)),
    detailStat("Plex audience", formatRating(movie.audience_rating)),
    detailStat("IMDb", movie.omdb_imdb_rating),
    detailStat("IMDb votes", movie.omdb_imdb_votes ? Number(movie.omdb_imdb_votes).toLocaleString() : ""),
    detailStat("Metascore", movie.omdb_metascore),
    detailStat("Rotten Tomatoes", movie.omdb_rt_rating),
    detailStat("Box office", movie.omdb_box_office),
    ratings,
  ].join("");
  const peopleSections = [
    detailText(directors.includes(",") ? "Directors" : "Director", directors),
    detailText("Writer", movie.omdb_writer),
    detailText("Cast", movie.omdb_actors),
  ].join("");
  const technicalStats = [
    detailStat("Resolution", formatResolution(movie.resolution)),
    detailStat("Bitrate", formatBitrate(movie.bitrate_kbps)),
    detailStat("Codec", movie.video_codec),
    detailStat("Plex duration", formatDuration(movie.duration_ms)),
    detailStat("Watched", watched ? `Yes (${movie.view_count}x)` : "No"),
    detailStat("Added to Plex", formatDate(movie.added_at)),
    detailStat("Last watched", movie.last_viewed_at ? formatDate(movie.last_viewed_at) : ""),
  ].join("");

  els.movieDetailContent.innerHTML = `
    ${thumb ? `<div class="detail-poster"><img src="${escapeHtml(thumb)}" alt="${escapeHtml(movie.title)} poster" /></div>` : ""}
    <div class="detail-body">
      <div>
        <p id="detailTitle" class="detail-title">${escapeHtml(movie.title)}</p>
        <p class="detail-subtitle">${escapeHtml(String(movie.year || "--"))}${movie.omdb_runtime ? " &middot; " + escapeHtml(movie.omdb_runtime) : ""}${movie.omdb_rated ? " &middot; " + escapeHtml(movie.omdb_rated) : ""}</p>
        ${genres ? `<div class="movie-meta" style="margin-top:6px">${genres}</div>` : ""}
      </div>
      ${detailText("Plot", movie.omdb_plot || movie.summary)}
      ${detailGroup("Overview", `<div class="detail-grid">${overviewStats}</div>`)}
      ${detailGroup("Ratings", `<div class="detail-grid">${ratingStats}</div>`)}
      ${detailGroup("Cast and Crew", peopleSections)}
      ${detailGroup("Awards", detailText("Awards", movie.omdb_awards))}
      ${detailGroup("Technical", `<div class="detail-grid">${technicalStats}</div>`)}
    </div>`;

  els.movieDetail.hidden = false;
}
function hideMovieDetail() {
  els.movieDetail.hidden = true;
}

// ── Render: movies table ───────────────────────────────────────────────────

function renderMovies(page) {
  state.total = page.total;
  currentPageMovies = page.items;
  const totalPages = Math.max(1, Math.ceil(page.total / page.per_page));
  els.pageLabel.textContent = `${page.page} / ${totalPages}`;
  els.resultCount.textContent = `${page.total.toLocaleString()} movie${page.total === 1 ? "" : "s"}`;
  els.prevPageButton.disabled = page.page <= 1;
  els.nextPageButton.disabled = page.page >= totalPages;
  els.emptyState.hidden = page.items.length > 0;

  if (els.exportFilteredLink) {
    els.exportFilteredLink.href = buildExportUrl();
  }

  els.moviesBody.innerHTML = page.items
    .map((movie) => {
      const thumb = posterUrl(movie);
      const genreHtml = movie.genres?.length
        ? movie.genres.slice(0, 3).map((g, i) =>
            `${i > 0 ? '<span class="genre-sep">·</span>' : ""}<button class="genre-btn" data-filter-genre="${escapeHtml(g)}">${escapeHtml(g)}</button>`
          ).join("")
        : "";
      const watched = movie.view_count > 0;
      const inList = matchedPlexKeys.has(movie.plex_rating_key);
      return `
        <tr data-movie-key="${escapeHtml(movie.plex_rating_key)}" data-in-list="${inList}">
          <td>
            <div class="movie-title">
              ${thumb
                ? `<img class="poster-thumb" src="${escapeHtml(thumb)}" alt="" loading="lazy" />`
                : '<span class="poster-thumb" aria-hidden="true"></span>'
              }
              <div>
                <strong>${escapeHtml(movie.title)}</strong>
                <div class="muted">${escapeHtml(valueOrDash(movie.content_rating))}</div>
                ${genreHtml ? `<div class="movie-meta">${genreHtml}</div>` : ""}
              </div>
            </div>
          </td>
          <td data-label="Year">${escapeHtml(valueOrDash(movie.year))}</td>
          <td data-label="Duration">${escapeHtml(formatDuration(movie.duration_ms))}</td>
          <td data-label="Ratings"><span class="rating-stack"><span>Plex ${escapeHtml(formatRating(movie.rating))}</span>${movie.omdb_imdb_rating ? `<span>IMDb ${escapeHtml(movie.omdb_imdb_rating)}</span>` : ""}${movie.omdb_rt_rating ? `<span>RT ${escapeHtml(movie.omdb_rt_rating)}</span>` : ""}</span></td>
          <td data-label="Bitrate">${escapeHtml(formatBitrate(movie.bitrate_kbps))}</td>
          <td data-label="Resolution">${escapeHtml(formatResolution(movie.resolution))}</td>
          <td data-label="Watched" class="${watched ? "status-good" : "status-bad"}">${watched ? "Yes" : "No"}</td>
        </tr>`;
    })
    .join("");

  updateSortDropdown();
  updateSortIndicators();
}

// ── Render: health panel ───────────────────────────────────────────────────

function renderHealth(metrics) {
  const values = [
    ["Movies", metrics.total_movies], ["Watched", metrics.total_watched],
    ["Lists", metrics.lists_loaded], ["LB entries", metrics.letterboxd_entries],
    ["Matched", metrics.matched_entries], ["Missing", metrics.unmatched_entries],
    ["Match rate", formatPercent(metrics.match_rate)], ["Medium conf.", metrics.medium_confidence],
    ["No match", metrics.no_match], ["Review queue", metrics.pending_review],
  ];
  els.healthGrid.innerHTML = values
    .map(([l, v]) => `<div><span>${escapeHtml(l)}</span><strong>${escapeHtml(String(v))}</strong></div>`)
    .join("");
  els.healthLists.innerHTML = metrics.list_coverage.length
    ? metrics.list_coverage.map((list) => `
        <article>
          <strong>${escapeHtml(list.name)}</strong>
          <span>${escapeHtml(formatPercent(list.coverage_pct))} covered</span>
          <span>${escapeHtml(String(list.in_plex))} in Plex / ${escapeHtml(String(list.missing))} missing</span>
        </article>`).join("")
    : '<div class="empty-state compact"><strong>No lists loaded</strong></div>';
}

// ── Render: Letterboxd lists ───────────────────────────────────────────────

function renderLists(lists) {
  if (!lists.length) { els.listSelect.innerHTML = '<option value="">None loaded</option>'; return; }
  els.listSelect.innerHTML = [
    '<option value="">Select list</option>',
    ...lists.map((l) => `<option value="${l.id}">${escapeHtml(l.name)}</option>`),
  ].join("");
}

// ── Render: coverage stats ─────────────────────────────────────────────────

function renderCoverage(result) {
  lastComparison = result;
  matchedPlexKeys = new Set(result.matched_plex_keys || []);
  const listId = els.listSelect.value;
  const hasStats = listId && typeof result.coverage_pct === "number";

  if (hasStats) {
    const inBothActive = state.listFilter === "in_list";
    const notInListActive = state.listFilter === "not_in_list";
    els.coverageSummary.innerHTML = `
      <div><dt>Coverage</dt><dd>${formatPercent(result.coverage_pct)}</dd></div>
      <div><dt>In Plex</dt><dd>
        <button class="stat-filter-btn" data-list-view="in_list" data-active="${inBothActive}">${result.in_both.length}</button>
      </dd></div>
      <div><dt>Missing from Plex</dt><dd>
        <button class="stat-filter-btn" data-list-view="missing">${result.lb_only.length}</button>
      </dd></div>
      <div><dt>Not in list</dt><dd>
        <button class="stat-filter-btn" data-list-view="not_in_list" data-active="${notInListActive}">${result.plex_only.length}</button>
      </dd></div>`;
  } else {
    matchedPlexKeys = new Set();
    els.coverageSummary.innerHTML = `
      <div><dt>Coverage</dt><dd>--</dd></div>
      <div><dt>In Plex</dt><dd>--</dd></div>
      <div><dt>Missing from Plex</dt><dd>--</dd></div>
      <div><dt>Not in list</dt><dd>--</dd></div>`;
  }

  if (listId) {
    els.diffCsvLink.href = `/api/export/letterboxd-diff-csv?list_id=${listId}`;
    const listName = els.listSelect.options[els.listSelect.selectedIndex].text;
    els.diffCsvLink.download = `plexsort-diff-${listName.toLowerCase().replace(/\s+/g, "-")}.csv`;
    els.exportLinks.hidden = false;
  } else {
    els.exportLinks.hidden = true;
  }
}

// ── Render: missing view ───────────────────────────────────────────────────

function sortMissingEntries(entries) {
  const dir = state.missingDir === "asc" ? 1 : -1;
  return [...entries].sort((a, b) => {
    if (state.missingSort === "title") return dir * String(a.title ?? "").localeCompare(b.title ?? "");
    if (state.missingSort === "year") return dir * ((a.year ?? 0) - (b.year ?? 0));
    return dir * ((a.list_position ?? 9999) - (b.list_position ?? 9999));
  });
}

function mkArrow(col) {
  return state.missingSort === col ? (state.missingDir === "asc" ? " ↑" : " ↓") : "";
}

function renderMissingView(lbOnly, listName) {
  els.missingViewTitle.textContent = `Missing from Plex — ${listName} (${lbOnly.length})`;
  const sorted = sortMissingEntries(lbOnly);
  const rows = sorted.length
    ? sorted.map((e) => `
        <tr>
          <td>${escapeHtml(String(e.list_position ?? ""))}</td>
          <td>${escapeHtml(e.title)}</td>
          <td>${escapeHtml(String(e.year ?? "--"))}</td>
          <td>${e.lb_rating ? escapeHtml(String(e.lb_rating)) : "--"}</td>
          <td>${e.lb_film_url
            ? `<a href="${escapeHtml(e.lb_film_url)}" target="_blank" rel="noopener noreferrer">Letterboxd ↗</a>`
            : "--"}</td>
        </tr>`).join("")
    : `<tr><td colspan="5"><div class="empty-state compact"><strong>Nothing missing</strong></div></td></tr>`;

  els.missingList.innerHTML = `
    <p class="missing-note">Films on this list not yet in your Plex library. Future: auto-download queue via qBittorrent.</p>
    <div class="table-frame">
      <table class="missing-table">
        <thead><tr>
          <th data-missing-sort="position">#${mkArrow("position")}</th>
          <th data-missing-sort="title">Title${mkArrow("title")}</th>
          <th data-missing-sort="year">Year${mkArrow("year")}</th>
          <th>LB Rating</th>
          <th>Link</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  showMissingView();
}

// ── Data loaders ───────────────────────────────────────────────────────────

async function loadStats() {
  const stats = await apiFetch("/stats");
  if (els.totalMovies) els.totalMovies.textContent = `${stats.total_movies.toLocaleString()} films`;
}

async function loadHealth() { renderHealth(await apiFetch("/health/metrics")); }

async function loadMovies() {
  const page = await apiFetch(`/movies?${movieParams()}`);
  renderMovies(page);
}

async function loadLists() { renderLists(await apiFetch("/lists")); }

async function loadGenres() {
  try {
    const genres = await apiFetch("/genres");
    if (els.genreDatalist) {
      els.genreDatalist.innerHTML = genres.map((g) => `<option value="${escapeHtml(g)}">`).join("");
    }
  } catch { /* non-critical */ }
}

async function loadCoverage({ autoShowMissing = true } = {}) {
  const id = els.listSelect.value;
  if (!id) {
    state.listFilter = null;
    lastComparison = null;
    matchedPlexKeys = new Set();
    renderCoverage({ coverage_pct: "--", in_both: [], lb_only: [], plex_only: [], matched_plex_keys: [] });
    renderActiveFilters();
    closeMissingView();
    return;
  }
  const comparison = await apiFetch(`/lists/${id}/compare`);
  renderCoverage(comparison);
  renderActiveFilters();
  if (autoShowMissing && comparison.lb_only.length > 0) {
    const listName = els.listSelect.options[els.listSelect.selectedIndex]?.text || "";
    renderMissingView(comparison.lb_only, listName);
  }
}

async function refreshMovies() {
  try {
    await loadMovies();
    renderActiveFilters();
    pushUrlState();
  } catch (error) {
    showToast(error.message);
  }
}

// ── Event binding ──────────────────────────────────────────────────────────

function bindEvents() {
  const debouncedRefresh = debounce(() => { state.page = 1; refreshMovies(); });

  [els.searchInput, els.yearMinInput, els.yearMaxInput, els.genreInput,
   els.resolutionSelect, els.contentRatingInput].forEach((el) => el.addEventListener("input", debouncedRefresh));

  document.querySelectorAll("input[name='watched']").forEach((el) => el.addEventListener("change", debouncedRefresh));

  document.querySelectorAll("th button[data-sort]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sort = btn.dataset.sort;
      if (state.sort === sort) { state.dir = state.dir === "asc" ? "desc" : "asc"; }
      else { state.sort = sort; state.dir = "asc"; }
      refreshMovies();
    });
  });

  els.sortSelect.addEventListener("change", () => {
    state.sort = els.sortSelect.value;
    state.page = 1;
    refreshMovies();
  });

  els.sortDirButton.addEventListener("click", () => {
    state.dir = state.dir === "asc" ? "desc" : "asc";
    refreshMovies();
  });

  els.perPageSelect.addEventListener("change", () => {
    state.perPage = parseInt(els.perPageSelect.value, 10);
    state.page = 1;
    refreshMovies();
  });

  // Movie row clicks: genre filter or detail panel
  els.moviesBody.addEventListener("click", (event) => {
    const genreTarget = event.target.closest("[data-filter-genre]");
    if (genreTarget) {
      els.genreInput.value = genreTarget.dataset.filterGenre;
      state.page = 1;
      refreshMovies();
      return;
    }
    const row = event.target.closest("tr[data-movie-key]");
    if (!row) return;
    const movie = currentPageMovies.find((m) => m.plex_rating_key === row.dataset.movieKey);
    if (movie) showMovieDetail(movie);
  });

  // Movie detail panel: genre clicks inside detail
  els.movieDetailContent.addEventListener("click", (event) => {
    const genreTarget = event.target.closest("[data-filter-genre]");
    if (!genreTarget) return;
    els.genreInput.value = genreTarget.dataset.filterGenre;
    hideMovieDetail();
    state.page = 1;
    refreshMovies();
  });

  els.closeMovieDetailButton.addEventListener("click", hideMovieDetail);
  els.movieDetailBackdrop.addEventListener("click", hideMovieDetail);

  // Active filter chip dismiss
  els.activeFilters.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-clear-filter]");
    if (!chip) return;
    const key = chip.dataset.clearFilter;
    if (key === "list_filter") { setListFilter(null); }
    else { clearFilter(key); state.page = 1; refreshMovies(); }
  });

  // Coverage stat buttons
  els.coverageSummary.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-list-view]");
    if (!btn || !lastComparison) return;
    const view = btn.dataset.listView;
    if (view === "missing") {
      const listName = els.listSelect.options[els.listSelect.selectedIndex]?.text || "";
      renderMissingView(lastComparison.lb_only, listName);
    } else if (view === "in_list") {
      setListFilter(state.listFilter === "in_list" ? null : "in_list");
    } else if (view === "not_in_list") {
      setListFilter(state.listFilter === "not_in_list" ? null : "not_in_list");
    }
  });

  // Missing view sort headers
  els.missingList.addEventListener("click", (event) => {
    const th = event.target.closest("[data-missing-sort]");
    if (!th || !lastComparison) return;
    const col = th.dataset.missingSort;
    if (state.missingSort === col) { state.missingDir = state.missingDir === "asc" ? "desc" : "asc"; }
    else { state.missingSort = col; state.missingDir = "asc"; }
    const listName = els.listSelect.options[els.listSelect.selectedIndex]?.text || "";
    renderMissingView(lastComparison.lb_only, listName);
  });

  els.closeMissingViewButton.addEventListener("click", closeMissingView);

  els.prevPageButton.addEventListener("click", () => { state.page = Math.max(1, state.page - 1); refreshMovies(); });
  els.nextPageButton.addEventListener("click", () => { state.page += 1; refreshMovies(); });

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

  els.sidebarToggleButton.addEventListener("click", () => {
    setSidebarOpen(els.sidebar.dataset.open !== "true");
  });

  els.listSelect.addEventListener("change", () => {
    state.listFilter = null;
    state.missingSort = "position";
    state.missingDir = "asc";
    closeMissingView();
    pushUrlState();
    loadCoverage().catch((e) => showToast(e.message));
  });

  els.settingsButton.addEventListener("click", async () => {
    els.settingsPanel.hidden = !els.settingsPanel.hidden;
    if (!els.settingsPanel.hidden) {
      try { await loadHealth(); } catch (e) { showToast(e.message); }
    }
  });
  els.closeSettingsButton.addEventListener("click", () => { els.settingsPanel.hidden = true; });

  // ── Keyboard shortcuts ─────────────────────────────────────────────────
  document.addEventListener("keydown", (e) => {
    // Always handle Escape regardless of focus
    if (e.key === "Escape") {
      if (!els.movieDetail.hidden) { hideMovieDetail(); return; }
      if (!els.settingsPanel.hidden) { els.settingsPanel.hidden = true; return; }
      if (document.activeElement && inInput()) { document.activeElement.blur(); }
      return;
    }
    if (inInput()) return;

    if (e.key === "/" || e.key === "s") {
      e.preventDefault();
      els.searchInput.focus();
      els.searchInput.select();
      return;
    }
    if (e.key === "g") {
      e.preventDefault();
      els.genreInput.focus();
      els.genreInput.select();
      return;
    }
    if (e.key === "ArrowLeft" && !els.prevPageButton.disabled) {
      state.page = Math.max(1, state.page - 1);
      refreshMovies();
      return;
    }
    if (e.key === "ArrowRight" && !els.nextPageButton.disabled) {
      state.page += 1;
      refreshMovies();
    }
  });
}

// ── Init ───────────────────────────────────────────────────────────────────

async function init() {
  const urlState = parseUrlState();
  const isMobile = window.matchMedia("(max-width: 860px)").matches;
  if (isMobile) { setSidebarOpen(false); setFiltersCollapsed(false); }

  bindEvents();
  updateSortDropdown();
  updateSortIndicators();
  renderActiveFilters();

  try {
    await Promise.all([loadStats(), loadLists(), loadGenres()]);
    if (urlState.listId) els.listSelect.value = urlState.listId;
    await Promise.all([loadMovies(), loadCoverage({ autoShowMissing: false })]);
    await loadHealth();
  } catch (error) {
    showToast(error.message);
  }
}

init();
