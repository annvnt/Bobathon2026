let gapsData = [];
let sortKey = "criticality";
let sortAsc = true;
let criticalityFilter = "";
let urgencyFilter = "";
let familyFilter = "";
let statusFilter = "";
let searchQuery = "";
let currentGap = null;

const CRIT_ORDER = { critical: 0, moderate: 1, administrative: 2 };
const URG_ORDER = { immediate: 0, short_term: 1, medium_term: 2, long_term: 3 };

async function fetchJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

function esc(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function critBadge(c) {
  const map = { critical: "critical", moderate: "medium", administrative: "low" };
  const cls = map[c] || "low";
  const label = { critical: "Critical", moderate: "Moderate", administrative: "Admin" }[c] || c;
  return `<span class="badge ${cls}">${esc(label)}</span>`;
}

function urgBadge(u) {
  const map = { immediate: "critical", short_term: "high", medium_term: "medium", long_term: "low" };
  const cls = map[u] || "low";
  const label = {
    immediate: "Act now",
    short_term: "Weeks",
    medium_term: "Plan",
    long_term: "Schedule",
  }[u] || u;
  return `<span class="badge ${cls}">${esc(label)}</span>`;
}

function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { el.hidden = true; }, 4000);
}

function filteredGaps() {
  return gapsData.filter((g) => {
    if (criticalityFilter && g.criticality !== criticalityFilter) return false;
    if (urgencyFilter && g.urgency !== urgencyFilter) return false;
    if (familyFilter && g.regulation_family !== familyFilter) return false;
    if (statusFilter && g.status !== statusFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const hay = `${g.company} ${g.product} ${g.regulation} ${g.gap}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderGaps() {
  const sorted = [...filteredGaps()].sort((a, b) => {
    if (sortKey === "criticality") {
      const av = CRIT_ORDER[a.criticality] ?? 9;
      const bv = CRIT_ORDER[b.criticality] ?? 9;
      if (av !== bv) return sortAsc ? av - bv : bv - av;
      const uav = URG_ORDER[a.urgency] ?? 9;
      const ubv = URG_ORDER[b.urgency] ?? 9;
      if (uav !== ubv) return uav - ubv;
      return String(a.deadline).localeCompare(String(b.deadline));
    }
    if (sortKey === "urgency") {
      const av = URG_ORDER[a.urgency] ?? 9;
      const bv = URG_ORDER[b.urgency] ?? 9;
      return sortAsc ? av - bv : bv - av;
    }
    const av = a[sortKey] || "";
    const bv = b[sortKey] || "";
    return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });

  const grid = document.getElementById("gaps-grid");
  if (!sorted.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <strong>No gaps match your filters</strong>
        Try clearing filters or run a scan to refresh your portfolio picture.
      </div>`;
    return;
  }

  grid.innerHTML = sorted.map((g, idx) => {
    const urgent = g.urgency === "immediate" || (g.days_remaining != null && g.days_remaining < 90);
    const critCls = `crit-${g.criticality || "moderate"}`;
    return `
    <article class="gap-card ${critCls}" data-idx="${idx}" tabindex="0" role="button">
      <div class="gap-card-top">
        <div class="gap-card-badges">${critBadge(g.criticality)} ${urgBadge(g.urgency)}</div>
      </div>
      <p class="gap-card-company">${esc(g.company)}</p>
      <h3 class="gap-card-product">${esc(g.product)}</h3>
      <p class="gap-card-reg">${esc(g.regulation_family)} · ${esc((g.regulation || "").slice(0, 64))}</p>
      <p class="gap-card-summary">${esc(g.gap)}</p>
      <div class="gap-card-footer">
        <span class="deadline-pill ${urgent ? "urgent" : ""}">📅 ${esc(g.deadline || "—")} · ${g.days_remaining ?? "?"} days</span>
        <span>${g.confidence_score ?? "—"}% match</span>
      </div>
    </article>`;
  }).join("");

  grid.querySelectorAll(".gap-card").forEach((card) => {
    const open = () => showGapDetail(sorted[Number(card.dataset.idx)]);
    card.addEventListener("click", open);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
    });
  });
}

