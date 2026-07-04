"""PDF計算書生成の統合テスト。"""
from app.engine.project import ProjectInput, run_project
from app.report.builder import build_pdf


def sample_input_chiba() -> ProjectInput:
    return ProjectInput(
        project_name="サンプル開発事業",
        prefecture_id="chiba",
        district_id="chiba",
        return_period="50",
        spillway_return_period="200",
        waveform="rear",
        basin_name="開発区域",
        area_ha=10.0,
        runoff_f=0.8,
        tc_method="fixed",
        tc_min=10.0,
        pond_name="調整池1号",
        hav_levels_m=[10.0, 11.0, 12.0, 13.0, 14.0],
        hav_areas_m2=[3000.0, 3300.0, 3600.0, 3900.0, 4200.0],
        orifices=[{"invert_m": 10.0, "shape": "rect",
                   "width_m": 0.25, "height_m": 0.25}],
        spillway_bank_level_m=14.0,
        pond_type="excavated",
    )


def test_run_project_chiba():
    res = run_project(sample_input_chiba())
    assert res["allowable_q_m3s"] == 0.25  # 0.025 × 10ha 自動設定
    assert res["routing"]["required_volume_m3"] > 0
    assert res["spillway"]["Qd_m3s"] > 0
    assert res["total_required_m3"] > res["routing"]["required_volume_m3"]


def test_build_pdf():
    res = run_project(sample_input_chiba())
    pdf = build_pdf(res)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 30_000


def test_run_project_ibaraki():
    inp = sample_input_chiba()
    inp.prefecture_id = "ibaraki"
    inp.district_id = "mito"
    inp.return_period = "30"
    inp.spillway_return_period = "100"
    inp.waveform = "central"
    inp.allowable_q_m3s = 0.30  # 茨城は比流量既定がないため直接指定
    res = run_project(inp)
    pdf = build_pdf(res)
    assert pdf[:5] == b"%PDF-"
