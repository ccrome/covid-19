import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Output, Input, State
import covid_19
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess
import random
import time
import threading
import unemployment
import json
import numpy as np
import death

from flask_caching import Cache

def state_to_abbr(state):
    state_map = json.loads(open("name-abbr.json").read())
    if state in state_map:
        state = state_map[state]
    else:
        if len(state) > 2:
            state = state[:2]
    return state
    
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
    state = state_to_abbr(state)
    #label=f"{county}, {state} ({int(cases[-1])}, {int(deaths[-1])})"
    label=f"{county},{state}({int(deaths[-1])})"
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
    label=f"{state_to_abbr(state)} ({int(cases[-1])}, {int(deaths[-1])})"
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

def update_county_plot(percent, cases_by_county, num_days):
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
            x, y, label = plot_county(cases_by_county, county_state, num_days = num_days, min_cases=300, lineweight=lw, percent=percent)
        except covid_19.NotEnoughCases:
            continue
        visible=True
        if i >= top_n:
            visible='legendonly'
        fig.add_trace(go.Scatter(x=x, y=y, mode='lines+markers', name=label, visible=visible, line=dict(width=lw)))
    if percent:
        fig.update_layout(title="US Counties (deaths in parenthesis)",
                          xaxis_title="Date",
                          yaxis_title="Growth rate per day (%)",)
    else:
        fig.update_layout(title="US Counties (deaths in parenthesis)",
                          xaxis_title="Total Number of Cases",
                          yaxis_title=f"New Cases per day, {num_days} day average",
                          xaxis_type='log',
                          yaxis_type='log',)
    return fig

def update_state_plot(percent, cases_by_state, num_days):
    top_n = 10
    states = covid_19.states_by_num_cases(cases_by_state)
    top_states = states[:top_n]
    the_rest = states[top_n:]
    top_states.extend(sorted(the_rest))
    states = top_states
    fig = go.Figure()
    for i, state in enumerate(states):
        try:
            x, y, label = plot_state(cases_by_state, state, num_days=num_days, lineweight=1, percent=percent)
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
                          yaxis_title=f"New Cases per day, {num_days} day average",
                          xaxis_type='log',
                          yaxis_type='log',
                          
        )
    return fig

external_stylesheets = [
#    'https://codepen.io/chriddyp/pen/bWLwgP.css',
    'https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css',
]


county_plot = dcc.Graph(
    id='county-plot',
)
state_plot = dcc.Graph(
    id='state-plot',
#    figure=update_state_plot(False),
)

new_unemployment_plot = dcc.Graph(id='new-unemployment')
continuing_unemployment_plot = dcc.Graph(id='continuing-unemployment')
new_unemployment_pct_plot = dcc.Graph(id='new-unemployment-pct')
employment_plot = dcc.Graph(id='employment')
unemployment_plot = dcc.Graph(id='unemployment')
excess_covid_plot = dcc.Graph(id='excess-covid-unemployment')
excess_covid_pct_plot = dcc.Graph(id='excess-covid-unemployment-pct')


covid_pane_controls = html.Div(
    [
        dcc.Checklist(id='pct-checkbox', options=[{'label' : "Plots as Percent", 'value' : 'PCT'}], value=[]),
        html.Div([
            html.Label("Days to average: "),
            dcc.Slider(
                id="days-slider",
                min=1,
                max=10,
                step=1,
                value=5,
                marks={x: str(x) for x in range(11)},
            ),
        ]
        )
    ],
    className="col-md-3")

covid_pane=html.Div([
    html.Div(
        [
            dcc.Markdown('''
# Covid-19 plots
These plots were inspired by this [MinutePhysics](https://www.youtube.com/watch?v=54XLXg4fYsc) video, 
and the [assosciated web site](https://aatishb.com/covidtrends/).  I wanted those same plots, but
for the US states and counties.

## The dataset
The source data is regularly updated from the [New York Times dataset](https://github.com/nytimes/covid-19-data).
            ''', className="col-md-9"),
            covid_pane_controls,
        ], className="row"),
    dcc.Loading(
        id='covid-loading', type='default', children=[
            html.Div(html.Div(county_plot, className="col-md-12"), className="col-md-12"),
            html.Div(html.Div(state_plot, className="col-md-12"), className="col-md-12"),
        ],
        className="row")
])

