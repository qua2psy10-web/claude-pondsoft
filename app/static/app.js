let PRESETS = {};

const INFIL_CATALOG = [
  { id: "trench", name: "浸透トレンチ", unit: "m" },
  { id: "masu", name: "浸透ます", unit: "個" },
  { id: "pavement", name: "透水性舗装", unit: "m²" },
  { id: "gutter", name: "浸透側溝", unit: "m" },
  { id: "tank", name: "大型貯留浸透槽", unit: "個" },
  { id: "other", name: "その他", unit: "－" },
];

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
  addInfilRow();
}

function addInfilRow(f) {
  const tb = $("infil-table").querySelector("tbody");
  const tr = document.createElement("tr");
  const opts = INFIL_CATALOG
    .map((c) => `<option value="${c.id}">${c.name}（${c.unit}）</option>`).join("");
  tr.innerHTML = `
    <td><select class="if-type">${opts}</select></td>
    <td><input type="number" step="0.01" class="if-qty" value="0"></td>
    <td><input type="number" step="0.0001" class="if-unit" value="0"></td>
    <td><button type="button" class="rm" onclick="this.closest('tr').remove()">✕</button></td>`;
  tb.appendChild(tr);
  if (f && typeof f === "object") {
    if (f.type_id) tr.querySelector(".if-type").value = f.type_id;
    if (f.quantity != null) tr.querySelector(".if-qty").value = f.quantity;
    if (f.unit_infiltration_m3h != null) tr.querySelector(".if-unit").value = f.unit_infiltration_m3h;
  }
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

function addOrificeRow(o) {
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
  if (o && typeof o === "object" && !(o instanceof Event)) {
    if (o.shape) tr.querySelector(".o-shape").value = o.shape;
    if (o.invert_m != null) tr.querySelector(".o-invert").value = o.invert_m;
    if (o.width_m != null) tr.querySelector(".o-b").value = o.width_m;
    if (o.height_m != null) tr.querySelector(".o-d").value = o.height_m;
    if (o.diameter_m != null) tr.querySelector(".o-dia").value = o.diameter_m;
    if (o.c != null) tr.querySelector(".o-c").value = o.c;
  }
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
  const infilFacilities = [...$("infil-table").querySelectorAll("tbody tr")]
    .map((tr) => {
      const typeId = tr.querySelector(".if-type").value;
      const cat = INFIL_CATALOG.find((c) => c.id === typeId);
      return {
        type_id: typeId,
        name: cat ? cat.name : "",
        quantity: parseFloat(tr.querySelector(".if-qty").value) || 0,
        unit_infiltration_m3h: parseFloat(tr.querySelector(".if-unit").value) || 0,
      };
    })
    .filter((f) => f.quantity > 0 && f.unit_infiltration_m3h > 0);
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
    infiltration_enabled: $("infiltration_enabled").value === "true",
    infiltration_facilities: infilFacilities,
    infiltration_treatment_area_ha: parseFloat($("infiltration_treatment_area").value) || 0,
    infiltration_direct_R_m3h: parseFloat($("infiltration_direct_R").value) || 0,
    infiltration_direct_fc_mmhr: parseFloat($("infiltration_direct_fc").value) || 0,
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

// ---- プロジェクト設定の保存/読込（フロント完結・外部依存なし） -------------

function savePayload() {
  const data = collectPayload();
  const blob = new Blob([JSON.stringify(data, null, 2)],
    { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${$("pond_name").value || "調整池"}_入力.json`;
  a.click();
  URL.revokeObjectURL(url);
  $("status").textContent = "設定を保存しました";
}

function loadPayload(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      applyPayload(JSON.parse(reader.result));
      $("status").textContent = "設定を読み込みました";
      $("result").classList.add("hidden");
      $("pdf-btn").disabled = true;
    } catch (e) {
      $("status").innerHTML = `<span class="ng">読込エラー: ${e.message}</span>`;
    }
  };
  reader.readAsText(file);
}

function applyPayload(d) {
  const setV = (id, v) => {
    const e = $(id);
    if (e && v !== undefined && v !== null) e.value = v;
  };
  // プリセット依存の順序: 県→地区→確率年
  if (d.prefecture_id) { $("prefecture").value = d.prefecture_id; onPrefChange(); }
  if (d.district_id) { $("district").value = d.district_id; onDistrictChange(); }
  setV("return_period", d.return_period);
  setV("spillway_return_period", d.spillway_return_period);
  setV("waveform", d.waveform);
  // スカラー項目（id → payloadキー）
  const map = {
    project_name: "project_name", duration_min: "duration_min", dt_min: "dt_min",
    basin_name: "basin_name", area_ha: "area_ha", runoff_f: "runoff_f",
    tc_method: "tc_method", tc_min: "tc_min",
    tc_length_m: "tc_length_m", tc_height_m: "tc_height_m",
    pond_name: "pond_name", hav_method: "hav_method",
    allowable_q: "allowable_q_m3s", unit_q: "unit_q_m3s_per_ha",
    infiltration_enabled: "infiltration_enabled",
    infiltration_treatment_area: "infiltration_treatment_area_ha",
    infiltration_direct_R: "infiltration_direct_R_m3h",
    infiltration_direct_fc: "infiltration_direct_fc_mmhr",
    sediment_years: "sediment_years", sediment_unit: "sediment_unit_m3_per_ha_year",
    spillway_enabled: "spillway_enabled",
    spillway_design_width: "spillway_design_width_m",
    spillway_weir_coef: "spillway_weir_coef",
    spillway_crest: "spillway_crest_level_m", spillway_bank: "spillway_bank_level_m",
    required_freeboard: "spillway_required_freeboard_m", pond_type: "pond_type",
  };
  for (const [id, key] of Object.entries(map)) {
    let v = d[key];
    if (typeof v === "boolean") v = String(v);  // 真偽値の select
    setV(id, v);
  }
  // テーブル系: 一旦クリアして配列ぶん再構築
  $("hav-table").querySelector("tbody").innerHTML = "";
  const levels = d.hav_levels_m || [], areas = d.hav_areas_m2 || [];
  for (let i = 0; i < levels.length; i++) addHavRow(levels[i], areas[i]);
  $("orifice-table").querySelector("tbody").innerHTML = "";
  (d.orifices || []).forEach((o) => addOrificeRow(o));
  $("infil-table").querySelector("tbody").innerHTML = "";
  (d.infiltration_facilities || []).forEach((f) => addInfilRow(f));

  onTcMethodChange();
  updateFormulaPreview();
}

// ---- 送信前の軽量チェック（最終防衛はサーバ側 _validate） -------------------

function clientValidate(p) {
  const L = p.hav_levels_m, A = p.hav_areas_m2;
  if (!L || L.length < 2) return "水位-面積表は2点以上（池底と天端）を入力してください";
  for (let i = 0; i < L.length - 1; i++)
    if (L[i] >= L[i + 1]) return `水位-面積表: 水位は下から昇順で入力してください（${i + 1}行目）`;
  for (let i = 0; i < A.length; i++)
    if (!(A[i] > 0)) return `水位-面積表: 面積は正の値で入力してください（${i + 1}行目）`;
  if (!p.orifices || !p.orifices.length) return "放流施設（オリフィス）を1つ以上入力してください";
  const bottom = L[0], top = L[L.length - 1];
  for (let k = 0; k < p.orifices.length; k++) {
    const o = p.orifices[k];
    if (o.invert_m < bottom - 1e-9 || o.invert_m > top + 1e-9)
      return `オリフィス${k + 1}: 敷高が池底 ${bottom}m〜天端 ${top}m の範囲外です`;
  }
  return null;
}

// ---- 結果グラフ（ネイティブCanvas・外部ライブラリなし） ----------------------

function drawSeriesChart(s) {
  const cv = $("series-chart");
  if (!cv || !s || !s.times_min || !s.times_min.length) return;
  const ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  const mL = 56, mR = 56, mT = 26, mB = 42;
  const x0 = mL, x1 = W - mR, y0 = H - mB, y1 = mT;
  const t = s.times_min;
  const tmin = Math.min(...t), tmax = Math.max(...t);
  const flowMax = Math.max(...s.inflow, ...s.outflow, 1e-6) * 1.1;
  const lvMin = Math.min(...s.levels), lvMax = Math.max(...s.levels);
  const lvPad = (lvMax - lvMin) * 0.1 || 0.5;
  const lMin = lvMin - lvPad, lMax = lvMax + lvPad;
  const sx = (v) => x0 + (v - tmin) / (tmax - tmin || 1) * (x1 - x0);
  const syF = (v) => y0 - v / flowMax * (y0 - y1);
  const syL = (v) => y0 - (v - lMin) / ((lMax - lMin) || 1) * (y0 - y1);

  ctx.strokeStyle = "#999"; ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(x0, y1); ctx.lineTo(x0, y0); ctx.lineTo(x1, y0); ctx.lineTo(x1, y1);
  ctx.stroke();
  ctx.font = "11px sans-serif"; ctx.textBaseline = "middle";
  for (let i = 0; i <= 4; i++) {
    const v = flowMax * i / 4, y = syF(v);
    ctx.strokeStyle = "#eee"; ctx.beginPath();
    ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    ctx.fillStyle = "#2244aa"; ctx.textAlign = "right";
    ctx.fillText(v.toFixed(2), x0 - 6, y);
    const lv = lMin + (lMax - lMin) * i / 4;
    ctx.fillStyle = "#aa5522"; ctx.textAlign = "left";
    ctx.fillText(lv.toFixed(2), x1 + 6, syL(lv));
  }
  ctx.fillStyle = "#333"; ctx.textAlign = "center"; ctx.textBaseline = "top";
  for (let i = 0; i <= 6; i++) {
    const tv = tmin + (tmax - tmin) * i / 6;
    ctx.fillText((tv / 60).toFixed(1), sx(tv), y0 + 6);
  }
  const line = (arr, sy, color) => {
    ctx.strokeStyle = color; ctx.lineWidth = 1.6; ctx.beginPath();
    arr.forEach((v, i) => {
      const X = sx(t[i]), Y = sy(v);
      i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
    });
    ctx.stroke();
  };
  line(s.inflow, syF, "#2244aa");
  line(s.outflow, syF, "#22aa66");
  line(s.levels, syL, "#aa5522");
  ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
  ctx.fillStyle = "#2244aa"; ctx.fillText("― 流入量 (m³/s)", x0 + 4, y1 - 10);
  ctx.fillStyle = "#22aa66"; ctx.fillText("― 放流量 (m³/s)", x0 + 130, y1 - 10);
  ctx.fillStyle = "#aa5522"; ctx.fillText("― 水位 (m)", x0 + 256, y1 - 10);
  ctx.fillStyle = "#333"; ctx.textAlign = "center";
  ctx.fillText("時間 (hr)", (x0 + x1) / 2, y0 + 32);
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
  const payload = collectPayload();
  const err = clientValidate(payload);
  if (err) {
    $("status").innerHTML = `<span class="ng">エラー: ${err}</span>`;
    $("result").classList.add("hidden");
    $("pdf-btn").disabled = true;
    return;
  }
  $("status").textContent = "計算中…";
  try {
    const res = await postJson("/api/calculate", payload);
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
    ...(r.infiltration ? [
      ["設計浸透量 R", `${r.infiltration.R_m3h == null ? "－" : fmt(r.infiltration.R_m3h, 3) + " m³/h"}`],
      ["設計浸透強度 Fc", `${fmt(r.infiltration.fc_mmhr, 4)} mm/h`],
      ["浸透処理面積率 α", `${fmt(r.infiltration.treatment_ratio * 100, 1)} %`],
    ] : []),
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
  drawSeriesChart(r.series);
  $("result").scrollIntoView({ behavior: "smooth" });
}

async function downloadPdf() {
  const payload = collectPayload();
  const err = clientValidate(payload);
  if (err) {
    $("status").innerHTML = `<span class="ng">エラー: ${err}</span>`;
    return;
  }
  $("status").textContent = "PDF生成中…";
  try {
    const res = await postJson("/api/report", payload);
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
