let lastJson = null;
let examplesById = {};

const TABS = [
  {
    id: "summary",
    title: "Mechanical system summary",
    buttons: [
      { label: "Mech system roll-up", example: "mech_system_summary", run: true },
      { label: "Counts by equip kind", example: "count_by_equip_kind", run: true },
      { label: "Class counts (points)", example: "class_counts", run: true },
      { label: "Equipment tree", example: "equipment_tree", run: true },
      { label: "Databases / TS store", example: "databases", run: true },
    ],
  },
  {
    id: "equipment",
    title: "List equipment",
    buttons: [
      { label: "AHUs", example: "list_ahus", run: true },
      { label: "AHU parts", example: "ahu_parts", run: true },
      { label: "Fans", example: "list_fans", run: true },
      { label: "VAV zones (by name)", example: "list_vav_zones", run: true },
      { label: "Typed VAVs", example: "list_vavs", run: true },
      { label: "Heat pumps", example: "list_heat_pumps", run: true },
      { label: "Boilers", example: "list_boilers", run: true },
      { label: "Chillers", example: "list_chillers", run: true },
      { label: "Cooling towers", example: "list_cooling_towers", run: true },
      { label: "Pumps", example: "list_pumps", run: true },
      { label: "Zones fed", example: "zones_fed", run: true },
    ],
  },
  {
    id: "points",
    title: "Points",
    buttons: [
      { label: "All points", example: "list_points", run: true },
      { label: "AHU points + refs", example: "points_of_ahus", run: true },
      { label: "VAV-zone points", example: "points_of_vav_zones", run: true },
      { label: "Points on other kinds", example: "points_by_equip_kind", run: true },
      { label: "Missing refs", example: "missing_refs", run: true },
    ],
  },
];

function setQuery(text) {
  document.getElementById("query").value = text || "";
}

function loadExample(id, { run = false } = {}) {
  const ex = examplesById[id];
  if (!ex) return;
  setQuery(ex.query);
  if (run) runQuery();
}

function bindButton(b) {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "ghost";
  btn.textContent = b.label;
  btn.addEventListener("click", () => loadExample(b.example, { run: !!b.run }));
  return btn;
}

function renderTabs() {
  const host = document.getElementById("tab-panels");
  host.innerHTML = "";
  for (const tab of TABS) {
    const panel = document.createElement("div");
    panel.className = "tab-panel" + (tab.id === "summary" ? " active" : "");
    panel.dataset.tab = tab.id;
    const h = document.createElement("h3");
    h.textContent = tab.title;
    panel.appendChild(h);
    const row = document.createElement("div");
    row.className = "quick";
    for (const b of tab.buttons) row.appendChild(bindButton(b));
    panel.appendChild(row);
    host.appendChild(panel);
  }

  document.querySelectorAll(".tab").forEach((tabBtn) => {
    tabBtn.addEventListener("click", () => {
      const id = tabBtn.dataset.tab;
      document.querySelectorAll(".tab").forEach((b) => {
        b.classList.toggle("active", b === tabBtn);
        b.setAttribute("aria-selected", b === tabBtn ? "true" : "false");
      });
      document.querySelectorAll(".tab-panel").forEach((p) => {
        p.classList.toggle("active", p.dataset.tab === id);
      });
    });
  });
}

function applyTheme(theme) {
  const next = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("brickts-theme", next);
  const btn = document.getElementById("theme-toggle");
  if (btn) btn.textContent = `Theme: ${next}`;
}

async function loadPresets() {
  const res = await fetch("/api/sparql/examples");
  const data = await res.json();
  examplesById = {};
  for (const ex of data.examples) examplesById[ex.id] = ex;
  renderTabs();
  if (examplesById.mech_system_summary) {
    loadExample("mech_system_summary", { run: true });
  }
}

