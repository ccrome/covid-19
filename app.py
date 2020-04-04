import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input
import covid_19
import pandas as pd
import plotly.graph_objects as go
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess


def plot_county(cases_by_county, county_state, num_days, min_cases=10, lineweight=1, percent=False):
    cases = cases_by_county[county_state]["cases"]
    deaths = cases_by_county[county_state]["deaths"]
    dates = cases_by_county[county_state]["date"]
    cases, new_cases, dates = covid_19.compute_new_cases(cases, dates, num_days)
    county, state = county_state
    if percent:
        x = dates
        y = new_cases/cases * 100
    else:
        x = cases
        y = new_cases
    label=f"{county}, {state} ({int(cases[-1])}, {int(deaths[-1])})"
    return x, y, label

def plot_state(states, state, num_days, min_cases=10, lineweight=1, percent=False):
    dates = states[state]["date"]
    deaths = states[state]["deaths"]
    cases = states[state]["cases"]
    cases, new_cases, dates = covid_19.compute_new_cases(cases, dates, num_days)
    if percent:
        x = dates
        y = new_cases/cases * 100
    else:
        x = cases
        y = new_cases
    label=f"{state} ({cases[-1]}, {deaths[-1]})"
    return x, y, label
    

def arrange_counties(sorted_counties, my_counties, top_n):
    top_counties = sorted_counties[:top_n]
    bottom_counties = sorted_counties[top_n:]
    for i, my_county in enumerate(my_counties):
        if my_county not in sorted_counties:
            print(f"Huh, {my_county} doesn't exist.")
        if my_county in sorted_counties:
            if my_county in sorted_counties and my_county in bottom_counties:
                top_counties.append(my_county)
                bottom_counties.remove(my_county)
            top_n += 1
    top_counties.extend(bottom_counties)
    sorted_counties = top_counties
    return sorted_counties, top_n

def update_county_plot(percent, cases_by_county):
    top_n = 10
    n = 200
    sorted_counties = covid_19.counties_by_num_cases(cases_by_county)
    
    my_counties = [
        ("Santa Clara", "California"),
        ("Marin", "California"),
    ]
    sorted_counties, top_n = arrange_counties(sorted_counties, my_counties, top_n)
    sorted_counties = sorted_counties[:n]
    fig = go.Figure()
    for i, county_state in enumerate(sorted_counties[:n]):
        try:
            lw = 1
            if county_state in my_counties:
                lw = 4
            x, y, label = plot_county(cases_by_county, county_state, num_days = 5, min_cases=300, lineweight=lw, percent=percent)
        except covid_19.NotEnoughCases:
            continue
        visible=True
        if i >= top_n:
            visible='legendonly'
        fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name=label, visible=visible, line=dict(width=lw)))
    if percent:
        fig.update_layout(title="US Counties",
                          xaxis_title="Date",
                          yaxis_title="Growth rate per day (%)",)
    else:
        fig.update_layout(title="US Counties",
                          xaxis_title="Total Number of Cases",
                          yaxis_title="New Cases per day, 5 day average",
                          xaxis_type='log',
                          yaxis_type='log',)
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

def del_and_clone():
    subprocess.call(["rm", "-rf", "covid-19-data"])
    subprocess.call(["git", "clone", "https://github.com/nytimes/covid-19-data.git"])

def pull():
    global cases_by_state, cases_by_county
    subprocess.call(["git", "pull"], cwd="covid-19-data")
    df_county = pd.read_csv("covid-19-data/us-counties.csv")
    df_state = pd.read_csv("covid-19-data/us-states.csv")
    cases_by_state = covid_19.df_to_dict_state(df_state)
    cases_by_county = covid_19.df_to_dict_county(df_county)
    
def update_data():
    try:
        pull()
    except:
        del_and_clone()
        pull()
    
def serve_layout():
    layout = html.Div(
        [html.Div(className="row",children=header),
         html.Div(className="row",children=sub_header),
         html.Div(className="row",children=main_area)])
    return layout

app.layout = serve_layout

del_and_clone()
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_data, trigger="interval", seconds=3600) # update the data once an hour
scheduler.start()

@app.callback(
    [Output('county-plot', 'figure'), Output('state-plot', 'figure')],
    [Input('pct-checkbox', 'value'),]
    )
def update_plots(percent):
    global cases_by_county, cases_by_state
    county_plot = update_county_plot(percent, cases_by_county)
    state_plot = update_state_plot(percent, cases_by_state)
    return county_plot, state_plot

server=app.server

if __name__ == '__main__':
    app.run_server(debug=True)
