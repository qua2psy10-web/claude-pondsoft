let PRESETS = {};

const $ = (id) => document.getElementById(id);

async function init() {
  PRESETS = await (await fetch("/api/presets")).json();
  const prefSel = $("prefecture");
  prefSel.innerHTML = Object.values(PRESETS)
    .map((p) => `<option value="${p.id}">${p.name}</option>`).join("");
  prefSel.addEventListener("change", onPrefChange);
  $("district").addEventListener("change", onDistrictChange);
  $("return_period").addEventListener("change", updateFormulaPreview);
  $("spillway_return_period").addEventListener("change", updateFormulaPreview);
  $("tc_method").addEventListener("change", onTcMethodChange);
  $("impervious_pct").addEventListener("input", onImperviousChange);
  onPrefChange();
  addHavRow(10.0, 3000); addHavRow(11.0, 3300); addHavRow(12.0, 3600);
  addHavRow(13.0, 3900); addHavRow(14.0, 4200);
  addOrificeRow();
}

function currentPreset() { return PRESETS[$("prefecture").value]; }
function currentDistrict() {
  const p = currentPreset();
  return p.districts.find((d) => d.id === $("district").value) || p.districts[0];
}

function onPrefChange() {
  const p = currentPreset();
  $("district").innerHTML = p.districts
    .map((d) => `<option value="${d.id}">${d.name}</option>`).join("");
  $("waveform").value = p.default_waveform || "central";
  $("preset-note").textContent =
    `適用基準: ${p.standard}／${p.runoff_coefficient_note || ""}` +
    (p.allowable_discharge_note ? `／${p.allowable_discharge_note}` : "");
  onDistrictChange();
}

function onDistrictChange() {
  const p = currentPreset();
  const d = currentDistrict();
  const rps = Object.keys(d.formulas).sort((a, b) => Number(a) - Number(b));
  const opts = rps.map((rp) => `<option value="${rp}">1/${rp}</option>`).join("");
  $("return_period").innerHTML = opts;
  $("spillway_return_period").innerHTML = opts;
  $("return_period").value = String(p.default_return_period);
  const sp = String(p.default_spillway_return_period);
  $("spillway_return_period").value = rps.includes(sp) ? sp : rps[rps.length - 1];
  updateFormulaPreview();
}

function fmtFormula(fx) {
  const b = fx.b >= 0 ? `＋${fx.b}` : `－${Math.abs(fx.b)}`;
  return `r = ${fx.a} / (t^(${fx.n}) ${b})`;
}

function updateFormulaPreview() {
  const d = currentDistrict();
  const rp = $("return_period").value;
  const srp = $("spillway_return_period").value;
  const parts = [];
  if (d.formulas[rp]) parts.push(`容量算定 1/${rp}: ${fmtFormula(d.formulas[rp])}`);
  if (d.formulas[srp]) parts.push(`洪水吐き 1/${srp}: ${fmtFormula(d.formulas[srp])}`);
  if (d.unit_discharge_m3s_per_ha)
    parts.push(`放流比流量既定値 ${d.unit_discharge_m3s_per_ha} m³/s/ha`);
  $("formula-preview").textContent = parts.join("　／　");
}

function onTcMethodChange() {
  const m = $("tc_method").value;
  $("tc-fixed-wrap").classList.toggle("hidden", m !== "fixed");
  $("tc-l-wrap").classList.toggle("hidden", m !== "doken");
  $("tc-h-wrap").classList.toggle("hidden", m !== "doken");
}

function onImperviousChange() {
  const p = currentPreset();
  const pct = parseFloat($("impervious_pct").value);
  if (isNaN(pct)) return;
  const imp = p.runoff_impervious ?? 1.0;
  const per = p.runoff_pervious ?? 0.6;
  const fmax = p.runoff_max ?? 1.0;
  let f = (pct / 100) * imp + (1 - pct / 100) * per;
  f = Math.min(f, fmax);
  $("runoff_f").value = f.toFixed(3);
}

function addHavRow(h = "", a = "") {
  const tb = $("hav-table").querySelector("tbody");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="number" step="0.001" class="hav-h" value="${h}"></td>
    <td><input type="number" step="1" class="hav-a" value="${a}"></td>
    <td><button type="button" class="rm" onclick="this.closest('tr').remove()">✕</button></td>`;
  tb.appendChild(tr);
}

function addOrificeRow() {
  const tb = $("orifice-table").querySelector("tbody");
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><select class="o-shape"><option value="rect">矩形</option><option value="circle">円形</option></select></td>
    <td><input type="number" step="0.001" class="o-invert" value="10.0"></td>
    <td><input type="number" step="0.001" class="o-b" value="0.24"></td>
    <td><input type="number" step="0.001" class="o-d" value="0.24"></td>
    <td><input type="number" step="0.001" class="o-dia" value="0"></td>
    <td><input type="number" step="0.01" class="o-c" value="0.60"></td>
    <td><button type="button" class="rm" onclick="this.closest('tr').remove()">✕</button></td>`;
  tb.appendChild(tr);
}

