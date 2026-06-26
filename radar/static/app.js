let gapsData = [];
let sortKey = "deadline";
let sortAsc = true;
let severityFilter = "";

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

function severityBadge(s) {
  const c = ["critical", "high", "medium", "low"].includes(s) ? s : "low";
  return `<span class="badge ${c}">${esc(s || "low")}</span>`;
}

function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { el.hidden = true; }, 4000);
}

function filteredGaps() {
  if (!severityFilter) return gapsData;
  return gapsData.filter((g) => g.severity === severityFilter);
}

function renderGaps() {
  const sorted = [...filteredGaps()].sort((a, b) => {
    const av = a[sortKey] || "";
    const bv = b[sortKey] || "";
    return sortAsc ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
  });
  const tbody = document.querySelector("#gaps-table tbody");
  if (!sorted.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row">No gaps found. Run a scan or adjust the severity filter.</td></tr>`;
    return;
  }
  tbody.innerHTML = sorted.map((g) => `
    <tr>
      <td>${esc(g.company)}</td>
      <td>${esc(g.product)}</td>
      <td>${esc((g.regulation || "").slice(0, 72))}</td>
      <td>${severityBadge(g.severity)}</td>
      <td>${esc(g.deadline || "-")}</td>
      <td>${esc((g.gap || "").slice(0, 100))}</td>
      <td><a class="link" href="${esc(g.source_url)}" target="_blank" rel="noopener">View source</a></td>
    </tr>
  `).join("");
}

function renderRouting(updates) {
  const el = document.getElementById("routing-list");
  const routed = updates.filter((u) => u.router_matches && u.router_matches.length);
  if (!routed.length) {
    el.innerHTML = `<div class="routing-card"><p class="reg-title">No routed regulations yet</p><span class="cluster-tag">Run scan to execute MCP pipeline</span></div>`;
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
    el.innerHTML = `<li class="hil-item"><span class="hil-title">Queue empty — all router matches above confidence threshold</span></li>`;
    return;
  }
  el.innerHTML = items.map((item) => `
    <li class="hil-item" data-id="${esc(item.id)}">
      <span class="hil-title">${esc(item.title)} <span class="hil-conf">${item.router_confidence}% confidence</span></span>
      <button type="button" class="btn btn-ghost btn-approve" data-id="${esc(item.id)}">Approve top match</button>
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
      ? `${name}: local`
      : info.configured
        ? `${name}: API key set`
        : `${name}: no key`;
    return `<span class="${cls}">${esc(label)}</span>`;
  }).join("");
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
      const q = new URLSearchParams({
        source: update.source,
        reference: update.reference || "",
        title: update.title || "",
      });
      rec = await fetchJson(`/api/regulations?${q}`);
    }
  } else {
    const q = new URLSearchParams({
      source: update.source,
      reference: update.reference || "",
      title: update.title || "",
    });
    rec = await fetchJson(`/api/regulations?${q}`);
  }

  const cached = rec.from_cache ? " · served from cache" : " · fetched from API";
  metaEl.textContent = `${rec.source || update.source} · ${rec.reference || update.reference} · ${rec.chars || 0} chars${cached}`;
  bodyEl.textContent = rec.text || rec.regulation_text_preview || "No text available.";
}

function bindRegTextButtons(updates) {
  document.querySelectorAll(".btn-view-text").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = Number(btn.dataset.idx);
      try {
        await showRegulationText(updates[idx]);
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
    ? new Date(status.last_run).toLocaleString()
    : "not yet run";
  document.getElementById("last-run").textContent = `Last scan: ${lastRun}`;

  document.getElementById("gap-total").textContent = status.gap_count;
  document.getElementById("update-count").textContent = status.update_count;
  document.getElementById("vector-count").textContent = status.vector_entries ?? 0;
  document.getElementById("hil-count").textContent = status.hil_pending ?? 0;

  gapsData = await fetchJson("/api/gaps");
  const crit = gapsData.filter((g) => g.severity === "critical" || g.severity === "high").length;
  document.getElementById("gap-critical").textContent = crit;

  renderGaps();

  const updates = await fetchJson("/api/updates?limit=12");
  renderRouting(updates);
  await renderHil();

  const list = document.getElementById("updates-list");
  list.innerHTML = updates.length
    ? updates.map((u, idx) => `
      <li class="resource-tile">
        <p class="tile-title">${esc(u.title || u.reference)}</p>
        <span class="tile-meta">${esc(u.source)} &middot; ${esc(u.published_date)}${u.regulation_text_cached ? '<span class="cache-tag">cached</span>' : ""}</span>
        <span class="tile-family">${esc(u.regulation_family)}${u.cluster_id ? " · " + esc(u.cluster_id) : ""}</span>
        <button type="button" class="btn btn-ghost btn-view-text" data-idx="${idx}">View regulation text</button>
      </li>
    `).join("")
    : `<li class="resource-tile"><p class="tile-title">No updates yet</p><span class="tile-meta">Click Run scan to ingest from live sources.</span></li>`;
  bindRegTextButtons(updates);
}

async function pollJob(jobId) {
  for (let i = 0; i < 120; i++) {
    await new Promise((r) => setTimeout(r, 2000));
    const job = await fetchJson(`/api/job/${jobId}`);
    if (job.status === "completed") {
      showToast(`Scan complete: ${job.gaps_found} gaps, MCP ${job.mcp?.processed || 0} routed`);
      return job;
    }
    if (job.status === "failed") {
      throw new Error(job.error || "Scan failed");
    }
  }
  throw new Error("Scan timed out");
}

async function runScan(btn) {
  const buttons = [btn, ...document.querySelectorAll("#run-btn, #run-btn-hero, #run-btn-cta")];
  buttons.forEach((b) => {
    b.disabled = true;
    if (b === btn) b.textContent = "Scanning...";
  });
  try {
    const { job_id } = await fetch("/api/run", { method: "POST" }).then((r) => r.json());
    await pollJob(job_id);
    await refresh();
  } catch (e) {
    showToast("Scan failed: " + e.message);
  } finally {
    document.getElementById("run-btn").textContent = "Run scan";
    document.getElementById("run-btn-hero").textContent = "Run scan";
    document.getElementById("run-btn-cta").textContent = "Run scan now";
    buttons.forEach((b) => { b.disabled = false; });
  }
}

["run-btn", "run-btn-hero", "run-btn-cta"].forEach((id) => {
  document.getElementById(id).addEventListener("click", (e) => runScan(e.target));
});

document.getElementById("severity-filter").addEventListener("change", (e) => {
  severityFilter = e.target.value;
  renderGaps();
});

document.querySelectorAll("#gaps-table th[data-sort]").forEach((th) => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (sortKey === key) sortAsc = !sortAsc;
    else { sortKey = key; sortAsc = true; }
    renderGaps();
  });
});

document.getElementById("reg-modal-close").addEventListener("click", () => {
  document.getElementById("reg-text-modal").close();
});

refresh();
