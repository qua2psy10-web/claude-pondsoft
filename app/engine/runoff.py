"""洪水到達時間と流入ハイドログラフ（合理式連続モデル）の計算。"""
import math
from dataclasses import dataclass, field


def rational_peak(f: float, r_mmhr: float, area_ha: float) -> float:
    """合理式 Q = 1/360・f・r・A  [Q: m3/s, r: mm/hr, A: ha]"""
    return f * r_mmhr * area_ha / 360.0


def kraven_velocity(gradient: float) -> float:
    """Kraven式（等流流速法）の区分流速。gradient = H/L（勾配）"""
    if gradient >= 1 / 100:
        return 3.5
    if gradient >= 1 / 200:
        return 3.0
    return 2.1


@dataclass
class ChannelSection:
    """流路の区分（Kraven式・等流流速法用）"""
    length_m: float
    gradient: float = 0.0      # H/L
    velocity_ms: float = 0.0   # 0 なら Kraven式で勾配から決定

    def velocity(self) -> float:
        return self.velocity_ms if self.velocity_ms > 0 else kraven_velocity(self.gradient)

    def travel_min(self) -> float:
        return self.length_m / self.velocity() / 60.0


def arrival_time_kraven(inlet_time_min: float, sections: list[ChannelSection]) -> dict:
    """洪水到達時間 = 流入時間 + Σ(流下時間)  （Kraven式／等流流速法）"""
    details = [
        {"length_m": s.length_m, "velocity_ms": s.velocity(), "travel_min": s.travel_min()}
        for s in sections
    ]
    t2 = sum(d["travel_min"] for d in details)
    return {"t1_min": inlet_time_min, "t2_min": t2,
            "tc_min": inlet_time_min + t2, "sections": details}


def arrival_time_doken(length_m: float, height_m: float) -> dict:
    """土研式（土木研究所）: tc = 2.40×10^-4・(L/√S)^0.7  [S = H/L]"""
    if length_m <= 0 or height_m <= 0:
        raise ValueError("流路延長・標高差は正の値を指定してください")
    s = height_m / length_m
    ls = length_m / math.sqrt(s)
    tc = 2.40e-4 * ls ** 0.7 * 60.0  # 式の値は時間(hr)単位 → 分に換算
    return {"S": s, "L_sqrtS": ls, "tc_min": tc}


def inflow_hydrograph(hyeto: dict, f: float, area_ha: float, tc_min: float) -> dict:
    """合理式連続モデルによる流入ハイドログラフ。

    各時刻 t の流出量は、直前の洪水到達時間 tc 内の平均降雨強度を合理式に
    適用して求める:  Q(t) = 1/360・f・r̄(t-tc, t)・A
    """
    dt = hyeto["dt_min"]
    times = hyeto["times"]
    cum = hyeto["cumulative_mm"]

    def cum_at(t_min: float) -> float:
        """累加雨量の折れ線補間（範囲外は端点値）"""
        if t_min <= 0:
            return 0.0
        if t_min >= times[-1]:
            return cum[-1]
        # times は等間隔 dt
        k = int(t_min // dt)
        t0 = k * dt
        c0 = cum[k - 1] if k >= 1 else 0.0
        c1 = cum[k] if k < len(cum) else cum[-1]
        return c0 + (c1 - c0) * (t_min - t0) / dt

    flows = []
    mean_intensities = []
    for t in times:
        depth = cum_at(t) - cum_at(t - tc_min)      # tc内雨量 (mm)
        r_bar = depth * 60.0 / tc_min               # 平均降雨強度 (mm/hr)
        mean_intensities.append(r_bar)
        flows.append(rational_peak(f, r_bar, area_ha))

    peak = max(flows) if flows else 0.0
    return {
        "times": times,
        "dt_min": dt,
        "flows_m3s": flows,
        "mean_intensity_mmhr": mean_intensities,
        "peak_m3s": peak,
        "peak_time_min": times[flows.index(peak)] if flows else 0,
        "cum_at": cum_at,   # 貯留追跡の内挿で再利用
        "f": f,
        "area_ha": area_ha,
        "tc_min": tc_min,
    }
