# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/Fluxnet/Hainich.ipynb.

# %% auto 0
__all__ = ['units', 'hai_path', 'read_fluxnet_csv']

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 3
from pathlib import Path
from pyprojroot import here
import pandas as pd
import numpy as np

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 4
_def_meteo_vars = {
    "TA_F": "TA",
    "SW_IN_F": "SW_IN",
    # "LW_IN_F": "LW_IN",
    "VPD_F": "VPD",
    #"PA": "PA"
}


units = {
    'TA': '°C',
    'SW_IN': 'W m-2',
    # 'LW_IN': 'W m-2',
    'VPD': 'hPa'
}

hai_path = here("data") / "FLX_DE-Hai_FLUXNET2015_FULLSET_HH_2000-2012_1-4.csv"

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 5
def read_fluxnet_csv(path,
                     nrows:int,
                     meteo_vars: dict[str, str] = _def_meteo_vars,):
    "Read fluxnet csv in Pandas with correct parsing of csv"
    return (pd.read_csv(path, na_values=["-9999", "-9999.99"], parse_dates=[0, 1], nrows=nrows, dtype=np.float32)
           .rename(columns=meteo_vars)
           .set_index("TIMESTAMP_END")
           .loc[:, meteo_vars.values()])

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 7
try:
    hai = read_fluxnet_csv(hai_path, 200)
except FileNotFoundError: # for CI
    hai = pd.DataFrame()
