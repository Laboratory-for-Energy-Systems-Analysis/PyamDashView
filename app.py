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

# Load YAML files
def load_yaml(filename):
    with open(filename, "r", encoding="utf-8") as stream:
        return yaml.safe_load(stream)

units = load_yaml("data/units.yaml")
ssp_descriptions = load_yaml("data/ssp_descriptions.yaml")
rcp_descriptions = load_yaml("data/rcp_descriptions.yaml")

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
load_figure_template("LUX")
server = app.server  # for deployment

# Layout
app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [html.A("Contact", href="mailto:romain.sacchi@psi.ch", target="_blank")],
                            style={"width": "33%", "display": "inline-block", "fontSize": "12px", "textAlign": "left"},
                        ),
                        html.Div(
                            [html.A("Documentation", href="https://premise.readthedocs.io", target="_blank")],
                            style={"width": "33%", "display": "inline-block", "fontSize": "12px", "textAlign": "center"},
                        ),
                        html.Div(
                            [html.A("Link to premise github repo", href="https://github.com/polca/premise", target="_blank")],
                            style={"width": "33%", "display": "inline-block", "fontSize": "12px", "textAlign": "right"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                html.H1("premise scenario explorer", style={"marginBottom": "20px"}),

                html.Div(
                    [
                        html.Label("Select Premise Version:"),
                        dcc.Dropdown(
                            id="dataset-version-dropdown",
                            options=[
                                {"label": "Version 2.3.0 (dev1)", "value": "structured_data (2, 3, 0, 'dev1').csv"},
                                {"label": "Version 2.2.0", "value": "structured_data.csv"},
                            ],
                            value="structured_data (2, 3, 0, 'dev1').csv",  # <- default is now 2.3.0
                            clearable=False,
                        ),
                    ],
                    style={"width": "32%", "display": "inline-block", "marginBottom": "20px", "marginRight": "1%"},
                ),

                html.Div(
                    [
                        html.Div(
                            [html.Label("Select Model-Scenario Combinations:"), dcc.Dropdown(id="model-scenario-dropdown", multi=True)],
                            style={"width": "32%", "display": "inline-block", "marginRight": "1%"},
                        ),
                        html.Div(
                            [html.Label("Select Sector:"), dcc.Dropdown(id="sector-dropdown")],
                            style={"width": "32%", "display": "inline-block", "marginRight": "1%"},
                        ),
                        html.Div(
                            [html.Label("Select Regions:"), dcc.Dropdown(id="region-dropdown", value=["World"], multi=True)],
                            style={"width": "32%", "display": "inline-block"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),

                html.Div(id="expl-text-box", style={"fontSize": "16px", "textAlign": "center", "marginBottom": "20px"}),
            ],
            style={"background": "#e9e9e9", "padding": "20px", "borderRadius": "5px", "marginBottom": "20px"},
        ),

        dcc.Store(id="data-store"),
        html.Div(id="graphs-container"),
    ]
)

# Set up a color map using the default dataset
default_df = pd.read_csv("data/structured_data.csv")
unique_variables = default_df["variables"].unique()
colors = px.colors.qualitative.Plotly
color_map = {var: colors[i % len(colors)] for i, var in enumerate(sorted(unique_variables))}

# Load dataset into dcc.Store
@app.callback(
    Output("data-store", "data"),
    Input("dataset-version-dropdown", "value"),
)
def load_dataset(selected_file):
    print(f"[CALLBACK] load_dataset triggered by dataset: {selected_file}")
    column_dtypes = {
        "region": "category",
        "variables": "category",
        "year": "int32",  # Smaller than int64
        "val": "float32",  # Lighter than float64
        "sector": "category",  # Was str → now category
        "model": "category",  # Was str → now category
        "scenario": "category",  # Was str → now category
        "powertrain": "category",  # Optional, depends on usage
        "size": "category",  # Already correct
    }

    df = pd.read_csv(f"data/{selected_file}", dtype=column_dtypes)
    return df.to_dict("records")

# Update model-scenario and sector dropdowns when dataset changes
@app.callback(
    Output("model-scenario-dropdown", "options"),
    Output("model-scenario-dropdown", "value"),
    Output("sector-dropdown", "options"),
    Output("sector-dropdown", "value"),
    Input("data-store", "data"),
    State("model-scenario-dropdown", "value"),
    State("sector-dropdown", "value"),
)
def update_dropdowns(data, current_model_scenario_value, current_sector_value):
    print("[CALLBACK] update_dropdowns triggered")
    if not data:
        return no_update, no_update, no_update, no_update

    df = pd.DataFrame(data)

    model_scenarios = df.drop_duplicates(subset=["model", "scenario"])[["model", "scenario"]]
    model_scenarios["combined"] = model_scenarios["model"] + " - " + model_scenarios["scenario"]
    model_scenario_options = model_scenarios["combined"].tolist()

    sectors = sorted(df["sector"].unique())
    sectors = [
        "GMST increase", "Carbon Dioxide emissions", "Population", "Gross Domestic Product"
    ] + [s for s in sectors if s not in ("GMST increase", "Carbon Dioxide emissions", "Population", "Gross Domestic Product")]

    new_model_value = (
        [model_scenario_options[0]]
        if not current_model_scenario_value or any(v not in model_scenario_options for v in current_model_scenario_value)
        else no_update
    )

    new_sector_value = (
        sectors[0] if current_sector_value not in sectors else no_update
    )

    return (
        [{"label": s, "value": s} for s in model_scenario_options],
        new_model_value,
        [{"label": s, "value": s} for s in sectors],
        new_sector_value,
    )

# Update regions dropdown based on selected sector
@app.callback(
    Output("region-dropdown", "options"),
    Input("sector-dropdown", "value"),
    State("data-store", "data"),
)
def update_region_options(selected_sector, data):
    print(f"[CALLBACK] update_region_options triggered for sector: {selected_sector}")
    if not data:
        return []
    df = pd.DataFrame(data)
    regions = df[df["sector"] == selected_sector]["region"].unique()
    return [{"label": r, "value": r} for r in sorted(regions)]

# Main callback to generate graphs
@app.callback(
    Output("graphs-container", "children"),
    Input("model-scenario-dropdown", "value"),
    Input("sector-dropdown", "value"),
    Input("region-dropdown", "value"),
    State("data-store", "data"),
    prevent_initial_call=True,
)
def update_graphs(selected_combinations, selected_sector, selected_regions, data):
    print(f"[CALLBACK] update_graphs triggered with: {selected_combinations=}, {selected_sector=}, {selected_regions=}")
    if not data or not selected_combinations or not selected_regions:
        raise PreventUpdate
    df = pd.DataFrame(data)
    df = pd.DataFrame(data)
    working_df = df[df["sector"] == selected_sector].copy()  # <- IMPORTANT

    # Create a fresh working copy to modify
    working_df = working_df.copy()

    for combo in selected_combinations:
        model, scenario = combo.split(" - ")
        combo_df = working_df[
            (working_df["model"] == model) & (working_df["scenario"] == scenario)
            ]

        for year in combo_df["year"].unique():
            year_df = combo_df[combo_df["year"] == year]
            world_df = year_df[year_df["region"] == "World"]

            if world_df.empty or world_df["val"].sum() == 0:
                summed_val = year_df[year_df["region"] != "World"]["val"].sum()

                if not world_df.empty:
                    working_df.loc[
                        (working_df["model"] == model)
                        & (working_df["scenario"] == scenario)
                        & (working_df["year"] == year)
                        & (working_df["region"] == "World"),
                        "val",
                    ] = summed_val
                else:
                    new_row = {
                        "region": "World",
                        "variables": year_df["variables"].iloc[0] if "variables" in year_df.columns else None,
                        "year": year,
                        "val": summed_val,
                        "sector": selected_sector,
                        "model": model,
                        "scenario": scenario,
                    }
                    working_df = pd.concat([working_df, pd.DataFrame([new_row])])

    working_df = working_df[working_df["region"].isin(selected_regions)]

    graph_pairs = []
    temp_graphs = []

    for combo in selected_combinations:
        model, scenario = combo.split(" - ")
        SSP, RCP = scenario.split("-")
        temp_df = working_df[
            (working_df["model"] == model) & (working_df["scenario"] == scenario)
        ]
        if "variables" in temp_df.columns:
            for variable in temp_df["variables"].unique():
                if temp_df[temp_df["variables"] == variable]["val"].sum() == 0:
                    temp_df = temp_df[temp_df["variables"] != variable]
        temp_df = temp_df.sort_values(by="year")

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

        ssp_name = ssp_descriptions.get(SSP, {}).get("name", "")
        ssp_desc = ssp_descriptions.get(SSP, {}).get("description", "")
        rcp_name = rcp_descriptions.get(RCP, {}).get("name", "")
        rcp_desc = rcp_descriptions.get(RCP, {}).get("description", "")

        scenario_details = html.Div(
            [
                html.H3(ssp_name, style={"fontSize": "10px", "marginLeft": "20px"}),
                html.P(ssp_desc, style={"fontSize": "8px", "marginLeft": "20px"}),
                html.H3(rcp_name, style={"fontSize": "10px", "marginLeft": "20px"}),
                html.P(rcp_desc, style={"fontSize": "8px", "marginLeft": "20px"}),
                dcc.Graph(
                    id=f"graph-{model}-{scenario}",
                    figure=fig,
                    config={"displayModeBar": False},
                    clear_on_unhover=False,
                    style={"height": "400px"},  # <- this prevents dynamic resizing
                ),
            ],
            style={"width": "50%", "display": "inline-block"},
        )

        yaxis_label = units.get(selected_sector, {}).get("label", "Value")
        fig.update_layout(yaxis_title=yaxis_label)

        temp_graphs.append(scenario_details)
        if len(temp_graphs) == 2:
            graph_pairs.append(html.Div(temp_graphs, style={"display": "flex"}))
            temp_graphs = []

    if temp_graphs:
        graph_pairs.append(html.Div(temp_graphs, style={"display": "flex"}))

    expl_text = units.get(selected_sector, {}).get("expl_text", "")
    expl_text_box = html.Div(
        [html.P(expl_text, style={"fontSize": "16px", "textAlign": "center", "marginBottom": "20px"})]
    )

    return [expl_text_box] + graph_pairs

# Run the app
if __name__ == "__main__":
    app.run(debug=True)