unemployment_pane=html.Div([
    html.Div(className="row",children=[
    dcc.Markdown('''
# Unemployment Data
It was hard to find a good machine readable data source for
unemployment data.  It appears that the US government releases
official unemployment data as... get this... a PDF file.  Rally?
   
But I finally found the FRED database.  has a zillion data
sources, all in nicely accessible CSV format.  For example, here's
the [unemployment data source](https://fred.stlouisfed.org/series/UNRATE)

Each of their data sources has an ID that you can access it by. 
These are the ones I use for these plots

| ID | Info |
| --- |:---:|
| *UNRATE* | Unemployment Rate |
| *ICSA* | New unemployment claims this week |
| *CCSA* | Continuing unemployment claims this week |
| *LNU02000000* | The number of employed people in the US |

    ''', className="col-sm-9"),
    dcc.RadioItems(
        options=[
            {"label": "1 Year", "value": 365},
            {"label": "5 Years", "value": 365*5},
            {"label": "All", "value": ""},
        ],
        id='scale-selector',
        value=365,
        className="col-sm-3"),
    dcc.Loading(
        id='unemployment-loading',
        type='default',
        children=[
            html.Div(
                [
                    html.Div(new_unemployment_plot, className="col-md-6"),
                    html.Div(continuing_unemployment_plot, className="col-md-6"),
                ],
                className="row"),
            html.Div(
                [
                    html.Div(employment_plot, className="col-md-6"),
                    html.Div(unemployment_plot, className="col-md-6"),
                ],
                className="row"),
            html.Div(
                [
                    html.Div(new_unemployment_pct_plot, className="col-md-12"),
                ],
                className="row"),
            html.Div(
                [
                    
                    html.Div([html.Label("Excess claims since March 7, 2020.  Basically, this is the integral of new claims-base_level since 3/14/2020.  base_level is the march 7 level, just before the effects of COVID-19 layoffs could be seen in the data"),excess_covid_plot], className="col-md-6"),
                    html.Div([html.Label("Same as the preivous plot to the left, but expressed as a percentage of the total work force"),excess_covid_pct_plot], className="col-md-6"),
                ],
                className="row"),
        ]
    )
    ])])

title_row = html.Div(
    children=[
        dcc.Interval(
            id='page-load-interval',
            interval=1,
            n_intervals=0,
        ),
        html.Div([html.H1("Crome's COVID-19 plotter"), 'Get the source code at ', html.A("GitHub", href="https://github.com/ccrome/covid-19", target="_blank")], className="col-md-9"),
    ],
    className="row"
)

tabs = dcc.Tabs(
    [
        dcc.Tab(
            html.Div([
                dcc.Markdown('''
# Average causes of death vs COVID-19
The average causes of death in the plots below are from the latest
[2017 National Vital Statistics Report](https://www.cdc.gov/nchs/data/nvsr/nvsr68/nvsr68_06-508.pdf).
The 2018 and 2019 data isn't available yet.
'''
                ),
                dcc.Graph(id='causes-graph'),
                dcc.Graph(id='flu-graph'),
            ]), label="Causes of Death"),
        dcc.Tab(covid_pane, label="COVID"),
        dcc.Tab(unemployment_pane, label="Unemployment"),
    ]
)
main_area = html.Div([title_row, tabs], className="container")

cases_by_county = None
cases_by_state = None
country_summary = None

def del_and_clone():
    print("del and clone")
    subprocess.call(["rm", "-rf", "covid-19-data"])
    subprocess.call(["git", "clone", "https://github.com/nytimes/covid-19-data.git"])

def pull():
    global cases_by_state, cases_by_county, country_summary
    subprocess.call(["git", "pull"], cwd="covid-19-data")
    df_county = pd.read_csv("covid-19-data/us-counties.csv")
    df_state = pd.read_csv("covid-19-data/us-states.csv")
    cases_by_state = covid_19.df_to_dict_state(df_state)
    cases_by_county = covid_19.df_to_dict_county(df_county)
    country_summary = covid_19.summarize_state_data(cases_by_state)
    

update_lock = threading.Lock()
def update_data():
    global update_lock
    print("updating database")
    update_lock.acquire()
    try:
        pull()
    except:
        print("update failed.  Trying again")
        n = random.randint(5, 15)
        time.sleep(n)
        del_and_clone()
        pull()
    update_lock.release()
    

def serve_layout():
    return main_area

def clear_cache():
    import subprocess
    subprocess.run(["rm", "-rf", "cache"])

clear_cache()
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.title="COVID-19 Dashboard"
app.layout = serve_layout
server=app.server
cache = Cache(app.server, config={
    'CACHE_TYPE':'filesystem',
    'CACHE_DIR':'cache',
})
app.config.suppress_callback_exceptions = True

#del_and_clone()
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_data, trigger="interval", seconds=3600) # update the data once an hour
scheduler.start()


def make_plot(df, x_column, y_column, title, xaxis_label, yaxis_label, mode='lines+markers'):
    fig = px.line(df, x=x_column, y=y_column)
    fig.update_layout(
        title=title,
        xaxis_title=xaxis_label,
        yaxis_title=yaxis_label,
        showlegend=False,
        margin=dict(
            l=0,
            r=0,
            b=0,
            t=30,
            pad=0
        ))
    fig.data[0].update(mode='markers+lines')
    return fig

def get_unemployment_plots():
    unemployment_data = unemployment.get_unemployment_all()
    plots = {}
    for k in unemployment_data:
        df, config = unemployment_data[k]
        plots[k] = make_plot(df, config['xaxis'], config['yaxis'], config['title'], config['xlabel'], config['ylabel'])
    return plots

def update_cases():
    global cases_by_county, cases_by_state
    if cases_by_county is None or cases_by_state is None:
        print("Couldn't get the data.  why is that.  Let's update the data...")
        update_data()
        if cases_by_county is None or cases_by_state is None:
            print("Updated and still can't get the data... drats.")
            return

