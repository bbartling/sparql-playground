let lastJson = null;
let examplesById = {};
let lastRunner = null;

const GROUPS = [
  {
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
    title: "Points",
    buttons: [
      { label: "All points", example: "list_points", run: true },
      { label: "AHU points + refs", example: "points_of_ahus", run: true },
      { label: "VAV-zone points", example: "points_of_vav_zones", run: true },
      { label: "Points on other kinds", example: "points_by_equip_kind", run: true },
      { label: "Missing refs", example: "missing_refs", run: true },
    ],
  },
  {
    title: "Open-FDD SPARQL lessons → local Python",
    hint: "Loads role SPARQL for the rule. Fault math runs locally via analyst_client.py.",
    buttons: [
      { label: "FC1 · AHU_1", lesson: { equipment: "AHU_1", rule: "FC1" } },
      { label: "FC1 · AHU_2", lesson: { equipment: "AHU_2", rule: "FC1" } },
      { label: "FC2 · AHU_1", lesson: { equipment: "AHU_1", rule: "FC2" } },
      { label: "FC2 · AHU_2", lesson: { equipment: "AHU_2", rule: "FC2" } },
      { label: "FC3 · AHU_1", lesson: { equipment: "AHU_1", rule: "FC3" } },
      { label: "FC4 · AHU_1", lesson: { equipment: "AHU_1", rule: "FC4" } },
    ],
  },
];

function setQuery(text) {
  document.getElementById("query").value = text || "";
}

function showLessonText(lines) {
  const box = document.getElementById("lesson");
  box.hidden = false;
  box.textContent = lines.join("\n");
}

function baseUrl() {
  return window.location.origin;
}

function buildPythonArtifacts(equipment, rule, lessons) {
  const url = baseUrl();
  const cmd =
    `uv run python scripts/analyst_client.py \\\n` +
    `  --base-url ${url} \\\n` +
    `  --equipment ${equipment} \\\n` +
    `  --rule ${rule}`;
  const roleLines = (lessons || [])
    .filter((l) => l.binding)
    .map(
      (l) =>
        `    # ${l.role} → ${l.binding.point_id} (${l.binding.brick_class})\n` +
        `    # SPARQL lesson available via GET /api/equipment/${equipment}/faults/${rule}/lesson`
    )
    .join("\n");
  const script = `#!/usr/bin/env python3
"""Generated from brickts UI — resolve Brick roles via API, run Open-FDD locally."""
from __future__ import annotations

import httpx
import pandas as pd
from open_fdd.rules import run_rule

BASE = ${JSON.stringify(url)}
EQUIPMENT = ${JSON.stringify(equipment)}
RULE = ${JSON.stringify(rule)}

${roleLines}

def main() -> None:
    with httpx.Client(base_url=BASE, timeout=300.0) as client:
        lesson = client.get(f"/api/equipment/{EQUIPMENT}/faults/{RULE}/lesson")
        lesson.raise_for_status()
        data = lesson.json()
        series = {}
        for item in data.get("lessons", []):
            binding = item.get("binding")
            if not binding:
                raise SystemExit(item.get("error") or f"missing role {item.get('role')}")
            pid = binding["point_id"]
            ts = client.get(f"/api/points/{pid}/timeseries")
            ts.raise_for_status()
            samples = ts.json()["samples"]
            idx = pd.to_datetime([s["ts"] for s in samples], unit="s", utc=True)
            series[item["role"]] = pd.Series(
                [s["value"] for s in samples], index=idx, name=item["role"]
            )
        df = pd.DataFrame(series).sort_index()
        df.attrs.update(equipment_id=EQUIPMENT, equipment_type="ahu")
        res = run_rule(RULE, df, poll_seconds=300)
        print(res.status, res.fault_hours, res.fault_pct, res.sample_count, res.fault_sample_count)

if __name__ == "__main__":
    main()
`;
  return { cmd, script };
}

function setRunner(equipment, rule, lessons) {
  lastRunner = buildPythonArtifacts(equipment, rule, lessons);
  document.getElementById("python-cmd").textContent = lastRunner.cmd;
  document.getElementById("python-script").textContent = lastRunner.script;
  document.getElementById("python-script").hidden = false;
  document.getElementById("copy-cmd").disabled = false;
  document.getElementById("copy-script").disabled = false;
}

async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

function loadExample(id, { run = false } = {}) {
  const ex = examplesById[id];
  if (!ex) return;
  setQuery(ex.query);
  if (run) runQuery();
}

async function loadFaultLesson(equipment, rule) {
  const roleBox = document.getElementById("role-buttons");
  roleBox.innerHTML = "";
  roleBox.hidden = true;
  const res = await fetch(
    `/api/equipment/${encodeURIComponent(equipment)}/faults/${encodeURIComponent(rule)}/lesson`
  );
  const data = await res.json();
  if (!res.ok) {
    showLessonText([data.detail || JSON.stringify(data)]);
    return;
  }
  const lessons = data.lessons || [];
  const ok = lessons.filter((l) => l.query);
  showLessonText([
    `${data.rule_id}: ${data.title}`,
    data.summary || "",
    data.equation ? `Equation: ${data.equation}` : "",
    "",
    "Role buttons below swap the SPARQL editor. Fault evaluation is local Python only.",
    ...ok.map((l) => `  ${l.role} → ${l.binding.point_id} (${l.binding.brick_class})`),
    ...(lessons.filter((l) => l.error).map((l) => `  ${l.role}: ${l.error}`)),
  ]);
  setRunner(equipment, rule, ok);
  if (ok.length) {
    setQuery(ok[0].query);
    roleBox.hidden = false;
    for (const l of ok) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ghost";
      btn.textContent = l.role;
      btn.addEventListener("click", () => {
        setQuery(l.query);
        runQuery();
      });
      roleBox.appendChild(btn);
    }
    await runQuery();
  }
}

function renderButtonGroups() {
  const host = document.getElementById("button-groups");
  host.innerHTML = "";
  for (const group of GROUPS) {
    const section = document.createElement("div");
    section.className = "btn-group";
    const h = document.createElement("h3");
    h.textContent = group.title;
    section.appendChild(h);
    if (group.hint) {
      const p = document.createElement("p");
      p.className = "hint";
      p.textContent = group.hint;
      section.appendChild(p);
    }
    const row = document.createElement("div");
    row.className = "quick";
    for (const b of group.buttons) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "ghost";
      btn.textContent = b.label;
      btn.addEventListener("click", async () => {
        if (b.example) loadExample(b.example, { run: !!b.run });
        if (b.lesson) await loadFaultLesson(b.lesson.equipment, b.lesson.rule);
      });
      row.appendChild(btn);
    }
    section.appendChild(row);
    host.appendChild(section);
  }
}

async function loadPresets() {
  const res = await fetch("/api/sparql/examples");
  const data = await res.json();
  examplesById = {};
  for (const ex of data.examples) {
    examplesById[ex.id] = ex;
  }
  renderButtonGroups();
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
  document.getElementById("plot").innerHTML =
    `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><polyline fill="none" stroke="#38bdf8" stroke-width="2" points="${pts}"/></svg>` +
    `<p>${pointId} · ${samples.length} samples via GET /api/points/…/timeseries</p>`;
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

document.getElementById("copy-cmd").addEventListener("click", async () => {
  if (lastRunner) await copyText(lastRunner.cmd);
});
document.getElementById("copy-script").addEventListener("click", async () => {
  if (lastRunner) await copyText(lastRunner.script);
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

loadPresets();
