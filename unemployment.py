import threading
import urllib.request
import pandas as pd
import os
import time

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
def _get_df(url, local_fn, expiry_age = 60*60*24):
    """Gets the url as a pandas dataframe.  Only retrieves new data once a day"""
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
    url = fred_url_base + config['fred_id']
    df = _get_df(url, config['fred_id']+'.csv')
    if 'apply' in config:
        df[config['fred_id']] = df[config['fred_id']].apply(config['apply'])
    return df, config

def get_unemployment_all():
    results = {}
    for k in plots_config:
        results[k] = get_unemployment(k)
    return results
