let lastJson = null;
let currentEquipment = "";
let currentLesson = null;

const QUICK = [
  { id: "list_ahus", label: "List AHUs" },
  { id: "list_points", label: "List points" },
  { id: "ahu_points_refs", label: "Points + refs" },
  { id: "databases", label: "Databases" },
  { id: "equipment_tree", label: "Equipment tree" },
  { id: "class_counts", label: "Class counts" },
  { id: "missing_refs", label: "Missing refs" },
  { id: "zones_fed", label: "Zones fed" },
];

function setQuery(text) {
  document.getElementById("query").value = text || "";
}

function showLessonText(lines) {
  const box = document.getElementById("lesson");
  box.hidden = false;
  box.textContent = lines.join("\n");
}

async function loadPresets() {
  const res = await fetch("/api/sparql/examples");
  const data = await res.json();
  const sel = document.getElementById("preset");
  sel.innerHTML = "";
  const byId = {};
  for (const ex of data.examples) {
    byId[ex.id] = ex;
    const opt = document.createElement("option");
    opt.value = ex.id;
    opt.dataset.query = ex.query;
    opt.textContent = ex.title;
    sel.appendChild(opt);
  }
  if (data.examples.length && !document.getElementById("query").value) {
    setQuery(data.examples[0].query);
  }
  sel.addEventListener("change", () => {
    const opt = sel.selectedOptions[0];
    if (opt) setQuery(opt.dataset.query);
  });

  const quick = document.getElementById("quick-buttons");
  quick.innerHTML = "";
  for (const q of QUICK) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ghost";
    btn.textContent = q.label;
    btn.addEventListener("click", () => {
      const ex = byId[q.id];
      if (!ex) return;
      sel.value = q.id;
      setQuery(ex.query);
    });
    quick.appendChild(btn);
  }
}

async function loadEquipment() {
  const res = await fetch("/api/equipment");
  const data = await res.json();
  const sel = document.getElementById("equipment");
  sel.innerHTML = "";
  for (const eq of data.equipment || []) {
    if (!/^AHU_/i.test(eq.equipment_id)) continue;
    const opt = document.createElement("option");
    opt.value = eq.equipment_id;
    opt.textContent = eq.label || eq.equipment_id;
    sel.appendChild(opt);
  }
  currentEquipment = sel.value;
  sel.addEventListener("change", async () => {
    currentEquipment = sel.value;
    await loadFaults();
  });
  await loadFaults();
}

async function loadFaults() {
  const sel = document.getElementById("fault-rule");
  const roleSel = document.getElementById("role-lesson");
  sel.innerHTML = "";
  roleSel.innerHTML = "";
  currentLesson = null;
  if (!currentEquipment) return;

  const res = await fetch(
    `/api/equipment/${encodeURIComponent(currentEquipment)}/faults?include_generic=false`
  );
  if (!res.ok) return;
  const faults = await res.json();
  const applicable = faults.filter((f) => f.applicable);
  for (const f of applicable) {
    const opt = document.createElement("option");
    opt.value = f.rule_id;
    opt.textContent = `${f.rule_id} — ${f.title}`;
    sel.appendChild(opt);
  }
  if (!applicable.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No role-based rules applicable";
    sel.appendChild(opt);
    return;
  }
  sel.onchange = () => loadFaultLesson(sel.value);
  await loadFaultLesson(sel.value);
}

async function loadFaultLesson(ruleId) {
  const roleSel = document.getElementById("role-lesson");
  roleSel.innerHTML = "";
  currentLesson = null;
  if (!currentEquipment || !ruleId) return;

  const res = await fetch(
    `/api/equipment/${encodeURIComponent(currentEquipment)}/faults/${encodeURIComponent(ruleId)}/lesson`
  );
  const data = await res.json();
  if (!res.ok) {
    showLessonText([data.detail || JSON.stringify(data)]);
    return;
  }
  currentLesson = data;
  const lessons = (data.lessons || []).filter((l) => l.query);
  for (const l of lessons) {
    const opt = document.createElement("option");
    opt.value = l.role;
    opt.textContent = `${l.role} → ${l.binding?.point_id || "?"}`;
    roleSel.appendChild(opt);
  }
  showLessonText([
    `${data.rule_id}: ${data.title}`,
    data.summary || "",
    data.equation ? `Equation: ${data.equation}` : "",
    "",
    "This menu only pre-fills SPARQL. Run Open-FDD locally with scripts/analyst_client.py.",
    "",
    "Roles:",
    ...lessons.map((l) => `  ${l.role} → ${l.binding.point_id} (${l.binding.brick_class})`),
  ].filter((x) => x !== undefined));

  if (lessons.length) {
    setQuery(lessons[0].query);
    roleSel.onchange = () => {
      const role = roleSel.value;
      const hit = lessons.find((l) => l.role === role);
      if (hit?.query) setQuery(hit.query);
    };
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
  const vars = body.head.vars || [];
  renderTable(body.results.bindings || [], vars);
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
  document.getElementById("plot").innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${pts}"/></svg><p>${pointId} · ${samples.length} samples via GET /api/points/…/timeseries</p>`;
}

function download(name, text, type) {
  const blob = new Blob([text], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

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

Promise.all([loadPresets(), loadEquipment()]);
