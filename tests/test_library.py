from unittest import TestCase

import copper as cp
import os
from copper.constants import CurveFilter

LOCATION = os.path.dirname(os.path.realpath(__file__))
CHILLER_LIB = os.path.join(LOCATION, "../copper/lib", "chiller_curves.json")


class TestLibrary(TestCase):
    def setUp(self) -> None:
        """Runs before every test. Good place to initialize values and store common objects."""
        self.lib = cp.Library(path=CHILLER_LIB)

    def tearDown(self) -> None:
        """Runs after every test and cleans up file created from the tests."""
        ...

    def test_find_equipment_df_all_except(self):
        column_name = "compressor_type"
        curve_filters = [CurveFilter(column_name, "~!scroll")]
        filtered_values = self.lib.find_equipment_df(filters=curve_filters)
        self.assertTrue(
            list(filtered_values[column_name].unique())
            == ["centrifugal", "reciprocating", "screw"]
        )

    def test_find_equipment_df_do_not_include(self):
        column_name = "compressor_type"
        curve_filters = [
            CurveFilter(column_name, "!scroll"),
            CurveFilter(column_name, "!screw"),
        ]
        filtered_values = self.lib.find_equipment_df(filters=curve_filters)
        self.assertTrue(
            list(filtered_values[column_name].unique())
            == ["centrifugal", "reciprocating"]
        )

    def test_find_equipment_df_include(self):
        column_name = "compressor_type"
        curve_filters = [
            CurveFilter(column_name, "~scroll"),
        ]
        filtered_values = self.lib.find_equipment_df(filters=curve_filters)
        self.assertTrue(list(filtered_values[column_name].unique()) == ["scroll"])

    def test_find_equipment_df_missing_column(self):
        column_name = "pump_type"
        curve_filters = [
            CurveFilter(column_name, "positive-displacement"),
        ]
        with self.assertRaises(KeyError) as context:
            self.lib.find_equipment_df(filters=curve_filters)
        self.assertTrue(
            f"{column_name} not found in columns name:" in str(context.exception)
        )

    def test_find_equipment_df_missing_value(self):
        column_name = "compressor_type"
        column_value = "vane"
        curve_filters = [
            CurveFilter(column_name, column_value),
        ]
        with self.assertRaises(ValueError) as context:
            self.lib.find_equipment_df(filters=curve_filters)
        self.assertTrue(f"{column_value} value not found in" in str(context.exception))

    def test_part_load_efficiency_calcs(self):
        """
        Test part load calculations when the library is loaded.
        """

        # Load library
        lib = cp.Library(path=CHILLER_LIB)
        self.assertTrue(lib.content()["6"]["part_eff"] > 0)

        # Check calculation for the chiller EIR model
        chlr = cp.Chiller(
            compressor_type="centrifugal",
            condenser_type="water",
            compressor_speed="constant",
            ref_cap=471000,
            ref_cap_unit="W",
            full_eff=5.89,
            full_eff_unit="cop",
            part_eff_ref_std="ahri_551/591",
            model="ect_lwt",
            sim_engine="energyplus",
            set_of_curves=lib.get_set_of_curves_by_name("6").curves,
        )

        assert round(chlr.calc_rated_eff("part", "cop"), 2) == 5.44  # IPLV.SI

        # Check calculation for the chiller EIR model
        chlr = cp.Chiller(
            compressor_type="centrifugal",
            condenser_type="water",
            compressor_speed="constant",
            ref_cap=471000,
            ref_cap_unit="W",
            full_eff=5.89,
            full_eff_unit="cop",
            part_eff_ref_std="ahri_550/590",
            model="ect_lwt",
            sim_engine="energyplus",
            set_of_curves=lib.get_set_of_curves_by_name("6").curves,
        )

        assert round(chlr.calc_rated_eff("part", "cop"), 2) == 5.47  # IPLV.IP

        # Check calculation for the reformulated chiller EIR model
        chlr = cp.Chiller(
            compressor_type="centrifugal",
            condenser_type="water",
            compressor_speed="constant",
            ref_cap=471000,
            ref_cap_unit="W",
            full_eff=5.89,
            full_eff_unit="cop",
            part_eff_ref_std="ahri_551/591",
            model="lct_lwt",
            sim_engine="energyplus",
            set_of_curves=lib.get_set_of_curves_by_name("337").curves,
        )

        assert round(chlr.calc_rated_eff("part", "cop"), 2) == 8.22  # IPLV.SI

        # Check calculation for the reformulated chiller EIR model
        chlr = cp.Chiller(
            compressor_type="centrifugal",
            condenser_type="water",
            compressor_speed="constant",
            ref_cap=471000,
            ref_cap_unit="W",
            full_eff=5.89,
            full_eff_unit="cop",
            part_eff_ref_std="ahri_550/590",
            model="lct_lwt",
            sim_engine="energyplus",
            set_of_curves=lib.get_set_of_curves_by_name("337").curves,
        )

        assert round(chlr.calc_rated_eff("part", "cop"), 2) == 8.19  # IPLV.IP
