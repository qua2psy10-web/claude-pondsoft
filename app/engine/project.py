"""入力一式（プロジェクト）から計算書に必要な全結果を組み立てるオーケストレータ。"""
from dataclasses import dataclass, field

from . import presets as presets_mod
from .infiltration import design_infiltration
from .rainfall import RainFormula, plan_hyetograph
from .runoff import (ChannelSection, arrival_time_doken, arrival_time_kraven,
                     inflow_hydrograph, rational_peak)
from .simplified import required_volume
from .spillway import SpillwayInput, design as spillway_design
from .storage import Orifice, StageStorage, route_storage


@dataclass
class ProjectInput:
    # 一般条件
    title: str = "防災調整池 容量計算書"
    project_name: str = ""
    prefecture_id: str = "ibaraki"
    district_id: str = ""
    return_period: str = "30"           # 洪水調節容量算定の確率年
    spillway_return_period: str = "100"  # 洪水吐き設計の確率年
    waveform: str = "central"           # central | rear
    duration_min: int = 1440
    dt_min: int = 10

    # 流域
    basin_name: str = "流域-1"
    area_ha: float = 10.0
    runoff_f: float = 0.9
    # 洪水到達時間: 直接指定 or 土研式 or Kraven式
    tc_method: str = "fixed"            # fixed | doken | kraven
    tc_min: float = 10.0
    tc_length_m: float = 0.0
    tc_height_m: float = 0.0
    tc_inlet_min: float = 7.0
    tc_sections: list = field(default_factory=list)  # [{"length_m":..,"gradient":..}]

    # 貯留施設
    pond_name: str = "調整池"
    allowable_q_m3s: float = 0.0        # 0なら比流量×面積で自動設定（千葉）
    unit_q_m3s_per_ha: float = 0.0
    hav_levels_m: list = field(default_factory=list)
    hav_areas_m2: list = field(default_factory=list)
    hav_method: str = "cone"            # cone | prism
    initial_level_m: float | None = None
    orifices: list = field(default_factory=list)  # [{"invert_m":..,"shape":..,...}]

    # 浸透施設（有効降雨モデル）
    infiltration_enabled: bool = False
    infiltration_facilities: list = field(default_factory=list)
    # [{"type_id":.., "name":.., "quantity":.., "unit_infiltration_m3h":..}]
    infiltration_treatment_area_ha: float = 0.0
    infiltration_direct_R_m3h: float = 0.0     # >0 なら R を直接指定
    infiltration_direct_fc_mmhr: float = 0.0   # >0 なら Fc を直接指定

    # 堆積土砂
    sediment_years: float = 1.0
    sediment_unit_m3_per_ha_year: float = 150.0

    # 洪水吐き
    spillway_enabled: bool = True
    spillway_widths_m: list = field(default_factory=lambda: [5, 6, 7, 8, 9, 10, 11, 12])
    spillway_design_width_m: float = 0.0
    spillway_weir_coef: float = 1.8
    spillway_crest_level_m: float = 0.0   # 0なら追跡計算のH.W.L.を採用
    spillway_bank_level_m: float = 0.0
    spillway_required_freeboard_m: float = 0.0  # 0なら県既定値
    pond_type: str = "excavated"         # excavated(掘り込み式) | dam(ダム式)
    creager_c: float = 0.0
    check_freeboard: bool = False
    wind_wave_m: float = 0.0
    seismic_k: float = 0.20
    seismic_tau_s: float = 1.0


def _resolve_tc(inp: ProjectInput) -> dict:
    if inp.tc_method == "doken":
        res = arrival_time_doken(inp.tc_length_m, inp.tc_height_m)
        return {"method": "土研式", "tc_min": res["tc_min"], "detail": res}
    if inp.tc_method == "kraven":
        sections = [ChannelSection(length_m=s["length_m"],
                                   gradient=s.get("gradient", 0.0),
                                   velocity_ms=s.get("velocity_ms", 0.0))
                    for s in inp.tc_sections]
        res = arrival_time_kraven(inp.tc_inlet_min, sections)
        return {"method": "等流流速法（Kraven式）", "tc_min": res["tc_min"], "detail": res}
    return {"method": "直接指定", "tc_min": inp.tc_min, "detail": None}


