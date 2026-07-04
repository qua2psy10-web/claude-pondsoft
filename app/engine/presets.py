"""県別プリセット（降雨強度式・基準ルール）の読み込み。"""
import json
from pathlib import Path

from .rainfall import RainFormula

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "prefectures"


def load_all() -> dict:
    presets = {}
    for path in sorted(DATA_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
        presets[data["id"]] = data
    return presets


def get_formula(preset: dict, district_id: str, return_period: str | int) -> RainFormula:
    rp = str(return_period)
    for d in preset["districts"]:
        if d["id"] == district_id:
            if rp not in d["formulas"]:
                available = ", ".join(d["formulas"].keys())
                raise KeyError(
                    f"{preset['name']} {d['name']}地区に 1/{rp} の式はありません（選択可: {available}）")
            fx = d["formulas"][rp]
            return RainFormula(a=fx["a"], n=fx["n"], b=fx["b"],
                               name=f"{preset['name']} {d['name']}地区 1/{rp}")
    raise KeyError(f"地区 {district_id} が見つかりません")
