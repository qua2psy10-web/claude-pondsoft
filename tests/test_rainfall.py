"""降雨強度式を基準書の数値表と照合するテスト。

照合元:
- 茨城県 道路計画設計マニュアル 表8-3-7（館野）・表8-3-8（水戸）
- 千葉県 手引 巻末資料－1（7地区の確率別降雨強度式及び確率雨量の表）
"""
import pytest

from app.engine import presets
from app.engine.rainfall import plan_hyetograph

ALL = presets.load_all()


def r(pref, district, rp, t):
    return presets.get_formula(ALL[pref], district, rp).intensity(t)


# (地区, 確率年, t分, 期待値mm/hr) — 基準書の数値表から抜粋
IBARAKI_CASES = [
    ("tateno", "50", 10, 178.58),
    ("tateno", "50", 60, 84.74),
    ("tateno", "50", 1440, 12.99),
    ("tateno", "30", 60, 74.57),
    ("tateno", "200", 10, 226.22),
    ("mito", "50", 10, 188.72),
    ("mito", "50", 60, 83.62),
    ("mito", "50", 120, 56.91),
    ("mito", "200", 1440, 16.85),
    ("mito", "10", 60, 59.27),
]

CHIBA_CASES = [
    ("abiko", "50", 60, 63.0),
    ("abiko", "200", 60, 72.1),
    ("yokotone", "50", 60, 91.2),
    ("yokotone", "200", 10, 278.3),
    ("choshi", "50", 60, 84.3),
    ("matsudo", "50", 60, 70.0),
    ("chiba", "50", 60, 72.9),
    ("chiba", "200", 60, 87.0),
    ("katsuura", "50", 60, 103.7),
    ("tateyama", "50", 60, 82.4),
    ("tateyama", "200", 1440, 18.2),
]


@pytest.mark.parametrize("district,rp,t,expected", IBARAKI_CASES)
def test_ibaraki_table(district, rp, t, expected):
    # 基準書の数値表は係数の丸め違いで ±0.3% 程度の差がある
    assert r("ibaraki", district, rp, t) == pytest.approx(expected, rel=0.005)


@pytest.mark.parametrize("district,rp,t,expected", CHIBA_CASES)
def test_chiba_table(district, rp, t, expected):
    assert r("chiba", district, rp, t) == pytest.approx(expected, rel=0.005)


def test_hyetograph_mass_conservation():
    """波形の並べ替えで総雨量が保存されること"""
    fx = presets.get_formula(ALL["chiba"], "chiba", "50")
    for wf in ("central", "rear"):
        hyeto = plan_hyetograph(fx, 1440, 10, wf)
        assert hyeto["total_mm"] == pytest.approx(fx.cumulative(1440), rel=1e-9)
        assert len(hyeto["interval_mm"]) == 144


def test_rear_waveform_monotonic():
    fx = presets.get_formula(ALL["chiba"], "chiba", "50")
    hyeto = plan_hyetograph(fx, 1440, 10, "rear")
    seq = hyeto["interval_mm"]
    assert all(seq[i] <= seq[i + 1] + 1e-12 for i in range(len(seq) - 1))


def test_central_waveform_peak_at_center():
    fx = presets.get_formula(ALL["ibaraki"], "mito", "30")
    hyeto = plan_hyetograph(fx, 1440, 10, "central")
    seq = hyeto["interval_mm"]
    assert seq.index(max(seq)) == len(seq) // 2
