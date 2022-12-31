from dataclasses import dataclass
from copper.units import newUnits
import copper.constants as const
from typing import Dict


@dataclass(frozen=True)
class AirData:
    terms = [
        "leaving_water_temperature",
        "entering_condenser_temperature",
        "leaving_condenser_temperature",
    ]

    data_550_values = [
        newUnits.F_to_C(const.COOLING_LCT_550_590),
        newUnits.F_to_C(const.EVAP_ECT),
        const.UNDEFINED_CONSTANT,
    ]

    data_550 = {key: value for key, value in zip(terms, data_550_values)}

    data_551_values = [
        const.COOLING_LCT_551_591,
        const.TOWER_ECT_551_591,
        const.UNDEFINED_CONSTANT,
    ]

    data_551 = {key: value for key, value in zip(terms, data_551_values)}

    @classmethod
    def get_ahri_550(cls) -> Dict[str, float]:
        return cls.data_550

    @classmethod
    def get_ahri_551(cls) -> Dict[str, float]:
        return cls.data_551


@dataclass(frozen=True)
class WaterData:
    data_550 = {
        "leaving_water_temperature": newUnits.F_to_C(const.COOLING_LCT_550_590),
        "entering_condenser_temperature": newUnits.F_to_C(const.TOWER_ECT_550_590),
        "leaving_condenser_temperature": newUnits.F_to_C(const.TOWER_LCT_550_590),
    }

    data_551 = {
        "leaving_water_temperature": const.COOLING_LCT_551_591,
        "entering_condenser_temperature": const.TOWER_ENTERING_TEMP_551_591,
        "leaving_condenser_temperature": const.TOWER_ECT_551_591,
    }

    @classmethod
    def get_ahri_550(cls) -> Dict[str, float]:
        return cls.data_550

    @classmethod
    def get_ahri_551(cls) -> Dict[str, float]:
        return cls.data_551
