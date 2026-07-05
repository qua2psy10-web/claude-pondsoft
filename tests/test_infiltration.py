"""浸透施設（有効降雨モデル）のテスト。"""
import pytest

from app.engine import presets
from app.engine.infiltration import design_infiltration, fc_from_R
from app.engine.rainfall import plan_hyetograph
from app.engine.runoff import inflow_hydrograph
from app.engine.simplified import required_volume

ALL = presets.load_all()


def test_fc_from_R_sample_kano():
    """FORUM8サンプル 加納(浸透-1): R=311 m³/h, A=247.9ha → Fc=0.1255 mm/hr"""
    assert fc_from_R(311.0, 247.9) == pytest.approx(0.1255, abs=0.0005)


def test_design_infiltration_facility_rollup():
    """施設テーブルの積み上げ: 設計浸透量 R=Σ(数量×単位設計浸透量)"""
    facs = [
        {"type_id": "trench", "quantity": 100.0, "unit_infiltration_m3h": 0.5},
        {"type_id": "masu", "quantity": 20.0, "unit_infiltration_m3h": 0.3},
    ]
    res = design_infiltration(area_ha=10.0, facilities=facs, treatment_area_ha=3.0)
    assert res["R_m3h"] == pytest.approx(100 * 0.5 + 20 * 0.3)   # 56.0
    assert res["fc_mmhr"] == pytest.approx(56.0 / (3.0 * 10.0))  # 1.8667
    assert res["treatment_ratio"] == pytest.approx(0.3)
    assert len(res["facilities"]) == 2


def test_design_infiltration_direct_fc():
    res = design_infiltration(area_ha=10.0, treatment_area_ha=3.0,
                              direct_fc_mmhr=5.0)
    assert res["fc_mmhr"] == 5.0
    assert res["R_m3h"] == pytest.approx(5.0 * 3.0 * 10.0)  # 150


def test_design_infiltration_direct_R():
    res = design_infiltration(area_ha=10.0, treatment_area_ha=2.0,
                              direct_R_m3h=100.0)
    assert res["R_m3h"] == 100.0
    assert res["fc_mmhr"] == pytest.approx(5.0)


def test_infiltration_requires_area_or_fc():
    with pytest.raises(ValueError):
        design_infiltration(area_ha=10.0, direct_R_m3h=100.0)  # Ac 未指定


def test_fc_zero_matches_baseline():
    """Fc=0 は浸透なしの流入・簡便法と完全一致すること"""
    fx = presets.get_formula(ALL["chiba"], "chiba", "50")
    hyeto = plan_hyetograph(fx, 1440, 10, "rear")
    base_inf = inflow_hydrograph(hyeto, 0.8, 10.0, 10.0)
    fc0_inf = inflow_hydrograph(hyeto, 0.8, 10.0, 10.0, fc_mmhr=0.0)
    assert fc0_inf["flows_m3s"] == base_inf["flows_m3s"]

    base_v = required_volume(fx, 0.8, 10.0, 0.25)
    fc0_v = required_volume(fx, 0.8, 10.0, 0.25, fc_mmhr=0.0)
    assert fc0_v["V_m3"] == pytest.approx(base_v["V_m3"])


def test_infiltration_reduces_peak_and_volume():
    """Fc を増やすほど流入ピーク・必要調節容量（簡便法）が単調減少すること"""
    fx = presets.get_formula(ALL["chiba"], "chiba", "50")
    hyeto = plan_hyetograph(fx, 1440, 10, "rear")
    peaks, vols = [], []
    for fc in (0.0, 5.0, 10.0, 15.0):
        inf = inflow_hydrograph(hyeto, 0.8, 10.0, 10.0, fc_mmhr=fc)
        v = required_volume(fx, 0.8, 10.0, 0.25, fc_mmhr=fc)
        peaks.append(inf["peak_m3s"])
        vols.append(v["V_m3"])
    assert all(peaks[i] > peaks[i + 1] for i in range(len(peaks) - 1))
    assert all(vols[i] > vols[i + 1] for i in range(len(vols) - 1))


def test_effective_intensity_never_negative():
    fx = presets.get_formula(ALL["chiba"], "chiba", "50")
    hyeto = plan_hyetograph(fx, 1440, 10, "rear")
    inf = inflow_hydrograph(hyeto, 0.8, 10.0, 10.0, fc_mmhr=50.0)
    assert all(ic >= 0.0 for ic in inf["effective_intensity_mmhr"])
    assert all(q >= 0.0 for q in inf["flows_m3s"])