function gapSection(title, body) {
  return `<section class="gap-section"><h3 class="gap-section-title">${esc(title)}</h3><p>${esc(body)}</p></section>`;
}

function showGapDetail(gap) {
  currentGap = gap;
  const modal = document.getElementById("gap-detail-modal");
  document.getElementById("gap-modal-badges").innerHTML =
    `${critBadge(gap.criticality)} ${urgBadge(gap.urgency)} <span class="badge medium">${esc(gap.status || "detected")}</span>`;
  document.getElementById("gap-modal-title").textContent = gap.product || "Gap detail";
  document.getElementById("gap-modal-meta").textContent =
    `${gap.company} · ${gap.regulation_family} · ${gap.deadline} (${gap.days_remaining} days) · ${gap.confidence_score}% confidence`;

  const actions = (gap.action_items || []).map((a) =>
    `<li><label><input type="checkbox"> <strong>${a.step}.</strong> ${esc(a.action)} <em>(${esc(a.owner)})</em></label></li>`
  ).join("");

  document.getElementById("gap-modal-sections").innerHTML = [
    gapSection("What you need to do", gap.requirement),
    gapSection("What's missing", gap.gap),
    gapSection("Why this applies to your product", gap.why_applies),
    gapSection("If you ignore this", gap.consequences),
    `<section class="gap-section"><h3 class="gap-section-title">Your action plan</h3><ol class="action-checklist">${actions}</ol><p class="tile-meta">${esc(gap.action_deadline_note || "")}</p></section>`,
    gapSection("How we matched this", gap.reasoning),
    `<p class="tile-meta"><a class="link" href="${esc(gap.source_url)}" target="_blank" rel="noopener">View official source</a> · updated ${esc(gap.fetched_at || "")}</p>`,
  ].join("");

  modal.showModal();
}

