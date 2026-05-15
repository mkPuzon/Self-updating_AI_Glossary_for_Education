const searchInput = document.getElementById("search-input");
const resultsList = document.getElementById("results-list");
const modalOverlay = document.getElementById("modal-overlay");
const detailPanel = document.getElementById("detail-panel");

modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) closeModal();
});

function closeModal() {
  modalOverlay.classList.add("hidden");
  detailPanel.innerHTML = "";
}

let debounceTimer;

searchInput.addEventListener("input", (e) => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => fetchKeywords(e.target.value.trim()), 250);
});

async function fetchKeywords(q) {
  try {
    const res = await fetch(`/api/keywords?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderResults(data);
  } catch {
    resultsList.innerHTML = `<p class="empty-state">Could not reach API.</p>`;
  }
}

function renderResults(keywords) {
  closeModal();

  if (keywords.length === 0) {
    resultsList.innerHTML = `<p class="empty-state">No terms found.</p>`;
    return;
  }

  resultsList.innerHTML = keywords
    .map(
      (k) => `
      <div class="result-item" data-keyword="${escapeAttr(k.keyword)}">
        <span class="keyword-name">${escapeHtml(k.keyword)}</span>
        <span class="keyword-count">${k.count} paper${k.count !== 1 ? "s" : ""}</span>
      </div>`
    )
    .join("");

  resultsList.querySelectorAll(".result-item").forEach((el) => {
    el.addEventListener("click", () => fetchDetail(el.dataset.keyword));
  });
}

async function fetchDetail(keyword) {
  try {
    const res = await fetch(`/api/keywords/${encodeURIComponent(keyword)}`);
    if (!res.ok) {
      detailPanel.innerHTML = `<div class="modal-main"><p class="empty-state">Term not found.</p></div><aside class="modal-sidebar"></aside><button class="close-btn">&times;</button>`;
      detailPanel.querySelector(".close-btn").addEventListener("click", closeModal);
      modalOverlay.classList.remove("hidden");
      return;
    }
    const data = await res.json();
    renderDetail(data);
  } catch {
    detailPanel.innerHTML = `<div class="modal-main"><p class="empty-state">Could not load details.</p></div><aside class="modal-sidebar"></aside><button class="close-btn">&times;</button>`;
    detailPanel.querySelector(".close-btn").addEventListener("click", closeModal);
    modalOverlay.classList.remove("hidden");
  }
}

function renderDetail(data) {
  const articleCards = (data.articles || [])
    .map(
      (art) => `
      <div class="article-card">
        <div class="article-title">
          <a href="${escapeAttr(art.arxiv_url)}" target="_blank" rel="noopener">
            ${escapeHtml(art.title)}
          </a>
        </div>
        <div class="article-meta">
          <span class="article-date">${escapeHtml(art.date_submitted || "")}</span>
          ${(art.tags || []).map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")}
        </div>
        <p class="article-abstract">${escapeHtml(art.abstract || "")}</p>
      </div>`
    )
    .join("");

  detailPanel.innerHTML = `
    <div class="modal-main">
      <div class="detail-header">
        <h2 class="detail-title">${escapeHtml(data.keyword)}</h2>
        <span class="detail-count">${data.count} paper${data.count !== 1 ? "s" : ""}</span>
      </div>
      <p class="detail-definition">${escapeHtml(data.definition || "")}</p>
      ${
        articleCards
          ? `<p class="articles-heading">Referenced in</p>
             <div class="article-cards">${articleCards}</div>`
          : ""
      }
    </div>
    <aside class="modal-sidebar">
      <p class="sidebar-heading">Related Terms</p>
      <div id="related-terms-list"></div>
    </aside>
    <button class="close-btn">&times;</button>
  `;
  detailPanel.querySelector(".close-btn").addEventListener("click", closeModal);
  modalOverlay.classList.remove("hidden");
  fetchRelatedTerms(data.keyword);
}

async function fetchRelatedTerms(keyword) {
  const list = document.getElementById("related-terms-list");
  if (!list) return;
  try {
    const res = await fetch(`/api/keywords/${encodeURIComponent(keyword)}/related`);
    if (!res.ok) return;
    const terms = await res.json();
    if (!terms.length) return;
    list.innerHTML = terms
      .map((t) => `<div class="related-term-item" data-keyword="${escapeAttr(t.keyword)}">${escapeHtml(t.keyword)}</div>`)
      .join("");
    list.querySelectorAll(".related-term-item").forEach((el) => {
      el.addEventListener("click", () => fetchDetail(el.dataset.keyword));
    });
  } catch {
    // endpoint not yet implemented — sidebar stays empty
  }
}


function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return String(str).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// Load all keywords on page start
fetchKeywords("");
