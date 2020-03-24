import pandas as pd
import geopandas as gpd
import shapely
import collections

from src.base import Base
from src.scout_data import ScoutData
from src.scout_census import ScoutCensus
import src.utility as utility
import numpy as np


class Boundary(Base):
    """

    :var dict Boundary.SECTION_AGES: Holds information about scout sections
    """

    SECTION_AGES = {
        'Beavers': {"ages": ["6", "7"]},
        'Cubs': {"ages": ["8", "9"], "halves": ["10"]},
        'Scouts': {"halves": ["10"], "ages": ["11", "12", "13"]},
        'Explorers': {"ages": ["14", "15", "16", "17"]}
    }

    def __init__(self, geography_name, scout_data_object: ScoutData):
        super().__init__(settings=True)

        self.scout_data = scout_data_object
        self.ons_pd = scout_data_object.ons_pd

        self.boundary_dict = None
        self.boundary_regions_data = None
        self.boundary_report = {}

        self.set_boundary(geography_name)

    @property
    def ons_column_name(self):
        return self.boundary_dict["name"]

    @property
    def shapefile_key(self):
        return self.boundary_dict["boundary"]["key"]

    @property
    def shapefile_name_column(self):
        return self.boundary_dict["boundary"]["name"]

    @property
    def data(self):
        return self.boundary_report[self.ons_column_name]

    @property
    def shapefile(self):
        return self.boundary_dict["boundary"]["shapefile"]

    def set_boundary(self, geography_name):
        """Sets the boundary_dict and boundary_regions_data members

        :param str geography_name: The type of boundary, e.g. lsoa11, pcon etc. Must be a key in ONSPostcodeDirectory.BOUNDARIES.

        :var dict self.boundary_dict: information about the boundary type
        :var self.boundary_regions_data: table of region codes and human-readable names for those codes

        :returns None: Nothing
        """
        self.logger.info(f"Setting the boundary to {geography_name}")

        boundaries_dict = self.ons_pd.BOUNDARIES

        if geography_name in boundaries_dict.keys():
            self.boundary_dict = boundaries_dict[geography_name]
            boundary_codes_dict = self.boundary_dict["codes"]
            names_and_codes_file_path = boundary_codes_dict.get("path")

            self.boundary_regions_data = pd.read_csv(
                self.ons_pd.NAMES_AND_CODES_FILE_LOCATION + names_and_codes_file_path,
                dtype={
                    boundary_codes_dict["key"]: boundary_codes_dict["key_type"],
                    boundary_codes_dict["name"]: "object"
                })
        elif geography_name in self.settings["Scout Mappings"].keys():
            self.boundary_dict = self.settings["Scout Mappings"][geography_name]
            boundary_codes_dict = self.boundary_dict["codes"]
            names_and_codes_file_path = boundary_codes_dict.get("path")

            self.boundary_regions_data = pd.read_csv(
                names_and_codes_file_path,
                dtype={
                    boundary_codes_dict["key"]: boundary_codes_dict["key_type"],
                    boundary_codes_dict["name"]: "object"
                })
        else:
            raise Exception(f"{geography_name} is an invalid boundary.\nValid boundaries include: {boundaries_dict.keys() + self.settings['Scout Mapping'].keys()}")

    def ons_to_district_mapping(self, ons_code):
        """Create json file, containing which scout districts are within an each ONS area, and how many ONS areas those districts are in.

        :param str ons_code: A field in the modified census report corresponding to an administrative region (lsoa11, msoa11, oslaua, osward, pcon, oscty, ctry, rgn)

        :returns None: Nothing
        """

        self.logger.debug("Creating mapping from ons boundary to scout district")
        codes_key = self.boundary_dict["codes"]["key"]

        region_type = ons_code  # Census column heading for the region geography type
        district_id_column = ScoutCensus.column_labels['id']["DISTRICT"]

        region_ids = self.boundary_regions_data[codes_key].dropna().drop_duplicates()

        district_ids_by_region = self.scout_data.data.loc[self.scout_data.data[region_type].isin(region_ids), [region_type, district_id_column, ]].dropna().drop_duplicates()
        district_ids = district_ids_by_region[district_id_column].dropna().drop_duplicates()

        region_ids_by_district = self.scout_data.data.loc[self.scout_data.data[district_id_column].isin(district_ids), [district_id_column, region_type]]
        region_ids_by_district = region_ids_by_district.loc[~(region_ids_by_district[region_type] == ScoutCensus.DEFAULT_VALUE)].dropna().drop_duplicates()

        count_regions_in_district = region_ids_by_district.groupby(district_id_column).count().rename(columns={region_type: "count"})  # count of how many regions the district occupies
        count_by_district_by_region = pd.merge(left=district_ids_by_region, right=count_regions_in_district, on=district_id_column)

        count_by_district_by_region = count_by_district_by_region.set_index([region_type, district_id_column])

        nested_dict = collections.defaultdict(dict)
        for keys, value in count_by_district_by_region["count"].iteritems():
            nested_dict[keys[0]][keys[1]] = value

        self.logger.debug("Finished mapping from ons boundary to district")
        return dict(nested_dict)  # Return the mapping

    def create_boundary_report(self, options=None, historical=False, report_name=None):
        """Produces .csv file summarising by boundary provided.

        Requires self.boundary_data to be set, preferably by :meth:scout_data.set_boundary

        :param list or None options: List of data to be included in report
        :param bool historical: Check to ensure that multiple years of data are intentional
        :param str report_name:
        """

        # Set default option set for `options`
        if options is None:
            options = ["Number of Sections", "Number of Groups", "Groups", "Section numbers", "6 to 17 numbers", "awards", "waiting list total"]

        opt_number_of_sections = \
            True if "Number of Sections" in options \
            else False
        opt_number_of_groups = \
            True if "Number of Groups" in options \
            else False
        opt_groups = \
            True if "Groups" in options \
            else False
        opt_section_numbers = \
            True if "Section numbers" in options \
            else False
        opt_6_to_17_numbers = \
            True if "6 to 17 numbers" in options \
            else False
        opt_awards = \
            True if "awards" in options \
            else False
        opt_waiting_list_totals = \
            True if "waiting list total" in options \
            else False
        geog_name = self.boundary_dict.get("name")  # e.g oslaua osward pcon lsoa11

        if not geog_name:
            raise Exception("boundary_dict has not been set. Try calling set_boundary")
        else:
            self.logger.info(f"Creating report by {geog_name} with {', '.join(options)} from {len(self.scout_data.data.index)} records")

        years = self.scout_data.data["Year"].drop_duplicates().dropna().sort_values().to_list()
        if len(years) > 1:
            if historical:
                self.logger.info(f"Historical analysis from {years[0]} to {years[-1]}")
            else:
                self.logger.error(f"Historical option not selected, but multiple years of data selected ({years[0]} - {years[-1]})")

        sections_dict = ScoutCensus.column_labels['sections']
        district_id_column = ScoutCensus.column_labels['id']["DISTRICT"]
        award_name = sections_dict["Beavers"]["top_award"]
        award_eligible = sections_dict["Beavers"]["top_award_eligible"]
        section_cols = {section: [sections_dict[section]["male"], sections_dict[section]["female"]] for section in sections_dict.keys() if section != "Network"}

        def groups_groupby(group_series: pd.Series):
            # Used to list the groups that operate within the boundary
            # Gets all groups in the records_in_boundary dataframe
            # Removes NaN values
            # Converts all values to strings to make sure the string operations work
            # Removes leading and trailing whitespace
            # Concatenates the Series to a string with a newline separator
            return group_series \
                .dropna().drop_duplicates() \
                .str.strip() \
                .str.cat(sep='\n')

            # boundary_data["Number of Groups"] = len(groups)
            # TODO Number of Groups

        def young_people_numbers_groupby(group_df: pd.DataFrame):
            output = {}
            dicts: pd.Series = group_df.groupby(['Year'], sort=True).apply(year_groupby).to_list()
            for row in dicts:
                output = {**output, **row}
            return output

        def year_groupby(group_df: pd.DataFrame):
            census_year = group_df.name
            output = {}
            all_young_people = 0
            waiting_list = 0

            for section, cols in section_cols.items():
                total_young_people = group_df[cols].to_numpy().sum()
                all_young_people += total_young_people
                if opt_section_numbers:
                    output[f"{section}-{census_year}"] = total_young_people
                if sections_dict[section].get("waiting_list"):
                    waiting_list += group_df[sections_dict[section]["waiting_list"]].sum()

            if opt_6_to_17_numbers:
                output[f"All-{census_year}"] = all_young_people
            if opt_waiting_list_totals:
                output[f"Waiting List-{census_year}"] = waiting_list
            if opt_number_of_sections:
                _ = 1+1
                # boundary_data[f"{sections_dict[section]['type']}s-{year}"] = len(year_records.loc[year_records["type"] == sections_dict[section]["type"]])
                # TODO Number of Sections
            return output

        def awards_groupby(group_df: pd.DataFrame, awards_data: pd.DataFrame):
            summed = group_df[[award_name, award_eligible, ]].sum()
            output = summed.to_dict()
            if summed[award_eligible] > 0:
                output[f"%-{award_name}"] = (summed[award_name] * 100) / summed[award_eligible]

            # calculates the nominal QSAs per ONS region specified.
            # Divides total # of awards by the number of Scout Districts that the ONS Region is in
            code = group_df.name
            district_ids = awards_mapping.get(code, {}) if not geog_name == "D_ID" else {code: 1}
            awards_regions_data = awards_data.loc[[id for id in district_ids.keys()]].sum()

            output["QSA"] = awards_regions_data["QSA"]
            if awards_regions_data["qsa_eligible"] > 0:
                output["%-QSA"] = 100 * awards_regions_data["QSA"] / awards_regions_data["qsa_eligible"]

            return output

        def awards_per_region(district_records, district_nums):
            district_id = district_records.name
            num_ons_regions_occupied_by_district = district_nums[district_id]

            self.logger.debug(f"{district_id} in {num_ons_regions_occupied_by_district} ons boundaries")

            return {
                # QSAs achieved in district, divided by the number of regions the district is in
                "QSA": district_records["Queens_Scout_Awards"].sum() / num_ons_regions_occupied_by_district,
                # number of young people eligible to achieve the QSA in district, divided by the number of regions the district is in
                "qsa_eligible": district_records["Eligible4QSA"].sum() / num_ons_regions_occupied_by_district
            }

        grouped_data = self.scout_data.data.groupby([geog_name], sort=False)
        dataframes = []

        if opt_groups or opt_number_of_groups:
            self.logger.debug(f"Adding group data")
            group_table: pd.Series = grouped_data[ScoutCensus.column_labels['name']["GROUP"]].apply(groups_groupby)
            dataframes.append(group_table.rename("Groups"))
            # TODO Num of Groups

        if opt_section_numbers or opt_6_to_17_numbers or opt_waiting_list_totals or opt_number_of_sections:
            self.logger.debug(f"Adding young people numbers")
            dataframes.append(grouped_data.apply(young_people_numbers_groupby).apply(pd.Series))
            # TODO Num of Sections

        if opt_awards:
            geog_names = [self.ons_pd.BOUNDARIES[boundary]['name'] for boundary in self.ons_pd.BOUNDARIES]
            if geog_name not in geog_names:
                raise ValueError(f"{geog_name} is not a valid geography name. Valid values are {geog_names}")

            self.logger.debug(f"Creating awards mapping")
            awards_mapping = self.ons_to_district_mapping(geog_name)
            district_nums = {district_id: num for district_dict in awards_mapping.values() for district_id, num in district_dict.items()}
            awards_per_district_per_regions = self.scout_data.data.groupby(district_id_column).apply(awards_per_region, district_nums).apply(pd.Series)

            self.logger.debug(f"Adding awards data")
            awards_table: pd.DataFrame = grouped_data.apply(awards_groupby, awards_per_district_per_regions).apply(pd.Series)
            top_award = awards_table[f"%-{sections_dict['Beavers']['top_award']}"]
            max_value = top_award.quantile(0.95)
            awards_table[f"%-{sections_dict['Beavers']['top_award']}"] = top_award.clip(upper=max_value)
            dataframes.append(awards_table)

        if geog_name == "lsoa11":
            self.logger.debug(f"Adding IMD deciles")
            dataframes.append(grouped_data[["imd_decile"]].first())

        renamed_cols_dict = {self.boundary_dict['codes']['name']: "Name", self.boundary_dict['codes']['key']: geog_name}

        # areas_data holds area names and codes for each area
        # Area names column is Name and area codes column is the geography type
        areas_data: pd.DataFrame = self.boundary_regions_data \
            .copy() \
            .rename(columns=renamed_cols_dict) \
            .reset_index(drop=True)

        merged_dataframes = pd.concat(dataframes, axis=1)
        output_data = areas_data.merge(merged_dataframes, how='left', left_on=geog_name, right_index=True, sort=False)
        self.boundary_report[geog_name] = output_data

        if report_name:
            self.save_report(output_data, report_name)

        return output_data

    def create_uptake_report(self, report_name=None):
        """Creates a report of scouting uptake in geographic areas

        Creates an report by the boundary that has been set, requires a boundary report to already have been run.
        Requires population data by age for the specified boundary.

        :param str report_name: Name to save the report as

        :returns pd.DataFrame: Uptake data of Scouts in the boundary
        """
        geog_name: str = self.boundary_dict.get("name")
        age_profile_path: str = self.boundary_dict.get("age_profile").get("path")
        age_profile_key: str = self.boundary_dict.get("age_profile").get("key")
        boundary_report: pd.DataFrame = self.boundary_report.get(geog_name)

        if boundary_report is None:
            raise AttributeError("Boundary report doesn't exist")
        elif age_profile_path is None:
            raise AttributeError(f"Population by age data not present for this {geog_name}")

        data_types = {str(key): "Int16" for key in range(5, 26)}
        try:
            age_profile_pd = pd.read_csv(self.settings["National Statistical folder"] + age_profile_path,
                                         dtype=data_types)
        except TypeError:
            self.logger.error("Age profiles must be integers in each age category")
            raise

        # population data
        for section, ages in Boundary.SECTION_AGES.items():
            age_profile_pd[f'Pop_{section}'] = age_profile_pd[ages["ages"]].sum(axis=1)
            age_profile_pd[f'Pop_{section}'] += age_profile_pd[ages["halves"]].sum(axis=1) // 2 if ages.get("halves") else 0
        age_profile_pd['Pop_All'] = age_profile_pd[[f"{age}" for age in range(6, 17+1)]].sum(axis=1)

        # merge population data
        cols = [f"Pop_{section}" for section in Boundary.SECTION_AGES.keys()] + ['Pop_All'] + [age_profile_key]
        uptake_report = boundary_report.merge(age_profile_pd[cols], how='left', left_on=geog_name, right_on=age_profile_key, sort=False)
        del uptake_report[age_profile_key]

        years = self.scout_data.data["Year"].drop_duplicates().dropna().sort_values()

        # add uptake data
        uptake_cols = []
        for year in years:
            for section in Boundary.SECTION_AGES.keys():
                uptake_section = uptake_report[f"{section}-{year}"] / uptake_report[f'Pop_{section}']
                max_value = uptake_section.quantile(0.975)
                uptake_report[f"%-{section}-{year}"] = uptake_section.clip(upper=max_value)
            uptake_all = uptake_report[f"All-{year}"] / uptake_report[f'Pop_All']
            max_value = uptake_all.quantile(0.975)
            uptake_report[f"%-All-{year}"] = uptake_all.clip(upper=max_value)
            # TODO explain 97.5th percentile clip
        # TODO check edge cases - 0 population and 0 or more scouts

        if report_name:
            self.save_report(uptake_report, report_name)

        return uptake_report

    def filter_boundaries_regions_data(self, field, value_list):
        """Filters the boundary_regions_data table by if the area code is within both value_list and the census_data table.

        Requires set_boundary to have been called.
        Uses ONS Postcode Directory to find which of set boundaries are within
        the area defined by the value_list.

        :param str field: The field on which to filter
        :param list value_list: The values on which to filter

        :returns None: Nothing
        """

        if not self.boundary_dict:
            raise Exception("boundary_dict has not been set, or there is no data in it")  # Has Boundary.set_boundary() been called?

        name = self.boundary_dict["name"]
        codes_key = self.boundary_dict["codes"]["key"]

        self.logger.info(f"Filtering {len(self.boundary_regions_data.index)} {name} boundaries by {field} being in {value_list}")
        # Filters ons data table if field column is in value_list. Returns ndarray of unique area codes
        boundary_subset = self.ons_pd.ons_field_mapping(field, value_list, name)
        self.logger.debug(f"This corresponds to {len(boundary_subset)} {name} boundaries")

        # Filters the boundary names and codes table by areas within the boundary_subset list
        self.boundary_regions_data = self.boundary_regions_data.loc[self.boundary_regions_data[codes_key].isin(boundary_subset)]
        self.logger.info(f"Resulting in {len(self.boundary_regions_data.index)} {name} boundaries")

    def filter_boundaries_by_scout_area(self, boundary, column, value_list):
        """Filters the boundaries, to include only those boundaries which have
        Sections that satisfy the requirement that the column is in the value_list.

        :param str boundary: ONS boundary to filter on
        :param str column: Scout boundary (e.g. C_ID)
        :param list value_list: List of values in the Scout boundary
        """
        ons_value_list = self.ons_from_scout_area(boundary, column, value_list)
        self.filter_boundaries_regions_data(boundary, ons_value_list)

    def filter_boundaries_near_scout_area(self, boundary, field, value_list):
        """Filters boundary list to those boundaries containing a scout unit matching requirements, or boundaries
        partially or fully within three kilometres of the external border (convex hull)

        #TODO investigate some method of actually finding a boundry's neighbours.

        :param str boundary: ONS boundary to filter on
        :param str field: Scout boundary (e.g. C_ID)
        :param list value_list: List of values in the Scout boundary
        """
        # Extend by 3000 metres
        distance = 3000

        # Reduce columns in dataset to minimum requirements
        reduced_points = self.scout_data.data[[field, boundary, "lat", "long"]]

        self.logger.info("Creates geometry")
        data_with_points = gpd.GeoDataFrame(reduced_points, geometry=gpd.points_from_xy(reduced_points.long, reduced_points.lat))
        data_with_points = data_with_points.drop(['lat', 'long'], axis=1)

        # Pivots the co-ordinate reference system into OS36 which uses
        # (x-y) coordinates in metres, rather than (long, lat) coordinates.
        data_with_points.crs = {'init': 'epsg:4326'}
        data_with_points = data_with_points.to_crs({'init': 'epsg:27700'})
        # TODO work out way to avoid co-ordinate pivot (i.e. convert 3km into GPS co-ords)

        self.logger.info(f"Filters for records that satify {field} in {value_list}")
        filtered_points = data_with_points.loc[data_with_points[field].isin(value_list)]
        self.logger.info(f"Resulting in {len(reduced_points.index)} number of Sections")

        self.logger.info(f"Creating area of interest")
        # Finds the outer boundary of all selected scout units and extends by `distance` in all directions to
        # incorporate nearby regions
        in_area = shapely.geometry.MultiPoint(filtered_points["geometry"].to_list()).convex_hull.buffer(distance)
        self.logger.info(f"Is result valid {in_area.geom_type}? {in_area.is_valid}. Area is {in_area.area}")

        self.logger.info(f"Finding Sections in buffered area of interest")

        nearby_values = data_with_points[data_with_points.geometry.within(in_area)][boundary]
        self.logger.info(f"Found {len(nearby_values)} Sections nearby")
        nearby_values = nearby_values.drop_duplicates().to_list()
        self.logger.info(f"Found {nearby_values}")

        self.filter_boundaries_regions_data(boundary, nearby_values)

    def ons_from_scout_area(self, ons_code, column, value_list):
        """Produces list of ONS Geographical codes that exist within a subset
        of the Scout Census data.

        :param str ons_code: A field of the ONS Postcode Directory
        :param str column: A field of the Scout Census data
        :param list value_list: Values to accept

        :returns list: List of ONS Geographical codes of type ons_code.
        """
        self.logger.info(f"Finding the ons areas that exist with {column} in {value_list}")

        records = self.scout_data.data.loc[self.scout_data.data[column].isin(value_list)]
        self.logger.debug(f"Found {len(records.index)} records that match {column} in {value_list}")

        records = records[records != ScoutCensus.DEFAULT_VALUE]
        ons_codes = records[ons_code].drop_duplicates().dropna().to_list()
        self.logger.debug(f"Found clean {len(ons_codes)} {ons_code}s that match {column} in {value_list}")

        return ons_codes

    def save_report(self, report_data, report_name):
        utility.save_report(report_data, self.settings["Output folder"], report_name, logger=self.logger)
