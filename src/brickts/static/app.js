let lastJson = null;

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

loadPresets();
