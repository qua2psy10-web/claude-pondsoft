"""洪水吐きの設計計算。

設計洪水流量: Q = 1.2 × Q'
  Q1 = 1/360・f・r・A （洪水吐き設計確率年の降雨強度・洪水到達時間で算定）
  Q2 = q・A （クリーガー型比流量曲線、任意）
  Q' = max(Q1, Q2)
越流水深: Q = C・L・H^1.5 （自由越流、C=1.8 標準） → H = (Q/(C・L))^(2/3)
"""
import math
from dataclasses import dataclass

from .rainfall import RainFormula
from .runoff import rational_peak

G = 9.8


def creager_specific_discharge(c_region: float, area_km2: float) -> float:
    """クリーガー型比流量曲線 q = C・A'^(A'^(-0.05) − 1)  [m3/s/km2]"""
    if area_km2 <= 0:
        raise ValueError("流域面積は正の値を指定してください")
    return c_region * area_km2 ** (area_km2 ** -0.05 - 1.0)


@dataclass
class SpillwayInput:
    formula: RainFormula        # 洪水吐き設計確率年の降雨強度式
    f: float                    # 流出係数
    area_ha: float              # 流域面積 (ha)
    tc_min: float               # 洪水到達時間 (分)
    weir_coef: float = 1.8      # 越流の流量係数 C
    crest_level_m: float = 0.0  # 洪水吐き越流頂 (H.W.L) 標高
    bank_level_m: float = 0.0   # 非越流部天端高（造成高）標高
    widths_m: tuple = (5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0)
    design_width_m: float = 0.0     # 採用越流幅（0なら widths の最後）
    safety_factor: float = 1.2
    creager_c: float = 0.0          # 0なら比流量法は省略
    # 余裕高チェック（ダム式のとき）
    check_freeboard: bool = False
    wind_wave_m: float = 0.0        # 風波高 hw (m)
    seismic_k: float = 0.20         # 水平震度
    seismic_tau_s: float = 1.0      # 地震周期 τ (s)
    water_depth_m: float = 0.0      # H.W.L 時の水深 (m)
    required_freeboard_m: float = 0.6


def design(inp: SpillwayInput) -> dict:
    r = inp.formula.intensity(inp.tc_min)
    q1 = rational_peak(inp.f, r, inp.area_ha)
    q2 = None
    if inp.creager_c > 0:
        area_km2 = inp.area_ha / 100.0
        q_sp = creager_specific_discharge(inp.creager_c, area_km2)
        q2 = q_sp * area_km2
    q_dash = max(q1, q2) if q2 is not None else q1
    qd = inp.safety_factor * q_dash

    table = []
    for w in inp.widths_m:
        h = (qd / (inp.weir_coef * w)) ** (2.0 / 3.0)
        table.append({"L_m": w, "Q_CL": qd / (inp.weir_coef * w), "H_m": h})

    width = inp.design_width_m if inp.design_width_m > 0 else inp.widths_m[-1]
    h0 = (qd / (inp.weir_coef * width)) ** (2.0 / 3.0)
    hhwl = inp.crest_level_m + h0
    freeboard = inp.bank_level_m - hhwl

    result = {
        "r_mmhr": r,
        "Q1_m3s": q1,
        "Q2_m3s": q2,
        "Q_dash_m3s": q_dash,
        "Qd_m3s": qd,
        "safety_factor": inp.safety_factor,
        "weir_coef": inp.weir_coef,
        "table": table,
        "design_width_m": width,
        "H0_m": h0,
        "HWL_m": inp.crest_level_m,
        "HHWL_m": hhwl,
        "bank_level_m": inp.bank_level_m,
        "freeboard_m": freeboard,
        "freeboard_ok": freeboard >= inp.required_freeboard_m,
        "required_freeboard_m": inp.required_freeboard_m,
    }

    if inp.check_freeboard:
        he = inp.seismic_k * inp.seismic_tau_s / math.pi * math.sqrt(G * inp.water_depth_m)
        h1 = hhwl + inp.wind_wave_m
        h2 = inp.crest_level_m + inp.wind_wave_m + he / 2.0
        needed = max(h1, h2)
        result["freeboard_check"] = {
            "wind_wave_m": inp.wind_wave_m,
            "seismic_wave_m": he,
            "H1_m": h1,
            "H2_m": h2,
            "needed_crest_m": needed,
            "ok": inp.bank_level_m >= needed,
        }
    return result
