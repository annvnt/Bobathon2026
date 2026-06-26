/** Chat tab — product / ingredient regulation lookup */

let chatRegulationsById = {};
let chatTermSections = {};

function escChat(s) {
  if (!s) return "";
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function escRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightTermsInText(text, terms) {
  let html = escChat(text);
  const sorted = [...(terms || [])].sort((a, b) => b.length - a.length);
  for (const term of sorted) {
    const re = new RegExp(`(\\b${escRegExp(term)}\\b)`, "gi");
    html = html.replace(re, '<mark class="section-highlight">$1</mark>');
  }
  return html;
}

function renderMessageParts(parts) {
  return (parts || [])
    .map((p) => {
      if (p.type === "text") return escChat(p.content);
      if (p.type === "term") {
        const ids = (p.regulation_ids || []).join(",");
        return `<button type="button" class="term-link" data-term="${escChat(p.term)}" data-reg-ids="${escChat(ids)}">${escChat(p.term)}</button>`;
      }
      return "";
    })
    .join("");
}

function renderRegulationSections(reg) {
  if (!reg.sections?.length) return "";
  return `
    <div class="chat-sections">
      <p class="chat-sections-heading">Relevant passages</p>
      ${reg.sections
        .map(
          (sec, i) => `
        <div class="chat-section-block" id="section-${escChat(reg.id)}-${i}" data-terms="${escChat((sec.matched_terms || []).join(","))}">
          <div class="chat-section-label">${escChat(sec.label)}</div>
          <p class="chat-section-text">${highlightTermsInText(sec.text, sec.matched_terms)}</p>
        </div>
      `,
        )
        .join("")}
    </div>
  `;
}

function renderRegulationCards(regulations) {
  if (!regulations?.length) return "";
  return `
    <div class="chat-reg-list">
      <p class="chat-reg-heading">Matching regulations</p>
      ${regulations
        .map(
          (r) => `
        <article class="chat-reg-card" data-reg-id="${escChat(r.id)}">
          <div class="chat-reg-card-head">
            <span class="chat-reg-source">${escChat(r.source)}</span>
            ${r.family ? `<span class="chat-reg-family">${escChat(r.family)}</span>` : ""}
            <span class="chat-reg-score">${r.match_score}% match</span>
          </div>
          <h3 class="chat-reg-title">
            ${r.url ? `<a href="${escChat(r.url)}" class="link" target="_blank" rel="noopener">${escChat(r.title)}</a>` : escChat(r.title)}
          </h3>
          <p class="chat-reg-ref">${escChat(r.reference)}</p>
          ${r.excerpt && !r.sections?.length ? `<p class="chat-reg-excerpt">${highlightTermsInText(r.excerpt, r.matched_terms)}</p>` : ""}
          ${renderRegulationSections(r)}
          <div class="chat-reg-actions">
            ${r.url ? `<a href="${escChat(r.url)}" class="btn btn-soft btn-sm" target="_blank" rel="noopener">Official law</a>` : ""}
            ${r.gadi_url ? `<a href="${escChat(r.gadi_url)}" class="btn btn-soft btn-sm" target="_blank" rel="noopener">GADI JSON</a>` : ""}
            <button type="button" class="btn btn-soft btn-sm chat-read-text" data-reg-id="${escChat(r.id)}">Read full text</button>
          </div>
        </article>
      `,
        )
        .join("")}
    </div>
  `;
}

function appendUserMessage(text) {
  const box = document.getElementById("chat-messages");
  const el = document.createElement("div");
  el.className = "chat-bubble chat-user";
  el.textContent = text;
  box.appendChild(el);
  box.scrollTop = box.scrollHeight;
}

function appendAssistantMessage(html) {
  const box = document.getElementById("chat-messages");
  const el = document.createElement("div");
  el.className = "chat-bubble chat-assistant";
  el.innerHTML = html;
  box.appendChild(el);
  bindChatInteractions(el);
  box.scrollTop = box.scrollHeight;
}

function regulationForId(id) {
  return chatRegulationsById[id] || null;
}

function flashSection(el) {
  el.classList.add("section-flash");
  setTimeout(() => el.classList.remove("section-flash"), 2200);
}

function jumpToTerm(term, regIds) {
  const needle = term.toLowerCase();
  const card = document.querySelector(`.chat-reg-card[data-reg-id="${CSS.escape(regIds[0] || "")}"]`);
  if (card) card.scrollIntoView({ behavior: "smooth", block: "start" });

  for (const id of regIds) {
    const reg = regulationForId(id);
    if (!reg?.sections?.length) continue;
    for (let i = 0; i < reg.sections.length; i++) {
      const sec = reg.sections[i];
      const terms = (sec.matched_terms || []).map((t) => t.toLowerCase());
      if (terms.includes(needle)) {
        const el = document.getElementById(`section-${id}-${i}`);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          flashSection(el);
          return true;
        }
      }
    }
  }

  const hits = chatTermSections[term] || chatTermSections[term.toLowerCase()] || [];
  if (hits.length) {
    const hit = hits[0];
    const cardEl = document.querySelector(`.chat-reg-card[data-reg-id="${CSS.escape(hit.regulation_id)}"]`);
    if (cardEl) {
      cardEl.scrollIntoView({ behavior: "smooth", block: "start" });
      const blocks = cardEl.querySelectorAll(".chat-section-block");
      for (const block of blocks) {
        const blockTerms = (block.dataset.terms || "").toLowerCase().split(",");
        if (blockTerms.includes(needle)) {
          block.scrollIntoView({ behavior: "smooth", block: "center" });
          flashSection(block);
          return true;
        }
      }
    }
  }

  const reg = regulationForId(regIds[0]);
  if (reg && typeof window.showRegulationText === "function") {
    window.showRegulationText(reg);
    return true;
  }
  return false;
}

