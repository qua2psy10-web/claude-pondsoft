"""流出・貯留・簡便法・洪水吐きエンジンのテスト。"""
import math

import pytest

from app.engine import presets
from app.engine.rainfall import RainFormula, plan_hyetograph
from app.engine.runoff import (arrival_time_doken, arrival_time_kraven,
                               ChannelSection, inflow_hydrograph, rational_peak)
from app.engine.simplified import required_volume
from app.engine.spillway import SpillwayInput, design
from app.engine.storage import Orifice, StageStorage, route_storage

ALL = presets.load_all()


def test_rational_peak():
    # Q = 1/360・f・r・A : f=0.8, r=90mm/hr, A=10ha → 2.0 m3/s
    assert rational_peak(0.8, 90.0, 10.0) == pytest.approx(2.0)


def test_doken_formula():
    # FORUM8サンプル1: H=25.0m, L=2740.0m → tc=19.0分
    res = arrival_time_doken(2740.0, 25.0)
    assert res["L_sqrtS"] == pytest.approx(28685, rel=1e-3)
    assert res["tc_min"] == pytest.approx(19.0, abs=0.5)


def test_kraven_velocity_classes():
    # FORUM8サンプル1: 勾配区分ごとの流速 2.1 / 3.0 / 3.5 m/s
    secs = [ChannelSection(1000, gradient=1 / 300),
            ChannelSection(750, gradient=1 / 150),
            ChannelSection(980, gradient=1 / 80)]
    res = arrival_time_kraven(7.0, secs)
    v = [d["velocity_ms"] for d in res["sections"]]
    assert v == [2.1, 3.0, 3.5]
    assert res["tc_min"] == pytest.approx(7.0 + 1000 / 2.1 / 60 + 750 / 3.0 / 60 + 980 / 3.5 / 60)


def test_inflow_hydrograph_peak_close_to_rational():
    """流入ハイドログラフのピークは合理式ピーク（r(tc)使用）に一致するはず。

    後方集中波形では最後の tc 分間に最大強度が集中するため、
    ピーク流量 ≒ 1/360・f・r(tc)・A となる。
    """
    fx = presets.get_formula(ALL["chiba"], "chiba", "50")
    hyeto = plan_hyetograph(fx, 1440, 10, "rear")
    tc = 10.0
    f, area = 0.8, 10.0
    inf = inflow_hydrograph(hyeto, f, area, tc)
    expected_peak = rational_peak(f, fx.intensity(tc), area)
    assert inf["peak_m3s"] == pytest.approx(expected_peak, rel=0.01)


def test_stage_storage_cone_vs_prism():
    levels = [0.0, 1.0, 2.0]
    areas = [100.0, 200.0, 400.0]
    prism = StageStorage(levels, areas, "prism")
    cone = StageStorage(levels, areas, "cone")
    assert prism.volumes[-1] == pytest.approx(150 + 300)
    v1 = 1 / 3 * (100 + 200 + math.sqrt(100 * 200))
    v2 = 1 / 3 * (200 + 400 + math.sqrt(200 * 400))
    assert cone.volumes[-1] == pytest.approx(v1 + v2)
    # H↔V 往復
    for h in (0.25, 0.5, 1.5, 1.99):
        assert cone.level_at(cone.volume_at(h)) == pytest.approx(h, abs=1e-6)


def test_orifice_discharge():
    o = Orifice(invert_m=0.0, shape="rect", width_m=0.9, height_m=0.9, c=0.6)
    # 満管: h=5.0m → Q = 0.6・0.81・√(2・9.8・(5−0.45))
    q = o.discharge(5.0)
    assert q == pytest.approx(0.6 * 0.81 * math.sqrt(2 * 9.8 * 4.55), rel=1e-9)
    # 未満管は越流式
    q_low = o.discharge(0.45)
    assert q_low == pytest.approx(1.8 * 0.9 * 0.45 ** 1.5, rel=1e-9)
    assert o.discharge(0.0) == 0.0


