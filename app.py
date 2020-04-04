import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input
import covid_19
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import git

from git import Repo
try:
    git.Git(".").clone("https://github.com/nytimes/covid-19-data.git")
except git.exc.GitCommandError:
    pass

repo = Repo("covid-19-data")
origin=repo.remotes.origin

def plot_county(cases_by_county, county_state, num_days, min_cases=10, lineweight=1, percent=False):
    cases = cases_by_county[county_state]["cases"]
    dates = cases_by_county[county_state]["date"]
    cases, new_cases, dates = covid_19.compute_new_cases(cases, dates, num_days)
    county, state = county_state
    if percent:
        x = dates
        y = new_cases/cases * 100
    else:
        x = cases
        y = new_cases
    label=f"{county}, {state}"
    return x, y, label

def plot_state(states, state, num_days, min_cases=10, lineweight=1, percent=False):
    dates = states[state]["date"]
    cases = states[state]["cases"]
    cases, new_cases, dates = covid_19.compute_new_cases(cases, dates, num_days)
    if percent:
        x = dates
        y = new_cases/cases * 100
    else:
        x = cases
        y = new_cases
    label=f"{state}"
    return x, y, label
    

def update_county_plot(percent, cases_by_county):
    top_n = 10
    n = 200
    sorted_counties = covid_19.counties_by_num_cases(cases_by_county)
    top_counties = sorted_counties[:top_n]
    bottom_counties = sorted(sorted_counties[top_n:n], key=lambda x: f"{x[0], x[1]}")
    top_counties.extend(bottom_counties)
    sorted_counties = top_counties
    fig = go.Figure()
    for i, county_state in enumerate(sorted_counties[:n]):
        try:
            x, y, label = plot_county(cases_by_county, county_state, num_days = 5, min_cases=300, lineweight=2, percent=percent)
        except covid_19.NotEnoughCases:
            continue
        visible=True
        if i >= top_n:
            visible='legendonly'
        fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name=label, visible=visible))
    if percent:
        fig.update_layout(title="US Counties",
                          xaxis_title="Date",
                          yaxis_title="Growth rate per day (%)",
                          
        )
    else:
        fig.update_layout(title="US Counties",
                          xaxis_title="Total Number of Cases",
                          yaxis_title="New Cases per day, 5 day average",
                          xaxis_type='log',
                          yaxis_type='log',
                          
        )
    return fig

def update_state_plot(percent, cases_by_state):
    top_n = 10
    states = covid_19.states_by_num_cases(cases_by_state)
    top_states = states[:top_n]
    the_rest = states[top_n:]
    top_states.extend(sorted(the_rest))
    states = top_states
    fig = go.Figure()
    for i, state in enumerate(states):
        try:
            x, y, label = plot_state(cases_by_state, state, num_days = 5, lineweight=1, percent=percent)
        except covid_19.NotEnoughCases:
            continue
        visible=True
        if i >= top_n:
            visible='legendonly'
        fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name=label, visible=visible))
    if percent:
        fig.update_layout(title="US States",
                          xaxis_title="Date",
                          yaxis_title="Growth rate per day (%)",
        )
    else:
        fig.update_layout(title="US States",
                          xaxis_title="Total Number of Cases",
                          yaxis_title="New Cases per day, 5 day average",
                          xaxis_type='log',
                          yaxis_type='log',
                          
        )
    return fig

external_stylesheets = [
    'https://codepen.io/chriddyp/pen/bWLwgP.css',
#    'https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css',
]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

colors = {
    'background': '#111111',
    'text': '#7FDBFF'
}

header = html.H1(
    children=['COVID-19 By County/State'],
    style={
        'textAlign': 'center',
        'color': colors['text']
    },
)

sub_header = html.Div(
    children='''Covid-19 data from the NYT''',
    style={'textAlign': 'center', 'color': colors['text']},
)

county_plot = dcc.Graph(
    id='county-plot',
)
state_plot = dcc.Graph(
    id='state-plot',
#    figure=update_state_plot(False),
)

plot_pane=html.Div(
    children=[
        html.Div(county_plot),
        html.Div(state_plot),
    ]
)

control_pane = html.Div(dcc.Checklist(id='pct-checkbox', options=[{'label' : "Plots as Percent", 'value' : 'PCT'}], value=[]))
main_area=html.Div([control_pane, plot_pane, ])

cases_by_county = None
cases_by_state = None
def serve_layout():
    global cases_by_county, cases_by_state
    origin.pull()   # Check for updates at page load.
    df_county = pd.read_csv("covid-19-data/us-counties.csv")
    df_state = pd.read_csv("covid-19-data/us-states.csv")
    cases_by_state = covid_19.df_to_dict_state(df_state)
    cases_by_county = covid_19.df_to_dict_county(df_county)
    
    layout = html.Div(
        [html.Div(className="row",children=header),
         html.Div(className="row",children=sub_header),
         html.Div(className="row",children=main_area)])
    return layout

app.layout = serve_layout

@app.callback(
    [Output('county-plot', 'figure'), Output('state-plot', 'figure')],
    [Input('pct-checkbox', 'value'),]
    )
def update_plots(percent):
    county_plot = update_county_plot(percent, cases_by_county)
    state_plot = update_state_plot(percent, cases_by_state)
    return county_plot, state_plot

server=app.server
if __name__ == '__main__':
    app.run_server(debug=True)
