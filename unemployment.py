import threading
import urllib.request
import pandas as pd
import io
import os
import time

class UnemploymentDataException(Exception):
    pass

new_claims_url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=ICSA'
continuing_claims_url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=CCSA'
employment_level_url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=LNU02000000'
unemployment_url = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE'

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

def get_unemployment():
    """retruns 2 data frames unemployment data: new claims and continuing claims.  Can raise an UnemploymentDataException if the data isnt' available."""
    new_claims = _get_df(new_claims_url, "new_claims.csv")
    continuing_claims = _get_df(continuing_claims_url, "continuing_claims.csv")
    employment_level = _get_df(employment_level_url, "employment_level.csv")
    employment_level['LNU02000000'] = employment_level['LNU02000000'].apply(lambda x: x*1000)
    unemployment = _get_df(unemployment_url, "unemployment.csv")
    return new_claims, continuing_claims, employment_level, unemployment
