# Imports
import dash
from dash import dcc, html, no_update
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import load_figure_template
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.express as px
import pandas as pd
import yaml
import time
from flask_caching import Cache

# Load YAML files
with open("data/units.yaml", "r", encoding="utf-8") as f:
    units = yaml.safe_load(f)
with open("data/ssp_descriptions.yaml", "r", encoding="utf-8") as f:
    ssp_descriptions = yaml.safe_load(f)
with open("data/rcp_descriptions.yaml", "r", encoding="utf-8") as f:
    rcp_descriptions = yaml.safe_load(f)

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
load_figure_template("LUX")
server = app.server

# Set up caching
cache = Cache(server, config={"CACHE_TYPE": "simple"})

# Load CSV with optimized dtypes
column_dtypes = {
    "region": "category",
    "variables": "category",
    "year": "int32",
    "val": "float32",
    "sector": "category",
    "model": "category",
    "scenario": "category",
    "powertrain": "category",
    "size": "category",
}

@cache.memoize(timeout=600)
def get_dataset(file):
    print(f"[LOAD] Reading {file}")
    return pd.read_csv(f"data/{file}", dtype=column_dtypes)

# Color map
default_df = get_dataset("structured_data.csv")
unique_variables = default_df["variables"].unique()
colors = px.colors.qualitative.Plotly
color_map = {var: colors[i % len(colors)] for i, var in enumerate(sorted(unique_variables))}

# Layout
app.layout = html.Div([
    html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.A("Contact", href="mailto:romain.sacchi@psi.ch", target="_blank")
                ], style={"width": "33%", "display": "inline-block", "fontSize": "12px", "textAlign": "left"}),
                html.Div([
                    html.A("Documentation", href="https://premise.readthedocs.io", target="_blank")
                ], style={"width": "33%", "display": "inline-block", "fontSize": "12px", "textAlign": "center"}),
                html.Div([
                    html.A("Link to premise github repo", href="https://github.com/polca/premise", target="_blank")
                ], style={"width": "33%", "display": "inline-block", "fontSize": "12px", "textAlign": "right"}),
            ], style={"marginBottom": "10px"}),

            html.H1("premise scenario explorer", style={"marginBottom": "20px"}),

            html.Div([
                html.Label("Select Premise Version:"),
                dcc.Dropdown(
                    id="dataset-version-dropdown",
                    options=[
                        {"label": "Version 2.3.0 (dev1)", "value": "structured_data (2, 3, 0, 'dev1').csv"},
                        {"label": "Version 2.2.0", "value": "structured_data.csv"},
                    ],
                    value="structured_data (2, 3, 0, 'dev1').csv",
                    clearable=False,
                )
            ], style={"width": "32%", "display": "inline-block", "marginBottom": "20px", "marginRight": "1%"}),

            html.Div([
                html.Div([
                    html.Label("Select Model-Scenario Combinations:"),
                    dcc.Dropdown(id="model-scenario-dropdown", multi=True)
                ], style={"width": "32%", "display": "inline-block", "marginRight": "1%"}),

                html.Div([
                    html.Label("Select Sector:"),
                    dcc.Dropdown(id="sector-dropdown")
                ], style={"width": "32%", "display": "inline-block", "marginRight": "1%"}),

                html.Div([
                    html.Label("Select Regions:"),
                    dcc.Dropdown(id="region-dropdown", value=["World"], multi=True)
                ], style={"width": "32%", "display": "inline-block"}),
            ], style={"marginBottom": "20px"}),

            html.Div(id="expl-text-box", style={"fontSize": "16px", "textAlign": "center", "marginBottom": "20px"}),
        ])
    ], style={"background": "#e9e9e9", "padding": "20px", "borderRadius": "5px", "marginBottom": "20px"}),

    dcc.Store(id="data-store"),
    html.Div(id="graphs-container")
])

