import dash
import dash_core_components as dcc
import dash_html_components as html

from src.base import Base

class Dashboard(Base):
    def __init__(self):
        self.app = dash.Dash(__name__,
                             external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'])

        self.app.layout = html.Div([
            html.H1('Devon Scouts Uptake and IMD Decile Map'),
            html.Iframe(id='map', srcDoc=open("Example Output/pcon_imd_uptake_map.html", 'r').read(), width="100%", height="600")
        ])

        self.input_layout = html.Div([
            dcc.Upload(
                    id='upload-scout-data',
                    children=html.Div([
                        'Add Census with ONS Postcode Directory',
                        html.A('Select Files')
                    ]))
        ])

    def run(self):
        self.app.run_server(debug=False)
