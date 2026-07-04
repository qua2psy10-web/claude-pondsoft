"""降雨強度式と計画降雨波形の計算。

降雨強度式は r = a / (t^n + b)  [r: mm/hr, t: 分] の形式で統一的に扱う。
（タルボット型: n=1、久野・石黒型: n=1/2 で b が負値になる場合を含む）
"""
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class RainFormula:
    a: float
    n: str          # "2/3" のような分数文字列（表示用に保持）
    b: float
    name: str = ""  # 例: "千葉地区 1/50"

    @property
    def n_value(self) -> float:
        return float(Fraction(self.n))

    def intensity(self, t_min: float) -> float:
        """継続時間 t(分) に対する降雨強度 r (mm/hr)"""
        if t_min <= 0:
            raise ValueError("継続時間は正の値を指定してください")
        return self.a / (t_min ** self.n_value + self.b)

    def cumulative(self, t_min: float) -> float:
        """継続時間 t(分) までの累加雨量 R (mm) = r(t)・t/60"""
        return self.intensity(t_min) * t_min / 60.0

    def label(self) -> str:
        b_str = f"{self.b:+.4g}".replace("+", "＋").replace("-", "－")
        return f"r = {self.a:.4g} / (t^({self.n}) {b_str})"


def interval_rains(formula: RainFormula, duration_min: int, dt_min: int) -> list[float]:
    """区間雨量列（降順）。d_k = R(kΔt) - R((k-1)Δt)"""
    n = duration_min // dt_min
    cum = [formula.cumulative(k * dt_min) for k in range(1, n + 1)]
    rains = [cum[0]] + [cum[k] - cum[k - 1] for k in range(1, n)]
    # 理論上 r(t)·t は単調増加・増分は単調減少だが、数値誤差に備えて降順を保証する
    return sorted(rains, reverse=True)


def arrange_waveform(rains_desc: list[float], waveform: str) -> list[float]:
    """区間雨量（降順）を計画降雨波形に並べる。

    central: 中央集中型（最大値を中央、交互に前後へ配置）
    rear:    後方集中型（時間とともに増加、最大値が最後）
    """
    n = len(rains_desc)
    if waveform == "rear":
        return list(reversed(rains_desc))
    if waveform == "central":
        # 最大値を中央に置き、以降 -1, +1, -2, +2, ... と交互に配置する
        result = [0.0] * n
        center = n // 2
        offsets = [0]
        step = 1
        while len(offsets) < n:
            if center - step >= 0 and len(offsets) < n:
                offsets.append(-step)
            if center + step < n and len(offsets) < n:
                offsets.append(step)
            step += 1
        for rank, off in enumerate(offsets):
            result[center + off] = rains_desc[rank]
        return result
    raise ValueError(f"不明な降雨波形: {waveform}")


def plan_hyetograph(formula: RainFormula, duration_min: int, dt_min: int,
                    waveform: str) -> dict:
    """計画降雨波形を作成する。

    Returns:
        times: 各区間終端時刻 (分)
        interval_mm: 区間雨量 (mm/Δt)
        intensity_mmhr: 区間平均降雨強度 (mm/hr)
        cumulative_mm: 累加雨量 (mm)
    """
    rains = interval_rains(formula, duration_min, dt_min)
    arranged = arrange_waveform(rains, waveform)
    times = [(k + 1) * dt_min for k in range(len(arranged))]
    cum = []
    total = 0.0
    for d in arranged:
        total += d
        cum.append(total)
    return {
        "times": times,
        "dt_min": dt_min,
        "interval_mm": arranged,
        "intensity_mmhr": [d * 60.0 / dt_min for d in arranged],
        "cumulative_mm": cum,
        "total_mm": total,
    }