function bindChatInteractions(root) {
  root.querySelectorAll(".term-link").forEach((btn) => {
    btn.addEventListener("click", () => {
      const ids = (btn.dataset.regIds || "").split(",").filter(Boolean);
      const term = btn.dataset.term || "";
      if (!jumpToTerm(term, ids)) {
        showToast?.("No matching passage found for this term.");
      }
    });
  });

  root.querySelectorAll(".chat-read-text").forEach((btn) => {
    btn.addEventListener("click", () => {
      const reg = regulationForId(btn.dataset.regId);
      if (reg && typeof window.showRegulationText === "function") {
        window.showRegulationText(reg);
      }
    });
  });
}

async function submitChat(query) {
  const submitBtn = document.getElementById("chat-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Searching…";

  const loading = document.createElement("div");
  loading.className = "chat-bubble chat-assistant chat-loading";
  loading.textContent = "Searching EUR-Lex and Open Legal Data, extracting relevant passages…";
  document.getElementById("chat-messages").appendChild(loading);

  try {
    const res = await fetch("/api/chat/lookup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    loading.remove();

    if (!res.ok) {
      appendAssistantMessage(`<p class="chat-error">${escChat(data.error || "Lookup failed.")}</p>`);
      return;
    }

    chatRegulationsById = {};
    chatTermSections = data.term_sections || {};
    (data.regulations || []).forEach((r) => {
      chatRegulationsById[r.id] = r;
    });

    const body = `<div class="chat-message-body">${renderMessageParts(data.message_parts)}</div>${renderRegulationCards(data.regulations)}`;
    appendAssistantMessage(body);
  } catch (e) {
    loading.remove();
    appendAssistantMessage(`<p class="chat-error">Could not reach the server: ${escChat(e.message)}</p>`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Find regulations";
  }
}

document.getElementById("chat-form")?.addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const query = input.value.trim();
  if (!query) return;
  appendUserMessage(query);
  input.value = "";
  submitChat(query);
});

let presentProducts = [];

function parseCountries(raw) {
  return raw
    .split(/[,;]+/)
    .map((c) => c.trim().toUpperCase())
    .filter(Boolean);
}

function updatePresentMeta(productId) {
  const meta = document.getElementById("present-meta");
  const product = presentProducts.find((p) => p.product_id === productId);
  if (!product || !meta) {
    if (meta) meta.hidden = true;
    return;
  }
  const streams = (product.compliance_streams || []).join(", ") || "—";
  const markets = (product.markets || []).join(", ") || "EU";
  meta.textContent = `${product.company} · labels: ${streams} · markets: ${markets}`;
  meta.hidden = false;
  const countriesInput = document.getElementById("present-countries");
  if (countriesInput && !countriesInput.dataset.touched) {
    countriesInput.value = markets.includes("EU") ? "DE, EU" : markets;
  }
}

async function loadPresentProducts() {
  const select = document.getElementById("present-product");
  if (!select) return;
  try {
    const data = await fetch("/api/mcp/products").then((r) => r.json());
    presentProducts = data.products || [];
    presentProducts.forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.product_id;
      opt.textContent = `${p.product_id} — ${p.name}`;
      select.appendChild(opt);
    });
    select.addEventListener("change", () => updatePresentMeta(select.value));
  } catch (e) {
    console.warn("Could not load products", e);
  }
}