def test_routing_mass_balance_and_attenuation():
    """貯留追跡: 最大放流量 < 最大流入量、かつ水収支が閉じること"""
    fx = presets.get_formula(ALL["ibaraki"], "mito", "30")
    hyeto = plan_hyetograph(fx, 1440, 10, "central")
    inf = inflow_hydrograph(hyeto, 0.8, 10.0, 10.0)
    stage = StageStorage([10.0, 12.0, 14.0], [2000.0, 2500.0, 3000.0])
    orifice = Orifice(invert_m=10.0, shape="rect", width_m=0.5, height_m=0.5)
    res = route_storage(inf, stage, [orifice])
    assert res["max_outflow_m3s"] < inf["peak_m3s"]
    assert res["required_volume_m3"] > 0
    # 水収支: 総流入 − 総流出 ≒ 残留貯留量（Δt=60s の台形累積で近似）
    dt = 60.0
    vin = sum(res["inflow_m3s"]) * dt
    vout = sum(res["outflow_m3s"]) * dt
    residual = res["volumes_m3"][-1] - res["initial_volume_m3"]
    assert vin - vout == pytest.approx(residual, rel=0.02, abs=50)


def test_simplified_volume_chiba_examples():
    """千葉県手引 図5-2 の地区別例示値（A=1ha, f=0.8, 1/50）との概算照合。

    例示値は厳密法（池形状に依存）による値のため、簡便法とは±15%程度の
    差を許容してオーダーを確認する。
    """
    for district, unit_q, expected in [("chiba", 0.025, 1147),
                                       ("katsuura", 0.035, 1730),
                                       ("abiko", 0.025, 1052),
                                       ("matsudo", 0.025, 1492)]:
        fx = presets.get_formula(ALL["chiba"], district, "50")
        res = required_volume(fx, 0.8, 1.0, unit_q)
        assert res["V_m3"] == pytest.approx(expected, rel=0.15), district


def test_routing_orifice_controlled_chiba_example():
    """千葉地区の例示条件で、満水時放流量≒許容放流量となるオリフィスを
    設定した貯留追跡が例示値 1,147 m3/ha のオーダーになること"""
    fx = presets.get_formula(ALL["chiba"], "chiba", "50")
    hyeto = plan_hyetograph(fx, 1440, 10, "rear")
    inf = inflow_hydrograph(hyeto, 0.8, 1.0, 10.0)
    stage = StageStorage([0.0, 5.0], [400.0, 400.0], "prism")
    orifice = Orifice(invert_m=0.0, shape="rect", width_m=0.0766, height_m=0.0766)
    res = route_storage(inf, stage, [orifice])
    assert res["max_outflow_m3s"] == pytest.approx(0.025, abs=0.001)
    assert res["required_volume_m3"] == pytest.approx(1045, rel=0.02)


def test_spillway_design():
    fx = presets.get_formula(ALL["chiba"], "chiba", "200")
    inp = SpillwayInput(formula=fx, f=0.9, area_ha=10.0, tc_min=10.0,
                        crest_level_m=12.0, bank_level_m=13.5,
                        design_width_m=8.0, required_freeboard_m=0.3)
    res = design(inp)
    q1 = rational_peak(0.9, fx.intensity(10.0), 10.0)
    assert res["Qd_m3s"] == pytest.approx(1.2 * q1)
    h0 = (res["Qd_m3s"] / (1.8 * 8.0)) ** (2 / 3)
    assert res["H0_m"] == pytest.approx(h0)
    assert res["HHWL_m"] == pytest.approx(12.0 + h0)


def test_spillway_seismic_wave():
    """FORUM8サンプル3: k=0.20, τ=1.0s, H=6.0m → he=0.488m"""
    fx = RainFormula(a=1607, n="2/3", b=3.87)
    inp = SpillwayInput(formula=fx, f=0.84, area_ha=247.9, tc_min=10.0,
                        crest_level_m=32.0, bank_level_m=36.0,
                        design_width_m=12.0, check_freeboard=True,
                        wind_wave_m=0.812, water_depth_m=6.0)
    res = design(inp)
    assert res["freeboard_check"]["seismic_wave_m"] == pytest.approx(0.488, abs=0.002)
