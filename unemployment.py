import threading
import urllib.request
import pandas as pd
import os
import time
import numpy as np

class UnemploymentDataException(Exception):
    pass

fred_url_base = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id='

plots_config = dict(
    new_claims=dict(fred_id='ICSA', title='Weekly new unemployment claims', xlabel='Date', ylabel='Claims Per Week'),
    cont_claims=dict(fred_id='CCSA', title="Weekly continuing unemployment claims", xlabel='Date', ylabel='Claims Per Week'),
    employment=dict(fred_id='LNU02000000', title='Employment Level', xlabel='Date', ylabel='Employment', apply=lambda x: x*1000),
    unemployment=dict(fred_id='UNRATE', title='Unemployment', xlabel='date', ylabel='Unemployment (%)'),
)

update_lock = threading.Lock()
def get_df(fred_id, local_fn=None, expiry_age = 60*60*24):
    """Gets the url as a pandas dataframe.  Only retrieves new data once a day"""
    if local_fn is None:
        local_fn = f"{fred_id}.csv"
    url = fred_url_base + fred_id
    do_update = True
    if os.path.exists(local_fn):
        mtime = os.path.getmtime(local_fn)
        now = time.time()
        age = now-mtime
        if age <= expiry_age:
            do_update = False
    if do_update:
        update_lock.acquire()
        df = None
        with urllib.request.urlopen(url) as response:
            data = response.read().decode('UTF-8')
            with open(local_fn, "w") as f:
                f.write(data)
        update_lock.release()
    df = pd.read_csv(local_fn)
    return df

def get_unemployment(name):
    """retruns 2 data frames unemployment data: new claims and continuing claims.  Can raise an UnemploymentDataException if the data isnt' available."""
    config = plots_config[name]
    if 'xaxis' not in config:
        config['xaxis']='DATE'
    if 'yaxis' not in config:
        config['yaxis']=config['fred_id']
    fred_id=config['fred_id']
    df = get_df(fred_id, config['fred_id']+'.csv')
    if 'apply' in config:
        df[config['fred_id']] = df[config['fred_id']].apply(config['apply'])
    return df, config

def get_unemployment_all():
    results = {}
    for k in plots_config:
        results[k] = get_unemployment(k)
    return results

def get_as_part_of_employment(key):
    """Get's a FRED key as a fraction of the total employment level.  Returns dates, fraction"""
    icsa = get_df(key)
    employment = get_df('LNU02000000')
    x0 = np.array(icsa['DATE'].values, dtype=np.datetime64)
    y0 = icsa[key].values
    x1 = np.array(employment['DATE'].values, dtype=np.datetime64)
    y1 = employment['LNU02000000'].values * 1000
    a = x0.astype(int, casting='unsafe')
    b = x1.astype(int, casting='unsafe')
    interp_employ = np.interp(a, b, y1)
    return x0, y0/interp_employ

def get_excess_covid_claims():
    """Look at the excess COVID-19 unemployment claims
    
    The first set of excess covid claims started on March 14, 2020
    The level before that was 211k claims, then 282k, then 3,030k and up
    This function returns the integral of (claims-211k) starting on 3/14
    """
    icsa_df = get_df('ICSA')
    icsa_values = icsa_df['ICSA']
    icsa_dates = np.array(icsa_df['DATE'].values, dtype=np.datetime64)
    starting_idx = np.argmin(np.abs(icsa_dates-np.datetime64('2020-03-07')))
    base_value = icsa_values[starting_idx]
    x = icsa_dates[starting_idx:]
    y = np.cumsum(icsa_values[starting_idx:])
    assert(x.shape == y.shape)
    return x, y-base_value, (y-base_value)/158000000
