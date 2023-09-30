# Imports
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import yaml

# Load YAML files
def load_yaml(filename):
    with open(filename, "r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)

units = load_yaml("data/units.yaml")
ssp_descriptions = load_yaml("data/ssp_descriptions.yaml")
rcp_descriptions = load_yaml("data/rcp_descriptions.yaml")

# Define column data types
column_dtypes = {
    'region': 'category',
    'variables': 'category',
    'year': 'int64',
    'val': 'float64',
    'sector': 'str',
    'model': 'str',
    'scenario': 'str',
    'powertrain': 'str',
    'construction_year': 'str',
    'size': 'category'
}

# Load the CSV with specified data types
df = pd.read_csv("data/structured_data.csv", dtype=column_dtypes)

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
load_figure_template('LUX')  # Load the Lux template

# Reference the underlying flask app (Used by gunicorn webserver in Heroku production deployment)
server = app.server

# Prepare data for dropdowns
sectors = sorted(df['sector'].unique())
sectors = [x for x in ["Global mean surface temperature increase", "Carbon dioxide emissions",
                      "Population", "Gross domestic product"] if x in sectors] + sectors

model_scenarios = df.drop_duplicates(subset=['model', 'scenario'])[['model', 'scenario']]
model_scenarios['combined'] = model_scenarios['model'] + " - " + model_scenarios['scenario']
model_scenario_options = model_scenarios['combined'].tolist()

# Define the app layout
app.layout = html.Div([
    # Header Section
    html.Div([
        # Links Row
        html.Div([
            html.Div([
                html.A("Contact", href="mailto:romain.sacchi@psi.ch", target="_blank")
            ], style={'width': '33%', 'display': 'inline-block', 'fontSize': '12px', 'textAlign': 'left'}),
            html.Div([
                html.A("Documentation", href="https://premise.readthedocs.io", target="_blank")
            ], style={'width': '33%', 'display': 'inline-block', 'fontSize': '12px', 'textAlign': 'center'}),
            html.Div([
                html.A("Link to premise github repo", href="https://github.com/polca/premise", target="_blank")
            ], style={'width': '33%', 'display': 'inline-block', 'fontSize': '12px', 'textAlign': 'right'}),
        ], style={"marginBottom": "10px"}),

        # Title
        html.H1("premise scenario explorer", style={"marginBottom": "20px"}),

        # Filters Row
        html.Div([
            # Model-Scenario Dropdown
            html.Div([
                html.Label("Select Model-Scenario Combinations:"),
                dcc.Dropdown(
                    id='model-scenario-dropdown',
                    options=[{'label': combo, 'value': combo} for combo in model_scenario_options],
                    value=[model_scenario_options[0]],  # Default value
                    multi=True
                ),
            ], style={'width': '32%', 'display': 'inline-block', 'marginRight': '1%'}),
            # Sector Dropdown
            html.Div([
                html.Label("Select Sector:"),
                dcc.Dropdown(
                    id='sector-dropdown',
                    options=[{'label': sector, 'value': sector} for sector in sectors],
                    value=sectors[0]
                ),
            ], style={'width': '32%', 'display': 'inline-block', 'marginRight': '1%'}),
            # Region Dropdown
            html.Div([
                html.Label("Select Regions:"),
                dcc.Dropdown(
                    id='region-dropdown',
                    value=['World'],
                    multi=True
                ),
            ], style={'width': '32%', 'display': 'inline-block'}),
        ], style={"marginBottom": "20px"}),

        # Explanatory Text Box
        html.Div(id='expl-text-box', style={"fontSize": "16px", "textAlign": "center", "marginBottom": "20px"})
    ], style={'background': '#e9e9e9', 'padding': '20px', 'borderRadius': '5px', 'marginBottom': '20px'}),

    # Graphs Container
    html.Div(id='graphs-container')
])

# Create a consistent color map for the unique variables in the dataset
unique_variables = df['variables'].unique()
colors = px.colors.qualitative.Plotly
color_map = {var: colors[i % len(colors)] for i, var in enumerate(unique_variables)}

# Callback to dynamically update region-dropdown options based on the selected sector
@app.callback(
    Output('region-dropdown', 'options'),
    [Input('sector-dropdown', 'value')]
)
def update_region_options(selected_sector):
    available_regions = df[df['sector'] == selected_sector]['region'].unique()
    return [{'label': region, 'value': region} for region in sorted(available_regions)]

# Callback to update graphs and explanatory text based on selected parameters
@app.callback(
    Output('graphs-container', 'children'),
    [
        Input('model-scenario-dropdown', 'value'),
        Input('sector-dropdown', 'value'),
        Input('region-dropdown', 'value')
    ]
)
def update_graphs(selected_combinations, selected_sector, selected_regions):
    # Filter the data based on the selected sector
    filtered_df = df[df['sector'] == selected_sector]

    # Handle "World" data that sums to zero
    for combo in selected_combinations:
        model, scenario = combo.split(" - ")
        combo_df = filtered_df[(filtered_df['model'] == model) & (filtered_df['scenario'] == scenario)]

        for year in combo_df['year'].unique():
            year_df = combo_df[combo_df['year'] == year]
            world_val = year_df[year_df['region'] == 'World']['val'].sum()
            if world_val == 0 or year_df[year_df['region'] == 'World'].empty:
                summed_val = year_df[year_df['region'] != 'World']['val'].sum()
                filtered_df.loc[(filtered_df['model'] == model) &
                                (filtered_df['scenario'] == scenario) &
                                (filtered_df['year'] == year) &
                                (filtered_df['region'] == 'World'), 'val'] = summed_val

                if year_df[year_df['region'] == 'World'].empty:
                    new_row = {
                        'region': 'World',
                        'variables': year_df['variables'].iloc[0] if 'variables' in year_df.columns else None,
                        'powertrain': year_df['powertrain'].iloc[0] if 'powertrain' in year_df.columns else None,
                        'size': year_df['size'].iloc[0] if 'size' in year_df.columns else None,
                        'construction_year': year_df['construction_year'].iloc[
                            0] if 'construction_year' in year_df.columns else None,
                        'year': year,
                        'val': summed_val,
                        'sector': selected_sector,
                        'model': model,
                        'scenario': scenario,
                    }
                    # Filter out None values
                    new_row = {k: v for k, v in new_row.items() if v is not None}
                    filtered_df = filtered_df.append(new_row, ignore_index=True)

    # Filter based on selected regions
    filtered_df = filtered_df[filtered_df['region'].isin(selected_regions)]

    # List to hold all graph pairs
    graph_pairs = []

    # Temporary list to hold individual graphs
    temp_graphs = []

    # Create a graph for each selected model-scenario combination
    # Create a graph for each selected model-scenario combination
    for combo in selected_combinations:
        model, scenario = combo.split(" - ")
        SSP, RCP = scenario.split("-")

        temp_df = filtered_df[(filtered_df['model'] == model) & (filtered_df['scenario'] == scenario)]

        # Default color column
        color_column = "variables"

        # If "Transport" is in the selected sector, aggregate over 'size' and 'construction_year'
        if "Transport" in selected_sector:
            color_column = "powertrain"

        # Extract the name and description of the scenario
        ssp_name = ssp_descriptions.get(SSP, {}).get('name', '')
        ssp_desc = ssp_descriptions.get(SSP, {}).get('description', '')
        rcp_name = rcp_descriptions.get(RCP, {}).get('name', '')
        rcp_desc = rcp_descriptions.get(RCP, {}).get('description', '')

        # Remove variables that don't have any non-zero values for any year
        if "variables" in temp_df.columns:
            for variable in temp_df['variables'].unique():
                if temp_df[temp_df['variables'] == variable]['val'].sum() == 0:
                    temp_df = temp_df[temp_df['variables'] != variable]

        # Sort the data by year before plotting
        temp_df = temp_df.sort_values(by='year')

        # Ensuring the necessary column is present before plotting
        if color_column not in temp_df.columns:
            continue

        if "Transport" in selected_sector:
            fig = px.area(temp_df, x="year", y="val", color=color_column,
                          color_discrete_map=color_map,
                          line_group="region", facet_col="region",
                          labels={"val": "Value", "year": "Year", color_column: color_column.capitalize(),
                                  "region": "Region"},
                          title=f"Model: {model} | Scenario: {scenario}",
                          height=350)
        elif "efficiency" in selected_sector.lower():
            fig = px.line(temp_df, x="year", y="val", color=color_column,
                          color_discrete_map=color_map,
                          line_group="region", facet_col="region",
                          labels={"val": "Value", "year": "Year", color_column: color_column.capitalize(),
                                  "region": "Region"},
                          title=f"Model: {model} | Scenario: {scenario}",
                          height=350)
        else:
            fig = px.area(temp_df, x="year", y="val", color=color_column,
                          color_discrete_map=color_map,
                          line_group="region", facet_col="region",
                          labels={"val": "Value", "year": "Year", color_column: color_column.capitalize(),
                                  "region": "Region"},
                          title=f"Model: {model} | Scenario: {scenario}",
                          height=350)


        # Display the name and description of the scenario above each chart
        # Display the name and description of the scenario above each chart
        scenario_details = html.Div([
            html.H3(ssp_name, style={"fontSize": "10px", "textAlign": "left", "marginLeft": "20px", "marginRight": "20px"}),
            html.P(ssp_desc, style={"fontSize": "8px", "textAlign": "left", "marginBottom": "20px", "marginLeft": "20px", "marginRight": "20px"}),
            html.H3(rcp_name, style={"fontSize": "10px", "textAlign": "left", "marginLeft": "20px", "marginRight": "20px"}),
            html.P(rcp_desc, style={"fontSize": "8px", "textAlign": "left", "marginBottom": "20px", "marginLeft": "20px", "marginRight": "20px"}),
            dcc.Graph(figure=fig)
        ], style={'width': '50%',
                  'display': 'inline-block'})  # Set width to 50% and inline-block for side-by-side display


        # Check if the selected sector has a custom label in the YAML content
        yaxis_label = units.get(selected_sector, {}).get('label', 'Value')

        # Update the y-axis label
        fig.update_layout(yaxis_title=yaxis_label)

        # Append the scenario details to the temporary list
        temp_graphs.append(scenario_details)

        # When two graphs are in temp_graphs, append them as a pair to graph_pairs
        if len(temp_graphs) == 2:
            graph_pairs.append(html.Div(temp_graphs, style={'display': 'flex'}))
            temp_graphs = []

    # If there's any remaining graph in temp_graphs, append it to graph_pairs
    if temp_graphs:
        graph_pairs.append(html.Div(temp_graphs, style={'display': 'flex'}))

    # Extract the expl_text for the selected sector
    expl_text = units.get(selected_sector, {}).get('expl_text', '')

    # Create an explanatory text box (using HTML components) to display the expl_text above the charts
    expl_text_box = html.Div([
        html.P(expl_text, style={"fontSize": "16px", "textAlign": "center", "marginBottom": "20px"})
    ])

    # Return both the explanatory text box and the graph pairs
    return [expl_text_box] + graph_pairs


# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)
