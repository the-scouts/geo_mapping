from src.scout_data import ScoutData
from src.boundary import Boundary
from src.map import Map

if __name__ == "__main__":

    scout_data = ScoutData(load_ons_pd_data=True)
    scout_data.filter_records("Year", [2015, 2016, 2017, 2018, 2019])
    scout_data.filter_records("postcode_is_valid", [1])
    scout_data.filter_records("C_ID", [10000122])
    print(scout_data.scout_census.data)
    scout_data.add_imd_decile()

    boundary = Boundary("lsoa", scout_data)
    boundary.filter_boundaries_by_scout_area("oslaua" , "C_ID", [10000122])
    boundary.filter_records_by_boundary()
    boundary.create_boundary_report(["Section numbers"], historical=True, report_name="central_yorkshire_by_lsoa8")   # TODO: before postcode filtering

    dimension = {"column": "imd_decile", "tooltip": "IMD", "legend": "IMD Decile"}
    map = Map(scout_data, boundary, dimension, map_name="central_yorkshire")
    map.add_sections_to_map(map.district_colour_mapping(), ["youth membership"])
    map.save_map()
    map.show_map()
    scout_data.close()
