"""Awards Mapping

This script produces a boundary report by local authority district, and plots
the percentage of Chief Scout Bronze Awards awarded between 31st January 2018
and 31st January 2019 of the eligible Beavers. and percentage of QSAs.

This script has no command line options.
"""

from src.data.scout_data import ScoutData
from src.reports.reports import Reports
from src.maps.map import Map

if __name__ == "__main__":
    year = 2020

    scout_data = ScoutData()
    # scout_data.filter_records("postcode_is_valid", [1])
    scout_data.filter_records("Year", [year])
    # Remove Jersey, Guernsey, and Isle of Man as they don't have lat long coordinates in their postcodes
    scout_data.filter_records("C_name", ["Bailiwick of Guernsey", "Isle of Man", "Jersey"], mask=True)

    # Generate boundary report
    reports = Reports("lad", scout_data)
    reports.create_boundary_report(["awards"], report_name="laua_awards_report")

    # Create map object
    mapper = Map(scout_data, map_name="UK_QSA_awards")

    # Plot
    dimension = {"column": "%-QSA", "tooltip": "QSA %", "legend": "QSA %"}
    mapper.add_areas(dimension, reports, show=True)
    mapper.add_sections_to_map(scout_data, mapper.district_colour_mapping(), ["youth membership", "awards"], single_section="Explorers", cluster_markers=True)

    # Save the map and display
    mapper.save_map()
    mapper.show_map()
    scout_data.close()
