"""貯留施設: 水位-面積-容量(H-A-V)、オリフィス放流、貯留追跡計算（厳密法）。"""
import math
from dataclasses import dataclass

G = 9.8  # 重力加速度 (m/s2)


class StageStorage:
    """水位-面積表から容量を算定し、H↔V を相互変換する。

    容量計算はせつ頭錐体法（デフォルト）:
        ΔV = Δh/3・(F1 + F2 + √(F1・F2))
    または平均面積法:  ΔV = Δh・(F1 + F2)/2
    """

    def __init__(self, levels_m: list[float], areas_m2: list[float],
                 method: str = "cone"):
        if len(levels_m) != len(areas_m2) or len(levels_m) < 2:
            raise ValueError("水位と面積は同数で2点以上を指定してください")
        if any(levels_m[i] >= levels_m[i + 1] for i in range(len(levels_m) - 1)):
            raise ValueError("水位は昇順で指定してください")
        self.levels = list(levels_m)
        self.areas = list(areas_m2)
        self.method = method
        vols = [0.0]
        for i in range(1, len(levels_m)):
            dh = levels_m[i] - levels_m[i - 1]
            f1, f2 = areas_m2[i - 1], areas_m2[i]
            if method == "cone":
                dv = dh / 3.0 * (f1 + f2 + math.sqrt(f1 * f2))
            else:
                dv = dh * (f1 + f2) / 2.0
            vols.append(vols[-1] + dv)
        self.volumes = vols

    def volume_at(self, h: float) -> float:
        if h <= self.levels[0]:
            return 0.0
        if h >= self.levels[-1]:
            # 最上段の面積で外挿（追跡計算の溢水判定用）
            return self.volumes[-1] + (h - self.levels[-1]) * self.areas[-1]
        i = self._segment(h)
        h1, h2 = self.levels[i], self.levels[i + 1]
        f1, f2 = self.areas[i], self.areas[i + 1]
        dh = h - h1
        f = f1 + (f2 - f1) * dh / (h2 - h1)
        if self.method == "cone":
            dv = dh / 3.0 * (f1 + f + math.sqrt(f1 * f))
        else:
            dv = dh * (f1 + f) / 2.0
        return self.volumes[i] + dv

    def area_at(self, h: float) -> float:
        if h <= self.levels[0]:
            return self.areas[0]
        if h >= self.levels[-1]:
            return self.areas[-1]
        i = self._segment(h)
        h1, h2 = self.levels[i], self.levels[i + 1]
        f1, f2 = self.areas[i], self.areas[i + 1]
        return f1 + (f2 - f1) * (h - h1) / (h2 - h1)

    def level_at(self, v: float) -> float:
        """容量から水位を求める（区間内は二分法）"""
        if v <= 0:
            return self.levels[0]
        if v >= self.volumes[-1]:
            extra = v - self.volumes[-1]
            return self.levels[-1] + extra / self.areas[-1]
        lo, hi = 0, len(self.volumes) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.volumes[mid] <= v:
                lo = mid
            else:
                hi = mid
        a, b = self.levels[lo], self.levels[lo + 1]
        for _ in range(50):
            m = (a + b) / 2
            if self.volume_at(m) < v:
                a = m
            else:
                b = m
        return (a + b) / 2

    def _segment(self, h: float) -> int:
        lo, hi = 0, len(self.levels) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.levels[mid] <= h:
                lo = mid
            else:
                hi = mid
        return lo