function setChatMode(mode) {
  const presentPanel = document.getElementById("present-panel");
  const freePanel = document.getElementById("free-chat-panel");
  document.querySelectorAll(".chat-mode-tab").forEach((tab) => {
    const active = tab.dataset.chatMode === mode;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  if (presentPanel) presentPanel.hidden = mode !== "present";
  if (freePanel) freePanel.hidden = mode !== "free";
}

document.querySelectorAll(".chat-mode-tab").forEach((tab) => {
  tab.addEventListener("click", () => setChatMode(tab.dataset.chatMode || "present"));
});

async function submitPresent(productId, countries) {
  const submitBtn = document.getElementById("present-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "Fetching laws…";

  const loading = document.createElement("div");
  loading.className = "chat-bubble chat-assistant chat-loading";
  loading.textContent = "AI request: resolving labels and markets, fetching EU + German regulation texts…";
  document.getElementById("chat-messages").appendChild(loading);

  try {
    const res = await fetch("/api/mcp/present", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId, countries }),
    });
    const data = await res.json();
    loading.remove();

    if (!res.ok) {
      appendAssistantMessage(`<p class="chat-error">${escChat(data.message || data.error || "Lookup failed.")}</p>`);
      return;
    }

    const product = presentProducts.find((p) => p.product_id === productId);
    const userLine = `${product?.name || productId} · ${(data.labels || []).join(", ")} · ${(data.countries || []).join(", ")}`;
    appendUserMessage(`[AI] ${userLine}`);

    chatRegulationsById = {};
    chatTermSections = {};
    (data.regulations || []).forEach((r) => {
      chatRegulationsById[r.id] = r;
    });

    const body = `<div class="chat-message-body">${renderMessageParts(data.message_parts)}</div>${renderRegulationCards(data.regulations)}`;
    appendAssistantMessage(body);
  } catch (e) {
    loading.remove();
    appendAssistantMessage(`<p class="chat-error">Could not reach the server: ${escChat(e.message)}</p>`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Show applicable laws";
  }
}

document.getElementById("present-form")?.addEventListener("submit", (e) => {
  e.preventDefault();
  const productId = document.getElementById("present-product")?.value;
  const countries = parseCountries(document.getElementById("present-countries")?.value || "");
  if (!productId) return;
  submitPresent(productId, countries);
});

document.getElementById("present-countries")?.addEventListener("input", (e) => {
  e.target.dataset.touched = "1";
});

loadPresentProducts();
setChatMode("present");
