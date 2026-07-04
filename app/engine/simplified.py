"""簡便法（大規模宅地開発に伴う調整池技術基準（案）の一般式）による必要調節容量。

V(ti) = (ri − rc/2)・f・A・ti / 6   [V: m3, r: mm/hr, A: ha, t: 分]
  ri: 継続時間 ti に対する降雨強度
  rc: 許容放流量に相当する降雨強度  rc = 360・Qc/(f・A)
継続時間 ti を掃引して最大となる V を必要調節容量とする。
"""
from .rainfall import RainFormula


def required_volume(formula: RainFormula, f: float, area_ha: float,
                    allowable_q_m3s: float, t_max_min: int = 1440,
                    dt_min: int = 1) -> dict:
    if f <= 0 or area_ha <= 0:
        raise ValueError("流出係数・流域面積は正の値を指定してください")
    rc = 360.0 * allowable_q_m3s / (f * area_ha)
    best = {"V_m3": 0.0, "ti_min": 0, "ri_mmhr": 0.0}
    rows = []
    for ti in range(dt_min, t_max_min + 1, dt_min):
        ri = formula.intensity(ti)
        v = (ri - rc / 2.0) * f * area_ha * ti / 6.0
        rows.append((ti, ri, v))
        if v > best["V_m3"]:
            best = {"V_m3": v, "ti_min": ti, "ri_mmhr": ri}
    return {
        "rc_mmhr": rc,
        "V_m3": best["V_m3"],
        "critical_duration_min": best["ti_min"],
        "ri_mmhr": best["ri_mmhr"],
        "sweep": rows,
    }
