"""防災調整池 計算ソフト — FastAPI アプリケーション。

起動:  uvicorn app.main:app --reload
"""
import io
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel, Field

from .engine import presets as presets_mod
from .engine.project import ProjectInput, run_project
from .report.builder import build_pdf

BASE = Path(__file__).resolve().parent

app = FastAPI(title="防災調整池 計算ソフト")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


class OrificeIn(BaseModel):
    invert_m: float
    shape: str = "rect"
    width_m: float = 0.0
    height_m: float = 0.0
    diameter_m: float = 0.0
    c: float = 0.60


class SectionIn(BaseModel):
    length_m: float
    gradient: float = 0.0
    velocity_ms: float = 0.0


class CalcRequest(BaseModel):
    title: str = "防災調整池 容量計算書"
    project_name: str = ""
    prefecture_id: str
    district_id: str
    return_period: str
    spillway_return_period: str
    waveform: str = "central"
    duration_min: int = 1440
    dt_min: int = 10

    basin_name: str = "流域-1"
    area_ha: float = Field(gt=0)
    runoff_f: float = Field(gt=0, le=1.0)
    tc_method: str = "fixed"
    tc_min: float = 10.0
    tc_length_m: float = 0.0
    tc_height_m: float = 0.0
    tc_inlet_min: float = 7.0
    tc_sections: list[SectionIn] = []

    pond_name: str = "調整池"
    allowable_q_m3s: float = 0.0
    unit_q_m3s_per_ha: float = 0.0
    hav_levels_m: list[float]
    hav_areas_m2: list[float]
    hav_method: str = "cone"
    initial_level_m: float | None = None
    orifices: list[OrificeIn]

    sediment_years: float = 1.0
    sediment_unit_m3_per_ha_year: float = 150.0

    spillway_enabled: bool = True
    spillway_widths_m: list[float] = [5, 6, 7, 8, 9, 10, 11, 12]
    spillway_design_width_m: float = 0.0
    spillway_weir_coef: float = 1.8
    spillway_crest_level_m: float = 0.0
    spillway_bank_level_m: float = 0.0
    spillway_required_freeboard_m: float = 0.0
    pond_type: str = "excavated"
    creager_c: float = 0.0
    check_freeboard: bool = False
    wind_wave_m: float = 0.0
    seismic_k: float = 0.20
    seismic_tau_s: float = 1.0

    def to_project(self) -> ProjectInput:
        data = self.model_dump()
        data["tc_sections"] = [s.model_dump() for s in self.tc_sections]
        data["orifices"] = [o.model_dump() for o in self.orifices]
        return ProjectInput(**data)


def _run(req: CalcRequest) -> dict:
    try:
        return run_project(req.to_project())
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/api/presets")
def api_presets():
    return presets_mod.load_all()


@app.post("/api/calculate")
def api_calculate(req: CalcRequest):
    res = _run(req)
    routing = res["routing"]
    spill = res["spillway"]
    return {
        "formula": res["formula"].label(),
        "spill_formula": res["spill_formula"].label(),
        "tc_min": res["tc"]["tc_min"],
        "tc_method": res["tc"]["method"],
        "total_rain_mm": res["hyetograph"]["total_mm"],
        "rational_peak_m3s": res["rational_peak_m3s"],
        "inflow_peak_m3s": res["inflow"]["peak_m3s"],
        "allowable_q_m3s": res["allowable_q_m3s"],
        "allowable_q_auto": res["allowable_q_auto"],
        "max_outflow_m3s": routing["max_outflow_m3s"],
        "outflow_ok": routing["max_outflow_m3s"] <= res["allowable_q_m3s"] + 1e-9,
        "required_volume_strict_m3": routing["required_volume_m3"],
        "required_volume_simplified_m3": res["simplified"]["V_m3"],
        "critical_duration_min": res["simplified"]["critical_duration_min"],
        "hwl_m": routing["hwl_m"],
        "sediment_m3": res["sediment_m3"],
        "total_required_m3": res["total_required_m3"],
        "pond_capacity_m3": res["pond_capacity_m3"],
        "capacity_ok": res["capacity_ok"],
        "spillway": None if spill is None else {
            "Qd_m3s": spill["Qd_m3s"],
            "H0_m": spill["H0_m"],
            "HWL_m": spill["HWL_m"],
            "HHWL_m": spill["HHWL_m"],
            "freeboard_m": spill["freeboard_m"],
            "freeboard_ok": spill["freeboard_ok"],
        },
        # グラフ描画用の間引き系列（10分毎）
        "series": {
            "times_min": routing["times_min"][9::10],
            "inflow": routing["inflow_m3s"][9::10],
            "outflow": routing["outflow_m3s"][9::10],
            "levels": routing["levels_m"][9::10],
        },
    }


@app.post("/api/report")
def api_report(req: CalcRequest):
    res = _run(req)
    pdf = build_pdf(res)
    name = urllib.parse.quote(f"{req.pond_name}_容量計算書.pdf")
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{name}"})