async function updateGapStatus(status) {
  if (!currentGap?.finding_id) return;
  await fetch(`/api/gaps/${encodeURIComponent(currentGap.finding_id)}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  currentGap.status = status;
  showToast(status === "resolved" ? "Marked as resolved — nice work!" : "Status saved");
  document.getElementById("gap-detail-modal").close();
  await loadGaps();
}

function renderRouting(updates) {
  const el = document.getElementById("routing-list");
  const routed = updates.filter((u) => u.router_matches && u.router_matches.length);
  if (!routed.length) {
    el.innerHTML = `<div class="routing-card"><p class="reg-title">No matches yet</p><span class="cluster-tag">Run a scan to map regulations to your product taxonomy.</span></div>`;
    return;
  }
  el.innerHTML = routed.slice(0, 6).map((u) => `
    <div class="routing-card">
      <p class="reg-title">${esc((u.title || u.reference || "").slice(0, 80))}</p>
      <span class="cluster-tag">${esc(u.source)} · cluster ${esc(u.cluster_id || "-")} · conf ${u.router_confidence || 0}%</span>
      <ul class="prob-list">
        ${(u.router_matches || []).map((m) => `
          <li><span>${esc(m.label || m.id)}</span><span class="prob-pct">${m.probability_pct}%</span></li>
        `).join("")}
      </ul>
    </div>
  `).join("");
}

async function renderHil() {
  const items = await fetchJson("/api/hil");
  const el = document.getElementById("hil-list");
  if (!items.length) {
    el.innerHTML = `<li class="hil-item"><span class="hil-title">All clear — nothing waiting for analyst review right now.</span></li>`;
    return;
  }
  el.innerHTML = items.map((item) => `
    <li class="hil-item" data-id="${esc(item.id)}">
      <span class="hil-title">${esc(item.title)} <span class="hil-conf">${item.router_confidence}% confidence</span></span>
      <button type="button" class="btn btn-soft btn-approve" data-id="${esc(item.id)}">Approve</button>
    </li>
  `).join("");
  el.querySelectorAll(".btn-approve").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      await fetch(`/api/hil/${encodeURIComponent(id)}/approve`, { method: "POST" });
      showToast("Approved: " + id);
      await renderHil();
    });
  });
}

function renderApiStatus(creds) {
  const el = document.getElementById("api-status");
  if (!creds) return;
  el.innerHTML = Object.entries(creds).map(([name, info]) => {
    let cls = "api-pill";
    if (info.mode === "local_files") cls += " local";
    else if (info.configured) cls += " live";
    else cls += " missing";
    const label = info.mode === "local_files"
      ? `${name} · local files`
      : info.configured
        ? `${name} · connected`
        : `${name} · not configured`;
    return `<span class="${cls}">${esc(label)}</span>`;
  }).join("");
}

async function loadGaps() {
  const params = new URLSearchParams();
  if (criticalityFilter) params.set("criticality", criticalityFilter);
  if (urgencyFilter) params.set("urgency", urgencyFilter);
  if (familyFilter) params.set("family", familyFilter);
  if (statusFilter) params.set("status", statusFilter);
  if (searchQuery) params.set("q", searchQuery);
  const qs = params.toString();
  gapsData = await fetchJson(`/api/gaps${qs ? `?${qs}` : ""}`);
  renderGaps();
}

async function showRegulationText(update) {
  const modal = document.getElementById("reg-text-modal");
  const titleEl = document.getElementById("reg-modal-title");
  const metaEl = document.getElementById("reg-modal-meta");
  const bodyEl = document.getElementById("reg-modal-body");
  titleEl.textContent = update.title || update.reference || "Regulation text";
  metaEl.textContent = "Loading…";
  bodyEl.textContent = "";
  modal.showModal();

  let rec;
  if (update.regulation_text_key) {
    rec = await fetchJson(`/api/regulations/${encodeURIComponent(update.regulation_text_key)}`);
    if (rec.status === "not_found") {
      const q = new URLSearchParams({ source: update.source, reference: update.reference || "", title: update.title || "" });
      rec = await fetchJson(`/api/regulations?${q}`);
    }
  } else {
    const q = new URLSearchParams({ source: update.source, reference: update.reference || "", title: update.title || "" });
    rec = await fetchJson(`/api/regulations?${q}`);
  }

  const cached = rec.from_cache ? " · served from cache" : " · fetched from API";
  metaEl.textContent = `${rec.source || update.source} · ${rec.reference || update.reference} · ${rec.chars || 0} chars${cached}`;
  bodyEl.textContent = rec.text || update.regulation_text_preview || "No text available.";
}

window.showRegulationText = showRegulationText;

function bindRegTextButtons(updates) {
  document.querySelectorAll(".btn-view-text").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await showRegulationText(updates[Number(btn.dataset.idx)]);
      } catch (e) {
        showToast("Could not load regulation text: " + e.message);
      }
    });
  });
}

async function refresh() {
  const status = await fetchJson("/api/status");
  renderApiStatus(status.api_credentials);
  const lastRun = status.last_run
    ? new Date(status.last_run).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
    : "never";
  document.getElementById("last-run").textContent = lastRun === "never" ? "No scan yet" : `Last scan · ${lastRun}`;

  document.getElementById("gap-total").textContent = status.gap_count;
  document.getElementById("update-count").textContent = status.update_count;
  document.getElementById("vector-count").textContent = status.vector_entries ?? 0;
  document.getElementById("hil-count").textContent = status.hil_pending ?? 0;

  await loadGaps();
  const crit = gapsData.filter((g) => g.criticality === "critical").length;
  document.getElementById("gap-critical").textContent = crit;

  const updates = await fetchJson("/api/updates?limit=12");
  renderRouting(updates);
  await renderHil();

  const list = document.getElementById("updates-list");
  list.innerHTML = updates.length
    ? updates.map((u, idx) => `
      <li class="resource-tile">
        <p class="tile-title">${esc(u.title || u.reference)}</p>
        <span class="tile-meta">${esc(u.source)} · ${esc(u.published_date)}${u.regulation_text_cached ? '<span class="cache-tag">cached</span>' : ""}</span>
        <span class="tile-family">${esc(u.regulation_family)}${u.cluster_id ? " · " + esc(u.cluster_id) : ""}</span>
        <button type="button" class="btn btn-soft btn-sm btn-view-text" data-idx="${idx}">Read full text</button>
      </li>
    `).join("")
    : `<li class="resource-tile"><p class="tile-title">No regulations yet</p><span class="tile-meta">Run a scan to pull live rules from EUR-Lex, ECHA, and more.</span></li>`;
  bindRegTextButtons(updates);
}

async function pollJob(jobId) {
  for (let i = 0; i < 120; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const job = await fetchJson(`/api/job/${jobId}`);
    if (job.status === "completed") {
      showToast(`Done! Found ${job.gaps_found} gaps across your portfolio.`);
      return job;
    }
    if (job.status === "failed") throw new Error(job.error || "Scan failed");
  }
  throw new Error("Scan timed out");
}

async function runScan(btn) {
  const buttons = [
    btn,
    ...document.querySelectorAll("#run-btn, #run-btn-hero, #run-btn-mobile"),
  ].filter(Boolean);
  const labels = new Map();
  buttons.forEach((b) => {
    labels.set(b, b.textContent);
    b.disabled = true;
    if (b === btn) b.textContent = "Scanning…";
  });
  try {
    const { job_id } = await fetch("/api/run", { method: "POST" }).then((r) => r.json());
    await pollJob(job_id);
    await refresh();
  } catch (e) {
    showToast("Scan didn't finish: " + e.message);
  } finally {
    buttons.forEach((b) => {
      b.disabled = false;
      b.textContent = labels.get(b);
    });
  }
}

["run-btn", "run-btn-hero", "run-btn-mobile"].forEach((id) => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("click", (e) => runScan(e.target));
});

["criticality-filter", "urgency-filter", "family-filter", "status-filter"].forEach((id) => {
  document.getElementById(id).addEventListener("change", (e) => {
    if (id === "criticality-filter") criticalityFilter = e.target.value;
    if (id === "urgency-filter") urgencyFilter = e.target.value;
    if (id === "family-filter") familyFilter = e.target.value;
    if (id === "status-filter") statusFilter = e.target.value;
    loadGaps();
  });
});

document.getElementById("gap-search").addEventListener("input", (e) => {
  searchQuery = e.target.value.trim();
  clearTimeout(document.getElementById("gap-search")._deb);
  document.getElementById("gap-search")._deb = setTimeout(loadGaps, 300);
});

document.getElementById("gap-sort")?.addEventListener("change", (e) => {
  sortKey = e.target.value;
  sortAsc = true;
  renderGaps();
});

function initNavHighlight() {
  const links = document.querySelectorAll(".nav-link");
  const sections = ["overview", "gaps-section", "review-section", "updates-section", "chat-section"];
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const id = entry.target.id;
        const navMap = {
          "gaps-section": "gaps",
          "review-section": "review",
          "updates-section": "updates",
          "chat-section": "chat",
        };
        const nav = navMap[id] || "overview";
        links.forEach((l) => l.classList.toggle("active", l.dataset.nav === nav));
      });
    },
    { rootMargin: "-30% 0px -55% 0px", threshold: 0 },
  );
  sections.forEach((id) => {
    const el = document.getElementById(id);
    if (el) observer.observe(el);
  });
}

document.getElementById("reg-modal-close").addEventListener("click", () => {
  document.getElementById("reg-text-modal").close();
});
document.getElementById("gap-modal-close").addEventListener("click", () => {
  document.getElementById("gap-detail-modal").close();
});
refresh();
initNavHighlight();
