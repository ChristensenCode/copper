"""
library.py
====================================
This is the library module of Copper. It contains functions used to parse the JSON library files.
"""

import json, inspect
from copper.units import *
from copper.curves import *
import copper.chiller
from copper.constants import CURVE_DATA, CurveFilter, CurveTypes
from typing import List, Dict


location = os.path.dirname(os.path.realpath(__file__))
chiller_lib = os.path.join(location, "lib", "chiller_curves.json")


class Library:
    def __init__(self, path=CURVE_DATA, rating_std="", export=False):
        # TODO: move whatever is going on here that's not initialization into it's
        # own method to keep the initialization process clean.
        self.path = path
        self.rating_std = rating_std

        # Load library
        self.data = json.loads(open(self.path, "r").read())

        # pandas verson of data
        self.df_data = self.read_chiller_curve_data(self.path)

        # Calculate part load efficiency for each item in the library
        for item, vals in self.data.items():

            # Cannot calculate the part load efficiency
            # if full load efficiency is not specified
            if not vals["full_eff"] is None and vals["condenser_type"] != "hr_scroll":

                # Get equipment properties
                props = inspect.getfullargspec(
                    eval("copper." + vals["eqp_type"].capitalize()).__init__
                )[0]
                if "self" in props:
                    props.remove("self")

                # Set the equipment properties
                # using values from the library
                obj_args = {}
                for p in props:
                    if (
                        not "part_eff" in p
                        and not "set_of_curves" in p
                        and not "alt" in p
                    ):
                        obj_args[p] = vals[p]

                # Temporarily set the part load efficiency to the
                # full load efficiency, units are assumed to be
                # the same
                obj_args["part_eff_unit"] = vals["full_eff_unit"]
                obj_args["part_eff"] = vals["full_eff"]

                # Create instance of the equipment
                obj = eval("copper." + vals["eqp_type"].capitalize())(**obj_args)

                # Retrieve curves for library item
                obj_args["set_of_curves"] = self.get_set_of_curves_by_name(item).curves

                if export:
                    self.get_set_of_curves_by_name(item).export("./curves", fmt="idf")

                # Set rating Stds
                if self.rating_std != "":
                    obj_args["part_eff_ref_std"] = self.rating_std

                # Update instance of the equipment
                obj = eval("copper." + vals["eqp_type"].capitalize())(**obj_args)

                # Compute part load efficiency
                part_eff = obj.calc_rated_eff(
                    eff_type="part", unit=vals["full_eff_unit"]
                )

                # Set part load efficiency if
                # the calculation was sucessful
                if part_eff > -999:
                    vals["part_eff"] = part_eff
                    vals["part_eff_unit"] = vals["full_eff_unit"]
                else:
                    if "part_eff" in vals.keys():
                        del vals["part_eff"]
                    if "part_eff_unit" in vals.keys():
                        del vals["part_eff_unit"]

    def read_chiller_curve_data(self, path_to_chiller_curves: str) -> pd.DataFrame:
        # Creates an empty dataframe to build with data
        flattened_df = pd.DataFrame()

        # Retains the original curve number in the chiller_curves.json
        read_in_chiller_curves = pd.read_json(path_to_chiller_curves).transpose()
        read_in_chiller_curves.reset_index(inplace=True)
        read_in_chiller_curves.rename(columns={"index": "curve_number"}, inplace=True)

        # Loops over the original dataframe row by row. TODO: this could probably be vectorized.
        for _, original_row_data in read_in_chiller_curves.iterrows():
            # Creates a dataframe based on the set_of_curves data from the original dataframe.
            set_of_curve_data = pd.DataFrame(
                original_row_data["set_of_curves"]
            ).transpose()

            set_of_curve_data.drop(columns=["out_var"], inplace=True)
            set_of_curve_data["out_var"] = [
                CurveTypes.EIR_F_T,
                CurveTypes.CAP_F_T,
                CurveTypes.EIR_F_PLR,
            ]

            # The index should be dropped inplace because it's not needed.
            set_of_curve_data.reset_index(inplace=True, drop=True)

            # Repeats the original row based on the number of items in the set_of_curves
            row_data = pd.concat(
                [pd.DataFrame(original_row_data.drop("set_of_curves")).transpose()]
                * len(set_of_curve_data)
            )

            # Again the index data is not needed
            row_data.reset_index(inplace=True, drop=True)

            # Combines the repeated row data with the set_of_curves data
            merge_with_original = pd.concat([row_data, set_of_curve_data], axis=1)

            # Appends the new updated rows to the empty dataframe
            flattened_df = pd.concat([flattened_df, merge_with_original], axis=0)
            # to create csv --> flattened_df.to_csv("chiller_curves.csv", index=False, header=True)
            # Cleans up the index after the merge.
            flattened_df.reset_index(inplace=True, drop=True)
        return flattened_df

    def load_obj(self, data):
        """Load data for an equipment from the libary.
        :param dict data: Equipment data in a dict format
        :return: Instance of the equipment in Copper (e.g. copper.chiller.Chiller)
        """
        # Get equipment properties
        props = inspect.getfullargspec(
            eval("copper." + data["eqp_type"].capitalize()).__init__
        )[0]
        props.remove("self")

        # Set the equipment properties
        # using values from the library
        obj_args = {}
        for p in props:
            if not "part_eff" in p and not "set_of_curves" in p and not "alt" in p:
                obj_args[p] = data[p]

        # Temporarily set the part load efficiency to the
        # full load efficiency, units are assumed to be
        # the same
        obj_args["part_eff_unit"] = data["full_eff_unit"]
        obj_args["part_eff"] = data["full_eff"]

        # Create instance of the equipment
        obj = eval("copper." + data["eqp_type"].capitalize())(**obj_args)

        return obj

    def content(self):
        """Content of a library in a dict format.

        :return: Dictionary of the data contained in a library
        :rtype: dict
        """
        return self.data

    def _remove_set_of_curves(self, curve_data: List[Dict]) -> pd.DataFrame:
        curve_data_without_set_of_curves = curve_data.copy()
        for curve_data in curve_data_without_set_of_curves:
            del curve_data["set_of_curves"]
        return pd.DataFrame(curve_data_without_set_of_curves)

    def _merge_curve_data(self, curve_data: pd.DataFrame) -> Dict[str, List]:
        unique_items = {}
        for column_name in curve_data.columns:
            unique_items[column_name] = list(curve_data[column_name].unique())
        return unique_items

    def get_unique_curve_fields(self):
        """Get all unique values for each field of a particular equipment.

        :return: Dictionary showing all unique values for each equipment field.
        :rtype: dict

        """
        # Store all value for each field
        curve_data_parameters = list(self.data.values())
        remove_set_of_curves = self._remove_set_of_curves(curve_data_parameters)
        return self._merge_curve_data(remove_set_of_curves)

    def find_set_of_curves_from_lib(self, filters=[], part_eff_flag=False):
        """Retrieve sets of curves from a library matching specific filters.

        :param list filters: List of filters, represented by tuples (field, val)
        :return: List of sets of curves object matching the filters
        :rtype: list

        """
        # Find name of equiment that match specified filter
        eqp_match = self.find_equipment(filters)

        # List of sets of curves that match specified filters
        set_of_curvess = []

        # Retrieve identified equipment's sets of curves from the library
        for name, props in eqp_match.items():
            c_set = SetofCurves()

            # Get equipment properties
            eqp_props = inspect.getfullargspec(
                eval("copper." + props["eqp_type"].capitalize()).__init__
            )[0]
            eqp_props.remove("self")

            # Set the equipment properties
            # using values from the library
            obj_args = {}
            for p in eqp_props:
                if not "set_of_curves" in p:
                    if part_eff_flag and "part_eff" in p:
                        if p == "part_eff_ref_std":
                            obj_args["part_eff_ref_std"] = "ahri_550/590"
                        else:
                            if p in props.keys():
                                obj_args[p] = props[p]
                    elif "part_eff" in p or "alt" in p:
                        pass
                    else:
                        obj_args[p] = props[p]

            # Create instance of the equipment
            obj = eval("copper." + props["eqp_type"].capitalize())(**obj_args)
            c_set.eqp = obj

            # Retrive all attributes of the sets of curves object
            for c_att in list(c_set.__dict__):
                # Set the attribute of new Curve object
                # if attrubute are identified in database entry
                if c_att in list(self.data[name].keys()):
                    c_set.__dict__[c_att] = self.data[name][c_att]

            c_lst = []

            # Create new SetofCurves and Curve objects for all the
            # sets of curves identified as matching the filters
            for c in self.data[name]["set_of_curves"]:
                c_lst.append(
                    self.get_curve(
                        c,
                        self.data[name],
                        eqp=self.load_obj(self.data[name]),
                    )
                )
            c_set.curves = c_lst
            set_of_curvess.append(c_set)

        return set_of_curvess

    def find_equipment_df(self, filters: List[CurveFilter] = None) -> pd.DataFrame:
        """Find equipment matching specified filter in the curve library.

        Special filter characters:

        - ~! means "all except..."
        - ! means "do not include..."
        - ~ means "include..."

        :param list filters: List of filters, represented by namedtuples (column_name, column_data)
        :return: A dataframe that's been reduced based on the provided list of filters.
        :rtype: pd.DataFrame

        """
        if filters is None:
            filters = []

        data_to_reduce = self.df_data.copy()
        all_except = "~!"
        do_not_include = "!"
        include = "~"

        for column_name, filter_criteria in filters:
            # Removes the special characters and removes any leading or trailing spaces.
            cleaned_filter_criteria = (
                filter_criteria.replace("!", "").replace("~", "").strip()
            )

            # Checks to make sure the columns and corresponding data values exist.
            if column_name not in data_to_reduce.columns:
                raise KeyError(
                    f"{column_name} not found in columns name: {data_to_reduce.columns}"
                )
            elif cleaned_filter_criteria not in data_to_reduce[column_name].unique():
                raise ValueError(
                    f"{cleaned_filter_criteria} value not found in {column_name} column"
                )

            # Starts applying filters
            if filter_criteria.startswith(all_except):
                column_values = list(data_to_reduce[column_name].unique())
                column_values.remove(cleaned_filter_criteria)
                data_to_reduce = data_to_reduce[
                    data_to_reduce[column_name].isin(column_values)
                ]
                continue

            elif filter_criteria.startswith(do_not_include):
                data_to_reduce = data_to_reduce[
                    data_to_reduce[column_name] != cleaned_filter_criteria
                ]
                continue

            elif filter_criteria.startswith(include):
                data_to_reduce = data_to_reduce[
                    data_to_reduce[column_name] == cleaned_filter_criteria
                ]
                continue

            data_to_reduce = data_to_reduce[
                data_to_reduce[column_name] == filter_criteria
            ]
        return data_to_reduce

    def find_equipment(self, filters: List[CurveFilter] = None):
        """Find equipment matching specified filter in the curve library.

        Special filter characters:

        - ~! means "all except..."
        - ! means "do not include..."
        - ~ means "include..."

        :param list filters: List of filters, represented by tuples (field, val)
        :return: Dictionary of field for each equipment matching specified filter
        :rtype: dict

        """
        if filters is None:
            filters = []

        eqp_match_dict = {}
        for eqp in self.data:
            assertions = []
            for prop, val in filters:
                # ~! = all but...
                if "~!" in val:
                    assertions.append(
                        val.replace("~!", "").lower().strip()
                        not in self.data[eqp][prop].lower().strip()
                    )
                # ! = does not include
                elif "!" in val:
                    assertions.append(self.data[eqp][prop] != val)
                # ~ = includes
                elif "~" in val:
                    assertions.append(
                        val.replace("~", "").lower().strip()
                        in self.data[eqp][prop].lower().strip()
                    )
                else:
                    assertions.append(self.data[eqp][prop] == val)
            if all(assertions):
                eqp_match_dict[eqp] = self.data[eqp]

        return eqp_match_dict

    def get_set_of_curves_by_name(self, curve_name):
        """Retrieve set of curves from the library by name.

        :param str name: Curve name
        :return: Set of curves object
        :rtype: SetofCurves

        """
        # Initialize set of curves object
        c_set = SetofCurves()
        c_set.name = curve_name

        # List of curves
        c_lst = []
        # Define curve objects
        try:
            for c in self.data[curve_name]["set_of_curves"]:
                c_lst.append(
                    self.get_curve(
                        c,
                        self.data[curve_name],
                        eqp=self.load_obj(self.data[curve_name]),
                    )
                )
            # Add curves to set of curves object
            c_set.curves = c_lst
            return c_set
        except:
            raise ValueError("Cannot find curve in library.")

    def get_curve(self, c, c_name, eqp):
        """Retrieve individual attribute of a curve object.

        :param Curve c: Curve object
        :param str c_name: Name of the curve object
        :param str eqp_type: Type of equipment associated with the curve
        :return: Curve object
        :rtype: Curve

        """
        # Curve properties
        c_prop = c_name["set_of_curves"][c]
        # Initialize curve object
        c_obj = Curve(eqp, c_prop["type"])
        c_obj.out_var = c
        # Retrive all attributes of the curve object
        for c_att in list(Curve(eqp, c_prop["type"]).__dict__):
            # Set the attribute of new Curve object
            # if attrubute are identified in database entry
            if c_att in list(c_prop.keys()):
                c_obj.__dict__[c_att] = c_prop[c_att]
        return c_obj

    def find_base_curves(self, filters, eqp):
        """Find an existing equipment curve that best matches the equipment.

        :param list filters: List of filters, represented by tuples (field, val)
        :param eqp: Instance of the equipment in Copper (e.g. copper.chiller.Chiller)
        :return: Set of curves object
        :rtype: SetofCurves

        """
        # Find equipment match in the library
        eqp_match = self.find_equipment(filters=filters)

        if len(eqp_match) > 0:
            # If multiple equipment match the specified properties,
            # return the one that has numeric attributes that best
            # match the proposed case
            if len(eqp_match) > 1:
                return self.get_set_of_curves_by_name(
                    self.get_best_match(eqp, eqp_match)
                )
            else:
                return self.get_set_of_curves_by_name(eqp_match)
        else:
            raise ValueError(
                "Could not find a set of curves that matches the specified properties."
            )

    def get_best_match(self, eqp, matches):
        """Find the set of curves matching the equipment characteristics the best.

        :param eqp: Instance of the equipment in Copper (e.g. copper.chiller.Chiller)
        :param dict matches: All potential matches
        :return: Name of the set of curves that best matches the equipment characteristics
        :rtype: str

        """
        # Initialize numeric attribute difference
        diff = float("inf")

        # Iterate over matches and calculate the
        # difference in numeric fields
        for name, val in matches.items():
            # Retrieve full load/reference numeric attribute
            if eqp.type == "chiller":
                cap = val["ref_cap"]
                cap_unit = val["ref_cap_unit"]
                eff = val["full_eff"]
                eff_unit = matches[name]["full_eff_unit"]

                if cap is not None:
                    # Capacity conversion
                    if cap_unit != eqp.ref_cap_unit:
                        c_unit = Units(cap, cap_unit)
                        cap = c_unit.conversion(eqp.ref_cap_unit)
                        cap_unit = eqp.ref_cap_unit

                    # Efficiency conversion
                    if eff_unit != eqp.full_eff_unit:
                        c_unit = Units(eff, eff_unit)
                        eff = c_unit.conversion(eqp.full_eff_unit)
                        eff_unit = eqp.full_eff_unit

                    # Compute difference
                    c_diff = abs((eqp.ref_cap - cap) / eqp.ref_cap) + abs(
                        (eqp.full_eff - eff) / eqp.full_eff
                    )

                    if c_diff < diff:
                        # Update lowest numeric difference
                        diff = c_diff

                        # Update best match
                        best_match = name

        return best_match