# Callback: update dropdowns
@app.callback(
    Output("model-scenario-dropdown", "options"),
    Output("model-scenario-dropdown", "value"),
    Output("sector-dropdown", "options"),
    Output("sector-dropdown", "value"),
    Input("dataset-version-dropdown", "value"),
)
def update_dropdowns(selected_file):
    df = get_dataset(selected_file)
    model_scenarios = df.drop_duplicates(subset=["model", "scenario"])
    model_scenarios["combined"] = model_scenarios["model"].astype(str) + " - " + model_scenarios["scenario"].astype(str)
    model_options = model_scenarios["combined"].tolist()

    sectors = sorted(df["sector"].unique())
    sectors = [
        "GMST increase", "Carbon Dioxide emissions", "Population", "Gross Domestic Product"
    ] + [s for s in sectors if s not in ("GMST increase", "Carbon Dioxide emissions", "Population", "Gross Domestic Product")]

    return (
        [{"label": s, "value": s} for s in model_options],
        [model_options[0]],
        [{"label": s, "value": s} for s in sectors],
        sectors[0],
    )

# Callback: update regions
@app.callback(
    Output("region-dropdown", "options"),
    Input("sector-dropdown", "value"),
    State("dataset-version-dropdown", "value"),
)
def update_region_options(selected_sector, selected_file):
    df = get_dataset(selected_file)
    regions = df[df["sector"] == selected_sector]["region"].unique()
    return [{"label": r, "value": r} for r in sorted(regions)]

# Callback: generate graphs
@app.callback(
    Output("graphs-container", "children"),
    Input("model-scenario-dropdown", "value"),
    Input("sector-dropdown", "value"),
    Input("region-dropdown", "value"),
    State("dataset-version-dropdown", "value"),
)
def update_graphs(selected_combinations, selected_sector, selected_regions, selected_file):
    if not selected_combinations or not selected_regions:
        raise PreventUpdate

    df = get_dataset(selected_file)
    df = df[df["sector"] == selected_sector]

    output = []
    temp_row = []

    for combo in selected_combinations:
        model, scenario = combo.split(" - ")
        temp_df = df[(df["model"] == model) & (df["scenario"] == scenario)]

        for year in temp_df["year"].unique():
            year_df = temp_df[temp_df["year"] == year]
            world_df = year_df[year_df["region"] == "World"]
            if world_df.empty or world_df["val"].sum() == 0:
                total_val = year_df[year_df["region"] != "World"]["val"].sum()
                if not world_df.empty:
                    df.loc[(df["model"] == model) & (df["scenario"] == scenario) & (df["year"] == year) & (df["region"] == "World"), "val"] = total_val
                else:
                    new_row = {
                        "region": "World",
                        "variables": year_df["variables"].iloc[0],
                        "year": year,
                        "val": total_val,
                        "sector": selected_sector,
                        "model": model,
                        "scenario": scenario,
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])])

        temp_df = df[(df["model"] == model) & (df["scenario"] == scenario) & (df["region"].isin(selected_regions))]
        temp_df = temp_df[temp_df["val"] > 0].sort_values("year")

        fig_func = px.line if "efficiency" in selected_sector.lower() else px.area
        fig = fig_func(
            temp_df,
            x="year",
            y="val",
            color="variables",
            color_discrete_map=color_map,
            line_group="region",
            facet_col="region",
            labels={"val": "Value", "year": "Year", "variables": "Variables", "region": "Region"},
            title=f"Model: {model} | Scenario: {scenario}",
            height=350,
        )

        yaxis_label = units.get(selected_sector, {}).get("label", "Value")
        fig.update_layout(yaxis_title=yaxis_label)

        scenario_details = html.Div([
            html.H3(ssp_descriptions.get(scenario.split("-")[0], {}).get("name", ""), style={"fontSize": "10px"}),
            html.P(ssp_descriptions.get(scenario.split("-")[0], {}).get("description", ""), style={"fontSize": "8px"}),
            html.H3(rcp_descriptions.get(scenario.split("-")[1], {}).get("name", ""), style={"fontSize": "10px"}),
            html.P(rcp_descriptions.get(scenario.split("-")[1], {}).get("description", ""), style={"fontSize": "8px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": "400px"})
        ], style={"width": "50%", "display": "inline-block"})

        temp_row.append(scenario_details)
        if len(temp_row) == 2:
            output.append(html.Div(temp_row, style={"display": "flex"}))
            temp_row = []

    if temp_row:
        output.append(html.Div(temp_row, style={"display": "flex"}))

    expl_text = units.get(selected_sector, {}).get("expl_text", "")
    output.insert(0, html.Div(html.P(expl_text, style={"fontSize": "16px"})))
    return output

if __name__ == "__main__":
    app.run(debug=True)