@dataclass
class Orifice:
    """放流施設（オリフィス）。矩形または円形。

    水位がオリフィス天端以下のときは越流（せき）公式、天端を超えると
    オリフィス公式 Q = C・a・√(2g・(h－D/2)) で放流量を算定する。
    """
    invert_m: float          # 敷高（標高）
    shape: str = "rect"      # "rect" | "circle"
    width_m: float = 0.0     # 矩形: 幅 B
    height_m: float = 0.0    # 矩形: 高さ D
    diameter_m: float = 0.0  # 円形: 内径 d
    c: float = 0.60          # 流量係数
    weir_c: float = 1.8      # 越流時の流量係数（矩形せき）

    @property
    def opening_height(self) -> float:
        return self.height_m if self.shape == "rect" else self.diameter_m

    @property
    def area(self) -> float:
        if self.shape == "rect":
            return self.width_m * self.height_m
        return math.pi * self.diameter_m ** 2 / 4.0

    def discharge(self, level_m: float) -> float:
        hw = level_m - self.invert_m
        if hw <= 0:
            return 0.0
        d = self.opening_height
        if hw >= d:
            # オリフィス流: 開口中心からの水頭
            return self.c * self.area * math.sqrt(2 * G * (hw - d / 2.0))
        # 開口部を満たさない間は越流状態として扱う
        if self.shape == "rect":
            return self.weir_c * self.width_m * hw ** 1.5
        # 円形は水没率で開口面積を近似し、水深の1/2を水頭とする
        ratio = hw / d
        theta = 2 * math.acos(1 - 2 * ratio)
        a_sub = self.diameter_m ** 2 / 8.0 * (theta - math.sin(theta))
        return self.c * a_sub * math.sqrt(2 * G * hw / 2.0)

    def spec_text(self) -> str:
        if self.shape == "rect":
            return f"矩形 B={self.width_m:.3f}m × D={self.height_m:.3f}m (敷高 {self.invert_m:.3f}m)"
        return f"円形 φ{self.diameter_m:.3f}m (敷高 {self.invert_m:.3f}m)"


def route_storage(inflow: dict, stage: StageStorage, orifices: list[Orifice],
                  initial_level_m: float | None = None,
                  dt_sec: float = 60.0) -> dict:
    """貯留追跡計算（厳密法）。

    連続式 dV/dt = Qin(t) − Qout(H) を Δt=1分 の陽解法（半段修正）で解く。
    流入量は流入ハイドログラフの折れ線補間。
    """
    times = inflow["times"]
    flows = inflow["flows_m3s"]
    dt_grid = inflow["dt_min"]
    total_min = times[-1]

    def qin(t_min: float) -> float:
        if t_min <= 0:
            return 0.0
        if t_min >= total_min:
            return flows[-1]
        k = int(t_min // dt_grid)
        t0 = k * dt_grid
        q0 = flows[k - 1] if k >= 1 else 0.0
        q1 = flows[k] if k < len(flows) else flows[-1]
        return q0 + (q1 - q0) * (t_min - t0) / dt_grid

    def qout(level: float) -> float:
        return sum(o.discharge(level) for o in orifices)

    h0 = initial_level_m if initial_level_m is not None else stage.levels[0]
    v = stage.volume_at(h0)
    v0 = v

    n_steps = int(total_min * 60 / dt_sec)
    rec_times, rec_qin, rec_qout, rec_h, rec_v = [], [], [], [], []
    max_state = {"qout": 0.0, "level": h0, "volume": 0.0, "t_min": 0.0, "qin": 0.0}

    for k in range(1, n_steps + 1):
        t_min = k * dt_sec / 60.0
        qi_mid = qin(t_min - dt_sec / 120.0)
        # 半段修正: 前進予測した中間水位で放流量を評価する
        h_now = stage.level_at(v)
        q_pred = qout(h_now)
        v_mid = max(v + (qi_mid - q_pred) * dt_sec / 2.0, 0.0)
        q_mid = qout(stage.level_at(v_mid))
        v = max(v + (qi_mid - q_mid) * dt_sec, 0.0)
        h = stage.level_at(v)
        qo = qout(h)

        rec_times.append(t_min)
        rec_qin.append(qin(t_min))
        rec_qout.append(qo)
        rec_h.append(h)
        rec_v.append(v)

        if qo > max_state["qout"]:
            max_state.update(qout=qo, t_min=t_min)
        if v - v0 > max_state["volume"]:
            max_state.update(volume=v - v0, level=h, qin=qin(t_min))

    peak_v = max((v - v0 for v in rec_v), default=0.0)
    hwl = stage.level_at(v0 + peak_v)
    return {
        "times_min": rec_times,
        "inflow_m3s": rec_qin,
        "outflow_m3s": rec_qout,
        "levels_m": rec_h,
        "volumes_m3": rec_v,
        "max_outflow_m3s": max(rec_qout, default=0.0),
        "max_outflow_time_min": rec_times[rec_qout.index(max(rec_qout))] if rec_qout else 0.0,
        "required_volume_m3": peak_v,
        "hwl_m": hwl,
        "initial_volume_m3": v0,
        "initial_level_m": h0,
    }
