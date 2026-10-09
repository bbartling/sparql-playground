let lastJson = null;
let currentEquipment = "";

async function loadPresets() {
  const res = await fetch("/api/sparql/examples");
  const data = await res.json();
  const sel = document.getElementById("preset");
  sel.innerHTML = "";
  for (const ex of data.examples) {
    const opt = document.createElement("option");
    opt.value = ex.query;
    opt.textContent = ex.title;
    sel.appendChild(opt);
  }
  if (data.examples.length) {
    document.getElementById("query").value = data.examples[0].query;
  }
  sel.addEventListener("change", () => {
    document.getElementById("query").value = sel.value;
  });
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
  sel.innerHTML = "";
  if (!currentEquipment) return;
  const res = await fetch(
    `/api/equipment/${encodeURIComponent(currentEquipment)}/faults?include_generic=true`
  );
  if (!res.ok) return;
  const faults = await res.json();
  const applicable = faults.filter((f) => f.applicable && !f.generic);
  const rest = faults.filter((f) => !f.applicable || f.generic);
  for (const f of [...applicable, ...rest]) {
    const opt = document.createElement("option");
    opt.value = f.rule_id;
    opt.textContent = `${f.rule_id} — ${f.title}${f.applicable ? "" : " (missing roles)"}`;
    opt.disabled = !f.applicable;
    sel.appendChild(opt);
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
  if (!res.ok) {
    document.getElementById("error").hidden = false;
    document.getElementById("error").textContent = payload.detail || JSON.stringify(payload);
    document.getElementById("meta").textContent = "";
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
  document.getElementById("plot").innerHTML = `<svg width="${w}" height="${h}"><polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${pts}"/></svg><p>${pointId} (${samples.length} samples)</p>`;
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
  const bad = (data.checks || []).filter((c) => c.count > 0 && String(c.check).startsWith("missing"));
  meta.textContent = bad.length
    ? `Issues: ${bad.map((c) => `${c.check}=${c.count}`).join(", ")}`
    : `OK · ${data.checks.length} checks clean`;
});

document.getElementById("load-lesson").addEventListener("click", async () => {
  const rule = document.getElementById("fault-rule").value;
  const box = document.getElementById("lesson");
  if (!currentEquipment || !rule) return;
  const res = await fetch(
    `/api/equipment/${encodeURIComponent(currentEquipment)}/faults/${encodeURIComponent(rule)}/lesson`
  );
  const data = await res.json();
  if (!res.ok) {
    box.hidden = false;
    box.textContent = data.detail || JSON.stringify(data);
    return;
  }
  const first = (data.lessons || []).find((l) => l.query);
  if (first?.query) {
    document.getElementById("query").value = first.query;
  }
  box.hidden = false;
  box.textContent = [
    `${data.rule_id}: ${data.title}`,
    data.summary || "",
    data.equation || "",
    "",
    "Required roles → Brick SPARQL lessons:",
    ...(data.lessons || []).map((l) =>
      l.error ? `  ${l.role}: ERROR ${l.error}` : `  ${l.role} → ${l.binding.point_id} (${l.binding.brick_class})`
    ),
    "",
    "Tip: Run the loaded SPARQL, then click Run rule.",
  ].join("\n");
});

document.getElementById("run-rule").addEventListener("click", async () => {
  const rule = document.getElementById("fault-rule").value;
  const meta = document.getElementById("rule-meta");
  const out = document.getElementById("rule-result");
  meta.textContent = "Running rule…";
  out.hidden = true;
  const res = await fetch(
    `/api/equipment/${encodeURIComponent(currentEquipment)}/faults/${encodeURIComponent(rule)}/run`,
    { method: "POST" }
  );
  const data = await res.json();
  if (!res.ok) {
    meta.textContent = "";
    document.getElementById("error").hidden = false;
    document.getElementById("error").textContent = data.detail || JSON.stringify(data);
    return;
  }
  meta.textContent = `${data.status} · fault_hours=${data.fault_hours} · samples=${data.sample_count}`;
  out.hidden = false;
  out.textContent = JSON.stringify(data, null, 2);
});

document.getElementById("run").addEventListener("click", runQuery);
document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key === "Enter") runQuery();
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
