from data.scout_data import ScoutData
from geographies.geography import Geography
from maps.map import Map
from reports.reports import Reports

if __name__ == "__main__":
    scout_data = ScoutData(csv_has_ons_pd_data=True, load_ons_pd_data=True)
    scout_data.filter_records("Year", [2019])
    scout_data.filter_records("oslaua", ["E08000035"])
    scout_data.filter_records("postcode_is_valid", [1], exclusion_analysis=True)

    boundary = Geography("lsoa", scout_data.ons_pd)
    boundary.filter_boundaries_regions_data("oslaua", ["E08000035"], scout_data.ons_pd)

    reports = Reports(boundary, scout_data)
    reports.create_boundary_report(["Section numbers", False], report_name="leeds_sections")

    dimension = {"column": "Beavers-2019", "tooltip": "Beavers 2019", "legend": "# Beavers"}
    map = Map(scout_data, map_name="Leeds")
    map.add_areas(dimension, boundary, reports, show=True)
    map.add_custom_data("../../data/National Statistical data/leeds_primary_schools.csv",
                        "Primary Schools",
                        location_cols="Postcode",
                        marker_data=["EstablishmentName"])
    map.add_sections_to_map(map.district_colour_mapping(), ["youth membership"], single_section="Beavers")
    map.save_map()
    map.show_map()
    # scout_data.close()
