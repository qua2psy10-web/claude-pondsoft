"""PDF計算書の組版（ReportLab）。

章立てはFORUM8「調節池・調整池の計算」出力例に準拠:
  表紙 / 目次 / 1章 設計条件 / 2章 流域 / 3章 貯留施設 / 4章 洪水吐き / 5章 総括表
"""
import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)

FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"
FONT_GOTHIC = "IPAGothic"
FONT_PGOTHIC = "IPAPGothic"

_registered = False


def _register_fonts():
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont(FONT_GOTHIC, str(FONT_DIR / "ipag.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_PGOTHIC, str(FONT_DIR / "ipagp.ttf")))
    font_manager.fontManager.addfont(str(FONT_DIR / "ipagp.ttf"))
    plt.rcParams["font.family"] = "IPAPGothic"
    _registered = True


# --- スタイル -----------------------------------------------------------

def _styles():
    return {
        "cover_title": ParagraphStyle("cover_title", fontName=FONT_PGOTHIC,
                                      fontSize=22, leading=30, alignment=1),
        "cover_sub": ParagraphStyle("cover_sub", fontName=FONT_PGOTHIC,
                                    fontSize=13, leading=20, alignment=1),
        "h1": ParagraphStyle("h1", fontName=FONT_PGOTHIC, fontSize=13,
                             leading=18, spaceBefore=8, spaceAfter=6),
        "h2": ParagraphStyle("h2", fontName=FONT_PGOTHIC, fontSize=11,
                             leading=16, spaceBefore=6, spaceAfter=4),
        "body": ParagraphStyle("body", fontName=FONT_PGOTHIC, fontSize=9.5,
                               leading=14),
        "small": ParagraphStyle("small", fontName=FONT_PGOTHIC, fontSize=8.5,
                                leading=12),
        "toc": ParagraphStyle("toc", fontName=FONT_PGOTHIC, fontSize=10.5,
                              leading=18, leftIndent=8),
    }


def _tbl(data, col_widths=None, align_right_cols=(), header_rows=1,
         font_size=8.5):
    style = [
        ("FONT", (0, 0), (-1, -1), FONT_PGOTHIC, font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if header_rows:
        style += [
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), colors.Color(0.9, 0.9, 0.9)),
            ("ALIGN", (0, 0), (-1, header_rows - 1), "CENTER"),
        ]
    for c in align_right_cols:
        style.append(("ALIGN", (c, header_rows), (c, -1), "RIGHT"))
    t = Table(data, colWidths=col_widths, repeatRows=header_rows)
    t.setStyle(TableStyle(style))
    return t


def _fmt(v, nd=3):
    if v is None:
        return "－"
    return f"{v:,.{nd}f}"


# --- グラフ --------------------------------------------------------------

def _hydrograph_png(routing, title):
    fig, ax = plt.subplots(figsize=(6.6, 3.1), dpi=150)
    t_hr = [t / 60.0 for t in routing["times_min"]]
    ax.plot(t_hr, routing["inflow_m3s"], label="流入量 Qi", lw=1.2)
    ax.plot(t_hr, routing["outflow_m3s"], label="放流量 Qo", lw=1.2)
    ax.set_xlabel("時間 (hr)")
    ax.set_ylabel("流量 (m³/s)")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, lw=0.3, alpha=0.6)
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def _hyeto_png(hyeto, title):
    fig, ax = plt.subplots(figsize=(6.6, 2.6), dpi=150)
    t_hr = [t / 60.0 for t in hyeto["times"]]
    ax.bar(t_hr, hyeto["intensity_mmhr"], width=hyeto["dt_min"] / 60.0 * 0.9,
           color="#4477aa")
    ax.set_xlabel("時間 (hr)")
    ax.set_ylabel("降雨強度 (mm/hr)")
    ax.set_title(title, fontsize=10)
    ax.grid(True, lw=0.3, alpha=0.6, axis="y")
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


# --- 本体 ----------------------------------------------------------------

def build_pdf(result: dict) -> bytes:
    _register_fonts()
    st = _styles()
    inp = result["input"]
    preset = result["preset"]
    district = result["district"]
    formula = result["formula"]
    hyeto = result["hyetograph"]
    inflow = result["inflow"]
    routing = result["routing"]
    simp = result["simplified"]
    stage = result["stage"]
    spill = result["spillway"]
    tc = result["tc"]

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=18 * mm, bottomMargin=16 * mm,
                          title=inp.title)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height,
                  id="main")

    def on_page(canvas, doc_):
        canvas.saveState()
        canvas.setFont(FONT_PGOTHIC, 8)
        if doc_.page > 1:
            canvas.drawCentredString(A4[0] / 2, 10 * mm, f"- {doc_.page - 1} -")
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="page", frames=[frame],
                                       onPage=on_page)])
    el = []

    # ---- 表紙
    el.append(Spacer(1, 55 * mm))
    el.append(Paragraph(inp.title, st["cover_title"]))
    el.append(Spacer(1, 12 * mm))
    if inp.project_name:
        el.append(Paragraph(inp.project_name, st["cover_sub"]))
        el.append(Spacer(1, 8 * mm))
    el.append(Paragraph(f"{preset['name']}（{district['name']}地区）",
                        st["cover_sub"]))
    el.append(Spacer(1, 4 * mm))
    el.append(Paragraph(f"適用基準: {preset['standard']}", st["cover_sub"]))
    el.append(PageBreak())

    # ---- 目次
    el.append(Paragraph("目次", st["h1"]))
    for line in ["1章 設計条件", "2章 流域", "3章 貯留施設",
                 "4章 洪水吐き" if spill else None, "5章 総括表" if spill else "4章 総括表"]:
        if line:
            el.append(Paragraph(line, st["toc"]))
    el.append(PageBreak())

    # ---- 1章 設計条件
    el.append(Paragraph("1章 設計条件", st["h1"]))
    el.append(Paragraph("1.1 名称及び年確率", st["h2"]))
    el.append(_tbl([
        ["項目", "内容"],
        ["適用基準", preset["standard"]],
        ["対象県・地区", f"{preset['name']} {district['name']}地区"],
        ["洪水調節容量算定の確率年", f"1/{inp.return_period}年"],
        ["洪水吐き設計の確率年", f"1/{inp.spillway_return_period}年"],
        ["計画降雨波形",
         "中央集中型" if inp.waveform == "central" else "後方集中型"],
        ["降雨継続時間", f"{inp.duration_min}分（{inp.duration_min // 60}時間）"],
        ["計算時間単位 Δt", f"{inp.dt_min}分"],
    ], col_widths=[55 * mm, None]))
    el.append(Spacer(1, 4 * mm))
    el.append(Paragraph("1.2 施設配置", st["h2"]))
    el.append(_tbl([
        ["番号", "名称", "形式"],
        ["1", inp.basin_name, "流域"],
        ["2", inp.pond_name, "貯留施設"],
    ], col_widths=[18 * mm, None, 40 * mm]))
    el.append(PageBreak())

    # ---- 2章 流域
    el.append(Paragraph("2章 流域", st["h1"]))
    el.append(Paragraph(f"2.1 {inp.basin_name}", st["h2"]))
    rows = [
        ["項目", "値"],
        ["流域面積 A", f"{_fmt(inp.area_ha, 3)} ha"],
        ["流出係数 f", _fmt(inp.runoff_f, 3)],
        ["降雨強度式", f"{formula.label()}　[r: mm/hr, t: 分]"],
        ["確率年", f"1/{inp.return_period}年"],
        ["洪水到達時間の算定方法", tc["method"]],
        ["洪水到達時間 tc", f"{_fmt(tc['tc_min'], 1)} 分"],
        ["合理式ピーク流量 Qp = 1/360・f・r(tc)・A",
         f"{_fmt(result['rational_peak_m3s'])} m³/s"],
    ]
    el.append(_tbl(rows, col_widths=[70 * mm, None]))
    el.append(Spacer(1, 3 * mm))

    if tc["method"] == "土研式" and tc["detail"]:
        d = tc["detail"]
        el.append(Paragraph(
            f"土研式: tc = 2.40×10⁻⁴・(L/√S)^0.7、"
            f"S = {d['S']:.5f}、L/√S = {_fmt(d['L_sqrtS'], 1)}",
            st["small"]))
    if tc["method"].startswith("等流流速法") and tc["detail"]:
        drows = [["区間", "延長 L (m)", "流速 v (m/s)", "流下時間 (分)"]]
        for i, s in enumerate(tc["detail"]["sections"], 1):
            drows.append([str(i), _fmt(s["length_m"], 1),
                          _fmt(s["velocity_ms"], 1), _fmt(s["travel_min"], 1)])
        drows.append(["流入時間 t1", "", "", _fmt(tc["detail"]["t1_min"], 1)])
        drows.append(["洪水到達時間 tc", "", "", _fmt(tc["detail"]["tc_min"], 1)])
        el.append(_tbl(drows, align_right_cols=(1, 2, 3)))
        el.append(Spacer(1, 3 * mm))

    el.append(Image(_hyeto_png(hyeto, "計画降雨波形"),
                    width=160 * mm, height=63 * mm))
    el.append(Spacer(1, 3 * mm))
    el.append(Paragraph(
        f"総雨量: {_fmt(hyeto['total_mm'], 1)} mm / {inp.duration_min}分", st["body"]))
    el.append(PageBreak())

    # 計画降雨・流出量表（Δt毎、6列組で圧縮表示）
    el.append(Paragraph("2.2 計画降雨と流出量の時系列", st["h2"]))
    head = ["時刻(分)", "降雨強度(mm/hr)", "流出量(m³/s)"]
    n = len(hyeto["times"])
    half = (n + 1) // 2
    table_rows = [head + head]
    for i in range(half):
        row = [str(hyeto["times"][i]),
               _fmt(hyeto["intensity_mmhr"][i], 2),
               _fmt(inflow["flows_m3s"][i], 3)]
        j = i + half
        if j < n:
            row += [str(hyeto["times"][j]),
                    _fmt(hyeto["intensity_mmhr"][j], 2),
                    _fmt(inflow["flows_m3s"][j], 3)]
        else:
            row += ["", "", ""]
        table_rows.append(row)
    el.append(_tbl(table_rows, align_right_cols=tuple(range(6)), font_size=7.5))
    el.append(PageBreak())

    # ---- 3章 貯留施設
    el.append(Paragraph("3章 貯留施設", st["h1"]))
    el.append(Paragraph(f"3.1 {inp.pond_name}", st["h2"]))
    q_note = "（放流比流量より自動設定）" if result["allowable_q_auto"] else ""
    el.append(_tbl([
        ["項目", "値"],
        ["上流流域", inp.basin_name],
        ["許容放流量 Qa", f"{_fmt(result['allowable_q_m3s'])} m³/s {q_note}"],
        ["放流比流量", f"{_fmt(result['unit_q_m3s_per_ha'], 3)} m³/s/ha"
         if result["unit_q_m3s_per_ha"] else "－"],
        ["水位容量計算方法",
         "せつ頭錐体" if inp.hav_method == "cone" else "平均面積を有する柱体"],
        ["初期水位", f"{_fmt(routing['initial_level_m'])} m"],
    ], col_widths=[70 * mm, None]))
    el.append(Spacer(1, 4 * mm))

    el.append(Paragraph("(1) 貯留施設の容量と水位", st["h2"]))
    hav_rows = [["水位 (m)", "面積 F (m²)", "容量 V (m³)"]]
    for h, a, v in zip(stage.levels, stage.areas, stage.volumes):
        hav_rows.append([_fmt(h), _fmt(a, 1), _fmt(v, 1)])
    el.append(_tbl(hav_rows, col_widths=[40 * mm, 55 * mm, 55 * mm],
                   align_right_cols=(0, 1, 2)))
    el.append(Spacer(1, 4 * mm))

    el.append(Paragraph("(2) 放流施設", st["h2"]))
    orows = [["No", "諸元", "流量係数 C"]]
    for i, o in enumerate(result["orifices"], 1):
        orows.append([str(i), o.spec_text(), _fmt(o.c, 2)])
    el.append(_tbl(orows, col_widths=[15 * mm, None, 30 * mm]))
    el.append(Spacer(1, 4 * mm))

    el.append(Paragraph("(3) 洪水調節計算（厳密法・Δt=1分）", st["h2"]))
    el.append(Image(_hydrograph_png(routing, "流入・放流ハイドログラフ"),
                    width=160 * mm, height=75 * mm))
    el.append(Spacer(1, 2 * mm))
    el.append(_tbl([
        ["項目", "値"],
        ["最大流入量", f"{_fmt(inflow['peak_m3s'])} m³/s"
         f"（{inflow['peak_time_min']}分）"],
        ["最大放流量", f"{_fmt(routing['max_outflow_m3s'])} m³/s"
         f"（{_fmt(routing['max_outflow_time_min'], 0)}分）"],
        ["判定（最大放流量 ≦ 許容放流量）",
         "ＯＫ" if routing["max_outflow_m3s"] <= result["allowable_q_m3s"] + 1e-9
         else "ＮＧ（オリフィス断面の見直しが必要）"],
        ["必要洪水調節容量（厳密法）", f"{_fmt(routing['required_volume_m3'], 1)} m³"],
        ["計画高水位 H.W.L", f"{_fmt(routing['hwl_m'])} m"],
    ], col_widths=[75 * mm, None]))
    el.append(Spacer(1, 4 * mm))

    # ピーク付近の1分毎詳細表
    el.append(Paragraph("(4) ピーク前後の詳細（1分毎）", st["h2"]))
    times = routing["times_min"]
    peak_idx = routing["outflow_m3s"].index(max(routing["outflow_m3s"]))
    lo = max(0, peak_idx - 15)
    hi = min(len(times), peak_idx + 15)
    prows = [["時刻(分)", "流入量(m³/s)", "放流量(m³/s)", "水位(m)", "容量(m³)"]]
    for k in range(lo, hi):
        prows.append([_fmt(times[k], 0), _fmt(routing["inflow_m3s"][k]),
                      _fmt(routing["outflow_m3s"][k]),
                      _fmt(routing["levels_m"][k]),
                      _fmt(routing["volumes_m3"][k], 1)])
    el.append(_tbl(prows, align_right_cols=(0, 1, 2, 3, 4), font_size=7.5))
    el.append(Spacer(1, 4 * mm))

    el.append(Paragraph("(5) 必要洪水調節容量（簡便法）", st["h2"]))
    el.append(Paragraph(
        "V = (rᵢ − r꜀/2)・f・A・tᵢ/6　[V: m³, r: mm/hr, A: ha, t: 分]、"
        f"r꜀ = 360・Qa/(f・A) = {_fmt(simp['rc_mmhr'], 3)} mm/hr", st["small"]))
    el.append(_tbl([
        ["項目", "値"],
        ["最大となる継続時間 tᵢ", f"{simp['critical_duration_min']} 分"],
        ["そのときの降雨強度 rᵢ", f"{_fmt(simp['ri_mmhr'], 2)} mm/hr"],
        ["必要洪水調節容量（簡便法）", f"{_fmt(simp['V_m3'], 1)} m³"],
    ], col_widths=[75 * mm, None]))
    el.append(PageBreak())

    # ---- 4章 洪水吐き
    chapter = 4
    if spill:
        el.append(Paragraph("4章 洪水吐き", st["h1"]))
        el.append(Paragraph(f"4.1 {inp.pond_name}", st["h2"]))
        q2row = ([["流出量 Q2（クリーガー型比流量）", f"{_fmt(spill['Q2_m3s'])} m³/s"]]
                 if spill["Q2_m3s"] is not None else [])
        el.append(_tbl([
            ["項目", "値", "備考"],
            ["年超過確率", f"1/{inp.spillway_return_period}",
             result["spill_formula"].label()],
            ["洪水到達時間 tc", f"{_fmt(tc['tc_min'], 1)} 分", ""],
            ["降雨強度 r", f"{_fmt(spill['r_mmhr'], 2)} mm/hr", ""],
            ["流出量 Q1", f"{_fmt(spill['Q1_m3s'])} m³/s", "Q1 = 1/360・f・r・A"],
            *q2row,
            ["計算で用いる流出量 Q'", f"{_fmt(spill['Q_dash_m3s'])} m³/s",
             "max(Q1, Q2)" if spill["Q2_m3s"] is not None else "Q1"],
            ["設計洪水流量 Q", f"{_fmt(spill['Qd_m3s'])} m³/s",
             f"Q = {spill['safety_factor']:.1f}・Q'"],
        ], col_widths=[58 * mm, 45 * mm, None]))
        el.append(Spacer(1, 4 * mm))

        el.append(Paragraph("(1) 越流幅L～越流水深H曲線一覧表　"
                            f"（Q = C・L・H^1.5、C = {spill['weir_coef']:.2f}）",
                            st["h2"]))
        wrows = [["越流幅 L (m)", "Q/(C・L)", "越流水深 H (m)"]]
        for row in spill["table"]:
            wrows.append([_fmt(row["L_m"], 3), _fmt(row["Q_CL"], 3),
                          _fmt(row["H_m"], 3)])
        el.append(_tbl(wrows, col_widths=[45 * mm, 45 * mm, 45 * mm],
                       align_right_cols=(0, 1, 2)))
        el.append(Spacer(1, 4 * mm))

        el.append(Paragraph("(2) 洪水吐きおよび非越流部天端高", st["h2"]))
        fb_rows = [
            ["項目", "値"],
            ["採用越流幅 L", f"{_fmt(spill['design_width_m'])} m"],
            ["洪水吐きの越流高 H.W.L", f"{_fmt(spill['HWL_m'])} m"],
            ["越流水深 H0", f"{_fmt(spill['H0_m'])} m"],
            ["設計洪水水位 H.H.W.L", f"{_fmt(spill['HHWL_m'])} m"],
            ["非越流部の天端高（造成高）", f"{_fmt(spill['bank_level_m'])} m"],
            ["余裕高", f"{_fmt(spill['freeboard_m'])} m"],
            ["必要余裕高", f"{_fmt(spill['required_freeboard_m'])} m"],
            ["判定", "ＯＫ" if spill["freeboard_ok"] else "ＮＧ"],
        ]
        el.append(_tbl(fb_rows, col_widths=[75 * mm, None]))

        if "freeboard_check" in spill:
            fc = spill["freeboard_check"]
            el.append(Spacer(1, 4 * mm))
            el.append(Paragraph("(3) 余裕高のチェック（ダム式）", st["h2"]))
            el.append(_tbl([
                ["項目", "値", "備考"],
                ["風波高 hw", f"{_fmt(fc['wind_wave_m'])} m", ""],
                ["地震波高 he", f"{_fmt(fc['seismic_wave_m'])} m",
                 "he = k・τ/π・√(g・H)"],
                ["H1 = H.H.W.L + hw", f"{_fmt(fc['H1_m'])} m", ""],
                ["H2 = H.W.L + hw + he/2", f"{_fmt(fc['H2_m'])} m", ""],
                ["必要天端高", f"{_fmt(fc['needed_crest_m'])} m", "max(H1, H2)"],
                ["判定", "ＯＫ" if fc["ok"] else "ＮＧ（危険）", ""],
            ], col_widths=[58 * mm, 45 * mm, None]))
        el.append(PageBreak())
        chapter = 5

    # ---- 総括表
    el.append(Paragraph(f"{chapter}章 総括表", st["h1"]))
    sum_rows = [
        ["項目", "値"],
        ["流域面積", f"{_fmt(inp.area_ha, 3)} ha"],
        ["降雨強度式", formula.label()],
        ["計画降雨超過確率", f"1/{inp.return_period}年"],
        ["流出係数", _fmt(inp.runoff_f, 3)],
        ["洪水到達時間", f"{_fmt(tc['tc_min'], 1)} 分"],
        ["許容放流量", f"{_fmt(result['allowable_q_m3s'])} m³/s"],
        ["最大放流量", f"{_fmt(routing['max_outflow_m3s'])} m³/s"],
        ["必要洪水調節容量（簡便法）", f"{_fmt(simp['V_m3'], 1)} m³"],
        ["必要洪水調節容量（厳密法）", f"{_fmt(routing['required_volume_m3'], 1)} m³"],
        ["設計堆積土砂量", f"{_fmt(result['sediment_m3'], 1)} m³"],
        ["必要総容量（max(簡便法, 厳密法) + 堆積土砂）",
         f"{_fmt(result['total_required_m3'], 1)} m³"],
        ["調整池容量（H-A-V表最上段）", f"{_fmt(result['pond_capacity_m3'], 1)} m³"],
        ["容量判定", "ＯＫ" if result["capacity_ok"] else "ＮＧ（容量不足）"],
        ["計画高水位 H.W.L", f"{_fmt(routing['hwl_m'])} m"],
    ]
    if spill:
        sum_rows += [
            ["洪水吐き 設計洪水流量", f"{_fmt(spill['Qd_m3s'])} m³/s"],
            ["洪水吐き 越流水深 H0", f"{_fmt(spill['H0_m'])} m"],
            ["設計洪水水位 H.H.W.L", f"{_fmt(spill['HHWL_m'])} m"],
        ]
    el.append(_tbl(sum_rows, col_widths=[90 * mm, None]))
    el.append(Spacer(1, 6 * mm))
    el.append(Paragraph(
        f"出典: {preset['source']}", st["small"]))

    doc.build(el)
    return buf.getvalue()