def run_project(inp: ProjectInput) -> dict:
    all_presets = presets_mod.load_all()
    preset = all_presets[inp.prefecture_id]
    district = next(d for d in preset["districts"] if d["id"] == inp.district_id)

    formula = presets_mod.get_formula(preset, inp.district_id, inp.return_period)
    spill_formula = presets_mod.get_formula(preset, inp.district_id,
                                            inp.spillway_return_period)

    # 洪水到達時間
    tc = _resolve_tc(inp)
    tc_min = tc["tc_min"]

    # 許容放流量（未指定なら県の放流比流量で自動算定）
    allowable_q = inp.allowable_q_m3s
    unit_q = inp.unit_q_m3s_per_ha or district.get("unit_discharge_m3s_per_ha", 0.0)
    allowable_q_auto = False
    if allowable_q <= 0:
        if unit_q <= 0:
            raise ValueError("許容放流量（または放流比流量）を指定してください")
        allowable_q = unit_q * inp.area_ha
        allowable_q_auto = True

    # 浸透施設（有効降雨モデル）: 設計浸透強度 Fc を算定
    infiltration = None
    fc_mmhr = 0.0
    if inp.infiltration_enabled:
        infiltration = design_infiltration(
            area_ha=inp.area_ha,
            facilities=inp.infiltration_facilities,
            treatment_area_ha=inp.infiltration_treatment_area_ha,
            direct_R_m3h=inp.infiltration_direct_R_m3h or None,
            direct_fc_mmhr=inp.infiltration_direct_fc_mmhr or None,
        )
        fc_mmhr = infiltration["fc_mmhr"]

    # 計画降雨波形と流入ハイドログラフ（浸透施設ありなら Fc を控除）
    hyeto = plan_hyetograph(formula, inp.duration_min, inp.dt_min, inp.waveform)
    inflow = inflow_hydrograph(hyeto, inp.runoff_f, inp.area_ha, tc_min,
                               fc_mmhr=fc_mmhr)

    # 簡便法
    simp = required_volume(formula, inp.runoff_f, inp.area_ha, allowable_q,
                           t_max_min=inp.duration_min, fc_mmhr=fc_mmhr)

    # 貯留追跡（厳密法）
    stage = StageStorage(inp.hav_levels_m, inp.hav_areas_m2, inp.hav_method)
    orifices = [Orifice(**o) for o in inp.orifices]
    routing = route_storage(inflow, stage, orifices,
                            initial_level_m=inp.initial_level_m)

    # 堆積土砂・総容量
    sediment = inp.sediment_unit_m3_per_ha_year * inp.area_ha * inp.sediment_years
    total_required = max(simp["V_m3"], routing["required_volume_m3"]) + sediment

    # 洪水吐き
    spill = None
    if inp.spillway_enabled:
        crest = inp.spillway_crest_level_m or routing["hwl_m"]
        bank = inp.spillway_bank_level_m or stage.levels[-1]
        fb_default = preset.get("freeboard", {})
        required_fb = inp.spillway_required_freeboard_m
        if required_fb <= 0:
            key = "dam_type_min_m" if inp.pond_type == "dam" else "excavated_type_min_m"
            required_fb = fb_default.get(key, 0.6)
        sp_inp = SpillwayInput(
            formula=spill_formula, f=inp.runoff_f, area_ha=inp.area_ha,
            tc_min=tc_min, weir_coef=inp.spillway_weir_coef,
            crest_level_m=crest, bank_level_m=bank,
            widths_m=tuple(inp.spillway_widths_m),
            design_width_m=inp.spillway_design_width_m,
            creager_c=inp.creager_c,
            check_freeboard=inp.check_freeboard and inp.pond_type == "dam",
            wind_wave_m=inp.wind_wave_m, seismic_k=inp.seismic_k,
            seismic_tau_s=inp.seismic_tau_s,
            water_depth_m=max(crest - stage.levels[0], 0.0),
            required_freeboard_m=required_fb,
        )
        spill = spillway_design(sp_inp)

    peak_q = rational_peak(inp.runoff_f, formula.intensity(tc_min), inp.area_ha)

    return {
        "input": inp,
        "preset": preset,
        "district": district,
        "formula": formula,
        "spill_formula": spill_formula,
        "tc": tc,
        "allowable_q_m3s": allowable_q,
        "allowable_q_auto": allowable_q_auto,
        "unit_q_m3s_per_ha": unit_q,
        "infiltration": infiltration,
        "hyetograph": hyeto,
        "inflow": inflow,
        "rational_peak_m3s": peak_q,
        "simplified": simp,
        "stage": stage,
        "orifices": orifices,
        "routing": routing,
        "sediment_m3": sediment,
        "total_required_m3": total_required,
        "pond_capacity_m3": stage.volumes[-1],
        "capacity_ok": stage.volumes[-1] >= total_required,
        "spillway": spill,
    }