@app.callback(
    [
        Output('excess-covid-unemployment', 'figure'),
        Output('excess-covid-unemployment-pct', 'figure'),
    ],
    [
        Input('page-load-interval', 'value'),
    ],
)
@cache.memoize(timeout=3600*4)
def update_excess_unemployment(pct):
    dates, excess_unemployment, excess_as_pct = unemployment.get_excess_covid_claims()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=excess_unemployment, mode='lines+markers'))
    fig.update_layout(
        title="Excess Claims",
        xaxis_title="Date",
        yaxis_title="Excess claims")
    excess_fig = go.Figure()
    excess_fig.add_trace(go.Scatter(x=dates, y = excess_as_pct*100, mode="lines+markers"))
    excess_fig.update_layout(title="Excess claims as percent of workforce",
                      xaxis_title="Date",
                      yaxis_title="Excess claims (%)")
    return [fig, excess_fig]

@app.callback(
    [
        Output('new-unemployment', 'figure'),
        Output('continuing-unemployment', 'figure'),
        Output('employment', 'figure'),
        Output('unemployment', 'figure'),
        Output('new-unemployment-pct', 'figure'),
    ],
    [
        Input('page-load-interval', 'value'),
        Input('scale-selector', 'value'),
    ])
@cache.memoize(timeout=3600*4)
def update_employment_plots(pct_checkbox, scale_days):
    fred_plots = get_unemployment_plots()

    icsa_dates, icsa_pct = unemployment.get_as_part_of_employment('ICSA')
    ccsa_dates, ccsa_pct = unemployment.get_as_part_of_employment('CCSA')
    icsa_pct_fig = go.Figure()
    icsa_pct_fig.add_trace(go.Scatter(x=icsa_dates, y=icsa_pct*100, mode='lines+markers', name="New Claims"))
    icsa_pct_fig.add_trace(go.Scatter(x=ccsa_dates, y=ccsa_pct*100, mode='lines+markers', name="Cont. Claims"))
    icsa_pct_fig.update_layout(title="Unemployment Claims as percent of total workforce",
                               xaxis_title="Date",
                               yaxis_title="Percent (%)",
    )
    end=np.datetime64('today')
    if scale_days is "":
        start = icsa_dates[0]
    else:
        start=end-np.timedelta64(scale_days, 'D')
    
    icsa_pct_fig.update_xaxes(range=[start, end])
    fred_plots['new_claims'].update_xaxes(range=[start, end])
    fred_plots['cont_claims'].update_xaxes(range=[start, end])
    fred_plots['employment'].update_xaxes(range=[start, end])
    fred_plots['unemployment'].update_xaxes(range=[start, end])
    return fred_plots['new_claims'], fred_plots['cont_claims'], fred_plots['employment'], fred_plots['unemployment'], icsa_pct_fig    

@app.callback(
    [Output('causes-graph', 'figure'),
     Output('flu-graph', 'figure'),
    ],
    [Input('page-load-interval', 'value')],
)

def causes_plot(loader):
    global cases_by_state, country_summary
    if cases_by_state is None:
        update_cases()
    total_deaths = country_summary['deaths'][-1]
    all_fig = go.Figure()
    causes = death.get_causes()
    x = [c[0] for c in causes]
    y = [int(c[1]/365+0.5) for c in causes]
    for xi, yi in zip(x, y):
        all_fig.add_trace(go.Bar(x=["Non-Covid",], y=[yi,], name=xi))
    weekdates = country_summary['date'][-14:]
    weekdeaths = country_summary['deaths'][-14:]
    all_fig.add_trace(go.Bar(x=weekdates, y=weekdeaths, name="COVID-19"))
    all_fig.update_layout(barmode='stack')
    date = cases_by_state["California"]["date"][-1]
    flu_fig = go.Figure()
    flu_deaths_years = [f"{x}" for x in [1918, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019]]
    flu_deaths_values = np.array([675, 37, 12, 43, 38, 51, 23, 38, 61, 34]) * 1000/365
    flu_fig.add_trace(go.Bar(x=flu_deaths_years, y = flu_deaths_values, name="Average Flu Deaths per day"))
    flu_fig.add_trace(go.Bar(x=[f"{date}",], y=[total_deaths,], name=f"COVID-19 deaths {date}"))
    flu_fig.update_layout(
        title=f"Average Influenza Deaths per day vs COVID-19 deaths {date} in the USA",
        xaxis_title="Year",
        yaxis_title="Deaths per day",
        xaxis_type="category",
    )
    return all_fig, flu_fig

@app.callback(
    [
        Output('county-plot', 'figure'),
        Output('state-plot', 'figure'),
    ],
    [
        Input('pct-checkbox', 'value'),
        Input('days-slider', 'value'),
    ])
@cache.memoize(timeout=3600*4)
def update_plots(percent, days):
    global cases_by_county, cases_by_state
    update_cases()
    county_plot = update_county_plot(percent, cases_by_county, days)
    state_plot = update_state_plot(percent, cases_by_state, days)
    return county_plot, state_plot

if __name__ == '__main__':
    app.run_server(debug=True, host="0.0.0.0")