function renderTable(bindings, vars) {
  const thead = document.querySelector("#table thead");
  const tbody = document.querySelector("#table tbody");
  thead.innerHTML = "";
  tbody.innerHTML = "";
  const hr = document.createElement("tr");
  for (const v of vars) {
    const th = document.createElement("th");
    th.textContent = v;
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  for (const row of bindings) {
    const tr = document.createElement("tr");
    if (row.point && row.point.value) {
      tr.classList.add("clickable");
      tr.dataset.point = row.point.value.split("#").pop();
    }
    for (const v of vars) {
      const td = document.createElement("td");
      td.textContent = row[v] ? row[v].value : "";
      tr.appendChild(td);
    }
    tr.addEventListener("click", () => {
      if (tr.dataset.point) plotPoint(tr.dataset.point);
    });
    tbody.appendChild(tr);
  }
}

function showApiJson(payload) {
  document.getElementById("api-json").textContent = JSON.stringify(payload, null, 2);
}

async function runQuery() {
  const q = document.getElementById("query").value;
  document.getElementById("error").hidden = true;
  document.getElementById("meta").textContent = "Running…";
  const res = await fetch("/api/sparql", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: q }),
  });
  const payload = await res.json();
  showApiJson(payload);
  if (!res.ok) {
    document.getElementById("error").hidden = false;
    document.getElementById("error").textContent = payload.detail || JSON.stringify(payload);
    document.getElementById("meta").textContent = "";
    document.getElementById("dl-csv").disabled = true;
    document.getElementById("dl-json").disabled = true;
    return;
  }
  lastJson = payload;
  const body = payload.results;
  const meta = payload.meta;
  document.getElementById("meta").textContent = `${meta.row_count} rows · ${meta.elapsed_ms} ms${
    meta.truncated ? " · truncated" : ""
  }`;
  document.getElementById("dl-csv").disabled = false;
  document.getElementById("dl-json").disabled = false;
  if (body.boolean !== undefined) {
    renderTable([], []);
    document.getElementById("meta").textContent += ` · ASK=${body.boolean}`;
    return;
  }
  renderTable(body.results.bindings || [], body.head.vars || []);
}

async function plotPoint(pointId) {
  const res = await fetch(`/api/points/${pointId}/timeseries?limit=500`);
  if (!res.ok) return;
  const data = await res.json();
  const samples = data.samples || [];
  if (!samples.length) return;
  const w = 480;
  const h = 160;
  const xs = samples.map((s) => s.ts);
  const ys = samples.map((s) => s.value);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const pad = 8;
  const scaleX = (x) => pad + ((x - minX) / (maxX - minX || 1)) * (w - 2 * pad);
  const scaleY = (y) => h - pad - ((y - minY) / (maxY - minY || 1)) * (h - 2 * pad);
  const pts = samples.map((s) => `${scaleX(s.ts)},${scaleY(s.value)}`).join(" ");
  document.getElementById("plot").innerHTML =
    `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${pts}"/></svg>` +
    `<p>${pointId} · ${samples.length} samples</p>`;
}

function download(name, text, type) {
  const blob = new Blob([text], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

document.getElementById("theme-toggle").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  applyTheme(cur === "dark" ? "light" : "dark");
});

document.getElementById("view-ttl").addEventListener("click", () => {
  window.open("/api/model/ttl", "_blank", "noopener,noreferrer");
});

document.getElementById("validate-model").addEventListener("click", async () => {
  const meta = document.getElementById("validate-meta");
  meta.textContent = "Validating…";
  const res = await fetch("/api/model/validate?shacl=false");
  const data = await res.json();
  showApiJson(data);
  const bad = (data.checks || []).filter(
    (c) => c.count > 0 && String(c.check).startsWith("missing")
  );
  meta.textContent = bad.length
    ? `Issues: ${bad.map((c) => `${c.check}=${c.count}`).join(", ")}`
    : `OK · ${(data.checks || []).length} checks clean`;
});

document.getElementById("run").addEventListener("click", runQuery);
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    runQuery();
  }
});
document.getElementById("dl-json").addEventListener("click", () => {
  if (lastJson) download("sparql.json", JSON.stringify(lastJson, null, 2), "application/json");
});
document.getElementById("dl-csv").addEventListener("click", () => {
  if (!lastJson?.results?.results?.bindings) return;
  const vars = lastJson.results.head.vars;
  const rows = lastJson.results.results.bindings.map((b) =>
    vars.map((v) => (b[v] ? b[v].value : "")).join(",")
  );
  download("sparql.csv", [vars.join(","), ...rows].join("\n"), "text/csv");
});

applyTheme(document.documentElement.getAttribute("data-theme") || "dark");
loadPresets();