function collectPayload() {
  const havRows = [...$("hav-table").querySelectorAll("tbody tr")];
  const levels = [], areas = [];
  for (const tr of havRows) {
    const h = parseFloat(tr.querySelector(".hav-h").value);
    const a = parseFloat(tr.querySelector(".hav-a").value);
    if (!isNaN(h) && !isNaN(a)) { levels.push(h); areas.push(a); }
  }
  const orifices = [...$("orifice-table").querySelectorAll("tbody tr")].map((tr) => ({
    shape: tr.querySelector(".o-shape").value,
    invert_m: parseFloat(tr.querySelector(".o-invert").value) || 0,
    width_m: parseFloat(tr.querySelector(".o-b").value) || 0,
    height_m: parseFloat(tr.querySelector(".o-d").value) || 0,
    diameter_m: parseFloat(tr.querySelector(".o-dia").value) || 0,
    c: parseFloat(tr.querySelector(".o-c").value) || 0.6,
  }));
  return {
    project_name: $("project_name").value,
    prefecture_id: $("prefecture").value,
    district_id: $("district").value,
    return_period: $("return_period").value,
    spillway_return_period: $("spillway_return_period").value,
    waveform: $("waveform").value,
    duration_min: parseInt($("duration_min").value) || 1440,
    dt_min: parseInt($("dt_min").value) || 10,
    basin_name: $("basin_name").value,
    area_ha: parseFloat($("area_ha").value),
    runoff_f: parseFloat($("runoff_f").value),
    tc_method: $("tc_method").value,
    tc_min: parseFloat($("tc_min").value) || 10,
    tc_length_m: parseFloat($("tc_length_m").value) || 0,
    tc_height_m: parseFloat($("tc_height_m").value) || 0,
    pond_name: $("pond_name").value,
    allowable_q_m3s: parseFloat($("allowable_q").value) || 0,
    unit_q_m3s_per_ha: parseFloat($("unit_q").value) || 0,
    hav_levels_m: levels,
    hav_areas_m2: areas,
    hav_method: $("hav_method").value,
    orifices,
    sediment_years: parseFloat($("sediment_years").value) || 0,
    sediment_unit_m3_per_ha_year: parseFloat($("sediment_unit").value) || 0,
    spillway_enabled: $("spillway_enabled").value === "true",
    spillway_design_width_m: parseFloat($("spillway_design_width").value) || 0,
    spillway_weir_coef: parseFloat($("spillway_weir_coef").value) || 1.8,
    spillway_crest_level_m: parseFloat($("spillway_crest").value) || 0,
    spillway_bank_level_m: parseFloat($("spillway_bank").value) || 0,
    spillway_required_freeboard_m: parseFloat($("required_freeboard").value) || 0,
    pond_type: $("pond_type").value,
  };
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (_) { /* noop */ }
    throw new Error(msg);
  }
  return res;
}

function fmt(v, nd = 3) {
  return v == null ? "－" : Number(v).toLocaleString("ja-JP",
    { minimumFractionDigits: nd, maximumFractionDigits: nd });
}

async function calculate() {
  $("status").textContent = "計算中…";
  try {
    const res = await postJson("/api/calculate", collectPayload());
    const r = await res.json();
    renderResult(r);
    $("pdf-btn").disabled = false;
    $("status").textContent = "";
  } catch (e) {
    $("status").textContent = `エラー: ${e.message}`;
    $("result").classList.add("hidden");
    $("pdf-btn").disabled = true;
  }
}

function judge(ok) {
  return ok ? '<span class="ok">ＯＫ</span>' : '<span class="ng">ＮＧ</span>';
}

function renderResult(r) {
  const rows = [
    ["降雨強度式（容量算定）", r.formula],
    ["降雨強度式（洪水吐き）", r.spill_formula],
    ["洪水到達時間", `${fmt(r.tc_min, 1)} 分（${r.tc_method}）`],
    ["総雨量", `${fmt(r.total_rain_mm, 1)} mm`],
    ["合理式ピーク流量", `${fmt(r.rational_peak_m3s)} m³/s`],
    ["最大流入量", `${fmt(r.inflow_peak_m3s)} m³/s`],
    ["許容放流量", `${fmt(r.allowable_q_m3s)} m³/s${r.allowable_q_auto ? "（比流量から自動設定）" : ""}`],
    ["最大放流量", `${fmt(r.max_outflow_m3s)} m³/s ${judge(r.outflow_ok)}`],
    ["必要洪水調節容量（簡便法）", `${fmt(r.required_volume_simplified_m3, 1)} m³（継続時間 ${r.critical_duration_min} 分）`],
    ["必要洪水調節容量（厳密法）", `${fmt(r.required_volume_strict_m3, 1)} m³`],
    ["計画高水位 H.W.L", `${fmt(r.hwl_m)} m`],
    ["設計堆積土砂量", `${fmt(r.sediment_m3, 1)} m³`],
    ["必要総容量", `${fmt(r.total_required_m3, 1)} m³`],
    ["調整池容量", `${fmt(r.pond_capacity_m3, 1)} m³ ${judge(r.capacity_ok)}`],
  ];
  if (r.spillway) {
    rows.push(["洪水吐き 設計洪水流量", `${fmt(r.spillway.Qd_m3s)} m³/s`]);
    rows.push(["洪水吐き 越流水深 H0", `${fmt(r.spillway.H0_m)} m`]);
    rows.push(["設計洪水水位 H.H.W.L", `${fmt(r.spillway.HHWL_m)} m`]);
    rows.push(["余裕高", `${fmt(r.spillway.freeboard_m)} m ${judge(r.spillway.freeboard_ok)}`]);
  }
  $("result-body").innerHTML =
    "<table>" + rows.map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join("") + "</table>";
  $("result").classList.remove("hidden");
  $("result").scrollIntoView({ behavior: "smooth" });
}

async function downloadPdf() {
  $("status").textContent = "PDF生成中…";
  try {
    const res = await postJson("/api/report", collectPayload());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${$("pond_name").value || "調整池"}_容量計算書.pdf`;
    a.click();
    URL.revokeObjectURL(url);
    $("status").textContent = "";
  } catch (e) {
    $("status").textContent = `エラー: ${e.message}`;
  }
}

init();
