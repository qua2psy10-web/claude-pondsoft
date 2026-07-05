"""入力バリデーション（run_project 冒頭の _validate）のテスト。"""
import pytest

from app.engine.project import ProjectInput, run_project


def base_input() -> ProjectInput:
    """正常に計算が通る最小構成（千葉・千葉地区）。"""
    return ProjectInput(
        project_name="検証用",
        prefecture_id="chiba",
        district_id="chiba",
        return_period="50",
        spillway_return_period="200",
        waveform="rear",
        area_ha=10.0,
        runoff_f=0.8,
        tc_method="fixed",
        tc_min=10.0,
        hav_levels_m=[10.0, 11.0, 12.0, 13.0, 14.0],
        hav_areas_m2=[3000.0, 3300.0, 3600.0, 3900.0, 4200.0],
        orifices=[{"invert_m": 10.0, "shape": "rect",
                   "width_m": 0.25, "height_m": 0.25}],
        spillway_bank_level_m=14.0,
        pond_type="excavated",
    )


def test_valid_input_passes():
    res = run_project(base_input())
    assert res["total_required_m3"] > 0


def test_hav_non_monotonic_levels():
    inp = base_input()
    inp.hav_levels_m = [10.0, 11.0, 11.0, 13.0, 14.0]  # 3行目が非増加
    with pytest.raises(ValueError, match="昇順"):
        run_project(inp)


def test_hav_length_mismatch():
    inp = base_input()
    inp.hav_areas_m2 = [3000.0, 3300.0, 3600.0]  # 行数不一致
    with pytest.raises(ValueError, match="行数"):
        run_project(inp)


def test_hav_non_positive_area():
    inp = base_input()
    inp.hav_areas_m2 = [3000.0, 3300.0, 0.0, 3900.0, 4200.0]
    with pytest.raises(ValueError, match="面積は正"):
        run_project(inp)


def test_hav_decreasing_area():
    inp = base_input()
    inp.hav_areas_m2 = [3000.0, 3300.0, 3200.0, 3900.0, 4200.0]  # 3行目で減少
    with pytest.raises(ValueError, match="減少しない"):
        run_project(inp)


def test_orifice_invert_out_of_range():
    inp = base_input()
    inp.orifices = [{"invert_m": 9.0, "shape": "rect",
                     "width_m": 0.25, "height_m": 0.25}]  # 池底10m未満
    with pytest.raises(ValueError, match="範囲外"):
        run_project(inp)


def test_orifice_rect_zero_dim():
    inp = base_input()
    inp.orifices = [{"invert_m": 10.0, "shape": "rect",
                     "width_m": 0.0, "height_m": 0.25}]
    with pytest.raises(ValueError, match="矩形"):
        run_project(inp)


def test_orifice_circle_zero_diameter():
    inp = base_input()
    inp.orifices = [{"invert_m": 10.0, "shape": "circle", "diameter_m": 0.0}]
    with pytest.raises(ValueError, match="円形"):
        run_project(inp)


def test_no_orifice():
    inp = base_input()
    inp.orifices = []
    with pytest.raises(ValueError, match="放流施設"):
        run_project(inp)


def test_spillway_crest_above_bank():
    inp = base_input()
    inp.spillway_crest_level_m = 14.0
    inp.spillway_bank_level_m = 13.5  # 越流頂 ≧ 天端
    with pytest.raises(ValueError, match="越流頂"):
        run_project(inp)


def test_infiltration_enabled_without_data():
    inp = base_input()
    inp.infiltration_enabled = True
    inp.infiltration_facilities = []
    with pytest.raises(ValueError, match="浸透施設"):
        run_project(inp)
