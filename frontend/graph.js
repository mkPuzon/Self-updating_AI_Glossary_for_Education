const svg = d3.select("#graph-svg");
const container = document.getElementById("graph-container");
const tooltip = document.getElementById("graph-tooltip");
const status = document.getElementById("ctl-status");
const topNInput = document.getElementById("ctl-top-n");
const minEdgeInput = document.getElementById("ctl-min-edge");
const applyBtn = document.getElementById("ctl-apply");
const searchInput = document.getElementById("ctl-search");

const detailCache = new Map();
let tooltipHideTimer = null;
let simulation = null;
let rootG = null;
let nodeSel = null;
let linkSel = null;

const zoom = d3.zoom()
  .scaleExtent([0.02, 5])
  .on("zoom", (event) => rootG.attr("transform", event.transform));

svg.call(zoom);

function nodeRadius(count) {
  return Math.sqrt(count) * 15 + 20;
}

function linkWidth(value) {
  return Math.max(2, Math.sqrt(value) * 3);
}

async function loadGraph() {
  const topN = clampInt(topNInput.value, 20, 500, 100);
  const minEdge = clampInt(minEdgeInput.value, 1, 20, 2);
  status.textContent = "Loading…";
  searchInput.value = "";

  try {
    const res = await fetch(`/api/graph?top_n=${topN}&min_edge_score=${minEdge}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    status.textContent = `${data.nodes.length} nodes, ${data.links.length} edges`;
    renderGraph(data);
  } catch (err) {
    status.textContent = `Error: ${err.message}`;
  }
}

function renderGraph({ nodes, links }) {
  svg.selectAll("*").remove();

  const { width, height } = container.getBoundingClientRect();
  svg.attr("viewBox", [0, 0, width, height]);

  rootG = svg.append("g");

  linkSel = rootG.append("g")
    .attr("class", "graph-links")
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke-width", (d) => linkWidth(d.value));

  nodeSel = rootG.append("g")
    .attr("class", "graph-nodes")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .attr("class", "graph-node")
    .call(drag());

  nodeSel.append("circle")
    .attr("r", (d) => nodeRadius(d.count));

  nodeSel.append("text")
    .attr("class", "graph-label")
    .attr("dx", (d) => nodeRadius(d.count) + 6)
    .attr("dy", "0.35em")
    .text((d) => d.id);

  nodeSel
    .on("mouseenter", (event, d) => showTooltip(event, d))
    .on("mousemove", (event) => positionTooltip(event))
    .on("mouseleave", scheduleHideTooltip);

  tooltip.addEventListener("mouseenter", () => {
    if (tooltipHideTimer) clearTimeout(tooltipHideTimer);
  });
  tooltip.addEventListener("mouseleave", scheduleHideTooltip);

  if (simulation) simulation.stop();
  simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.id).distance(220).strength(0.4))
    .force("charge", d3.forceManyBody().strength(-400))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .on("tick", () => {
      linkSel
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      nodeSel.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

  applySearch(searchInput.value);
}

function drag() {
  return d3.drag()
    .on("start", (event, d) => {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    })
    .on("drag", (event, d) => {
      d.fx = event.x;
      d.fy = event.y;
    })
    .on("end", (event, d) => {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    });
}

function applySearch(query) {
  if (!nodeSel) return;
  const q = query.trim().toLowerCase();

  if (!q) {
    nodeSel.classed("graph-node--dim", false).classed("graph-node--match", false);
    linkSel.classed("graph-link--dim", false);
    return;
  }

  const matchedIds = new Set();
  nodeSel.each((d) => {
    if (d.id.toLowerCase().includes(q)) matchedIds.add(d.id);
  });

  nodeSel
    .classed("graph-node--match", (d) => matchedIds.has(d.id))
    .classed("graph-node--dim", (d) => !matchedIds.has(d.id));

  linkSel.classed("graph-link--dim", (d) =>
    !matchedIds.has(d.source.id) && !matchedIds.has(d.target.id)
  );
}

searchInput.addEventListener("input", (e) => applySearch(e.target.value));

async function showTooltip(event, d) {
  if (tooltipHideTimer) clearTimeout(tooltipHideTimer);
  tooltip.classList.remove("hidden");
  tooltip.innerHTML = `<div class="tooltip-title">${escapeHtml(d.id)}</div><p class="tooltip-loading">Loading…</p>`;
  positionTooltip(event);

  let detail = detailCache.get(d.id);
  if (!detail) {
    try {
      const res = await fetch(`/api/keywords/${encodeURIComponent(d.id)}`);
      if (!res.ok) throw new Error("not found");
      detail = await res.json();
      detailCache.set(d.id, detail);
    } catch {
      tooltip.innerHTML = `<div class="tooltip-title">${escapeHtml(d.id)}</div><p class="tooltip-loading">Could not load details.</p>`;
      return;
    }
  }

  if (!tooltip.classList.contains("hidden")) {
    tooltip.innerHTML = renderTooltipHtml(detail);
  }
}

function renderTooltipHtml(detail) {
  const articleHtml = (detail.articles || [])
    .map((art) => `
      <div class="tooltip-article">
        <div class="tooltip-article-title">
          <a href="${escapeAttr(art.arxiv_url)}" target="_blank" rel="noopener">
            ${escapeHtml(art.title)}
          </a>
        </div>
        <p class="tooltip-article-abstract">${escapeHtml(art.abstract || "")}</p>
      </div>`)
    .join("");

  return `
    <div class="tooltip-header">
      <span class="tooltip-title">${escapeHtml(detail.keyword)}</span>
      <span class="tooltip-count">${detail.count} paper${detail.count !== 1 ? "s" : ""}</span>
    </div>
    <p class="tooltip-definition">${escapeHtml(detail.definition || "")}</p>
    ${articleHtml ? `<div class="tooltip-articles">${articleHtml}</div>` : ""}
  `;
}

function positionTooltip(event) {
  const padding = 16;
  const rect = container.getBoundingClientRect();
  const x = event.clientX - rect.left + padding;
  const y = event.clientY - rect.top + padding;
  const tipRect = tooltip.getBoundingClientRect();
  const maxX = rect.width - tipRect.width - 8;
  const maxY = rect.height - tipRect.height - 8;
  tooltip.style.left = Math.max(8, Math.min(x, maxX)) + "px";
  tooltip.style.top = Math.max(8, Math.min(y, maxY)) + "px";
}

function scheduleHideTooltip() {
  if (tooltipHideTimer) clearTimeout(tooltipHideTimer);
  tooltipHideTimer = setTimeout(() => tooltip.classList.add("hidden"), 250);
}

function clampInt(raw, min, max, fallback) {
  const n = parseInt(raw, 10);
  if (isNaN(n)) return fallback;
  return Math.max(min, Math.min(max, n));
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

applyBtn.addEventListener("click", loadGraph);
window.addEventListener("resize", () => {
  if (!simulation) return;
  const { width, height } = container.getBoundingClientRect();
  svg.attr("viewBox", [0, 0, width, height]);
  simulation.force("center", d3.forceCenter(width / 2, height / 2));
  simulation.alpha(0.3).restart();
});

loadGraph();
