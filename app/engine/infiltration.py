"""浸透施設の計算（千葉県手引 第10条・防災調節池等技術基準(案)準拠）。

浸透施設による流出抑制は「有効降雨モデル」で評価する。すなわち各時刻の
有効降雨強度 f・I から設計浸透強度 Fc を差し引き、流入ハイドログラフを低減する。

  設計浸透量 R (m³/h)  = Σ(構造形式別 数量 × 単位設計浸透量)
  設計浸透強度 Fc (mm/h) = R / (浸透処理面積 Ac(ha) × 10)
  浸透処理面積率 α      = Ac / 開発面積 A

単位設計浸透量は、飽和透水係数による基準浸透量に目詰まり・地下水位の影響係数
及び安全率を乗じた値で、現地浸透試験や雨水浸透施設技術指針(案)から与える
（本ソフトではユーザー入力とする）。
"""
from dataclasses import dataclass


# 施設種別カタログ（名称と数量の単位のみ。単位設計浸透量は入力値）
FACILITY_CATALOG = [
    {"id": "trench", "name": "浸透トレンチ", "unit": "m"},
    {"id": "masu", "name": "浸透ます", "unit": "個"},
    {"id": "pavement", "name": "透水性舗装", "unit": "m²"},
    {"id": "gutter", "name": "浸透側溝", "unit": "m"},
    {"id": "tank", "name": "大型貯留浸透槽", "unit": "個"},
    {"id": "other", "name": "その他", "unit": "－"},
]
_CATALOG_BY_ID = {c["id"]: c for c in FACILITY_CATALOG}


@dataclass
class InfiltrationFacility:
    """浸透施設の1種別。設計浸透量 = 数量 × 単位設計浸透量。"""
    type_id: str = "other"
    name: str = ""
    quantity: float = 0.0                 # 数量（延長m・個数・面積m²）
    unit_infiltration_m3h: float = 0.0    # 単位設計浸透量 (m³/h / 単位)

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        c = _CATALOG_BY_ID.get(self.type_id)
        return c["name"] if c else self.type_id

    @property
    def unit_label(self) -> str:
        c = _CATALOG_BY_ID.get(self.type_id)
        return c["unit"] if c else "－"

    @property
    def total_m3h(self) -> float:
        return self.quantity * self.unit_infiltration_m3h


def fc_from_R(R_m3h: float, treatment_area_ha: float) -> float:
    """設計浸透強度 Fc (mm/h) = R / (Ac × 10)"""
    if treatment_area_ha <= 0:
        raise ValueError("浸透処理面積は正の値を指定してください")
    return R_m3h / (treatment_area_ha * 10.0)


def design_infiltration(area_ha: float,
                        facilities: list | None = None,
                        treatment_area_ha: float = 0.0,
                        direct_R_m3h: float | None = None,
                        direct_fc_mmhr: float | None = None) -> dict:
    """浸透施設の設計浸透量・設計浸透強度を算定する。

    優先順位:
      1. direct_fc_mmhr が指定されればそれを Fc として採用
      2. direct_R_m3h が指定されれば R として採用し Fc = R/(Ac×10)
      3. facilities から R を積み上げ Fc = R/(Ac×10)

    Returns dict: R_m3h, fc_mmhr, treatment_area_ha, treatment_ratio, facilities(明細)
    """
    facs = [f if isinstance(f, InfiltrationFacility) else InfiltrationFacility(**f)
            for f in (facilities or [])]
    detail = [{
        "name": f.display_name, "unit": f.unit_label,
        "quantity": f.quantity, "unit_infiltration_m3h": f.unit_infiltration_m3h,
        "total_m3h": f.total_m3h,
    } for f in facs]

    if direct_fc_mmhr is not None and direct_fc_mmhr > 0:
        fc = direct_fc_mmhr
        R = fc * treatment_area_ha * 10.0 if treatment_area_ha > 0 else None
    else:
        R = direct_R_m3h if (direct_R_m3h is not None and direct_R_m3h > 0) \
            else sum(f.total_m3h for f in facs)
        if treatment_area_ha <= 0:
            raise ValueError("浸透処理面積（または設計浸透強度）を指定してください")
        fc = fc_from_R(R, treatment_area_ha)

    ratio = (treatment_area_ha / area_ha) if area_ha > 0 else 0.0
    return {
        "R_m3h": R,
        "fc_mmhr": fc,
        "treatment_area_ha": treatment_area_ha,
        "treatment_ratio": ratio,
        "facilities": detail,
    }
