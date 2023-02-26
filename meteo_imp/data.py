# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/Fluxnet/Hainich.ipynb.

# %% auto 0
__all__ = ['meteo_vars_big', 'units', 'units_big', 'hai_path_raw', 'hai_path', 'hai_path64', 'hai_big_path', 'hai_era_path_raw',
           'hai_era_path', 'hai_era_path64', 'hai_era_big_path', 'era_vars', 'era_vars_big', 'control_map', 'dark2',
           'scale_meteo', 'read_fluxnet_csv']

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 3
from pathlib import Path
from pyprojroot import here
import pandas as pd
import numpy as np

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 5
_def_meteo_vars = {
    "TA_F": "TA",
    "SW_IN_F": "SW_IN",
    # "LW_IN_F": "LW_IN",
    "VPD_F": "VPD",
    #"PA": "PA"
}


meteo_vars_big = {f"{var}_F" : var for var in ['TA', 'SW_IN', 'LW_IN', 'VPD', 'WS', 'PA', 'P']} | {'SWC_F_MDS_1': 'SWC', 'TS_F_MDS_1': 'TS'}


units = {
    'TA': '°C',
    'SW_IN': 'W m-2',
    # 'LW_IN': 'W m-2',
    'VPD': 'hPa'
}

units_big = {
    'TA': '°C',
    'SW_IN': 'W m-2',
    'VPD': 'hPa',
    'PA': 'hPa',
    'P': 'mm',
    'WS': 'm s-1',
    'LW_IN': 'W m-2',
    'TS': '°C',
    'SWC': '%'
    
    # 'NETRAD': 'W m-2',
}

hai_path_raw = here("data") / "FLX_DE-Hai_FLUXNET2015_FULLSET_HH_2000-2012_1-4.csv"
hai_path = here("data") / "FLX_DE-Hai_FLUXNET2015_FULLSET_HH_2000-2012_1-4_float32.parquet"
hai_path64 = here("data") / "FLX_DE-Hai_FLUXNET2015_FULLSET_HH_2000-2012_1-4_float64.parquet"
hai_big_path = here("data") / "FLX_DE-Hai_FLUXNET2015_FULLSET_HH_2000-2012_1-4_float64_big.parquet"

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 6
def get_dtype(col_name: str, num_dtype=np.float32):
    "Get correct dtype based on column name"
    if col_name in ["TIMESTAMP_END", "TIMESTAMP_START"]:
        return 'str'
    elif col_name.endswith("QC"):
        return None # pd.CategoricalDtype
    else:
        return num_dtype

def col_types(cols, num_dtype=np.float32):
    return {col: get_dtype(col, num_dtype) for col in cols}

def read_col_names(path):
    "read only column names from csv"
    return pd.read_csv(path, nrows=0).columns

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 9
def read_fluxnet_csv(path,
                     nrows:int,
                     meteo_vars: dict[str, str] = _def_meteo_vars,
                     num_dtype = np.float32 # type for numerical columns
                    ):
    "Read fluxnet csv in Pandas with correct parsing of csv"
    return (pd.read_csv(path, na_values=["-9999", "-9999.99"],
                        parse_dates=[0, 1],
                        nrows=nrows,
                        dtype=col_types(read_col_names(path), num_dtype)
                       )
           .rename(columns={'TIMESTAMP_END': "time"})
           .set_index("time")
           .filter(meteo_vars.keys(), axis='columns')
           .rename(columns=meteo_vars))

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 21
try:
    hai = pd.read_parquet(hai_path)
except FileNotFoundError: # for CI
    hai = pd.DataFrame()

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 25
hai_era_path_raw = here("data") / "FLX_DE-Hai_FLUXNET2015_ERAI_HH_1989-2014_1-4.csv"
hai_era_path = here("data")/"FLX_DE-Hai_FLUXNET2015_ERAI_HH_1989-2014_1-4_float32.parquet"
hai_era_path64 = here("data")/"FLX_DE-Hai_FLUXNET2015_ERAI_HH_1989-2014_1-4_float64.parquet"
hai_era_big_path = here("data")/"FLX_DE-Hai_FLUXNET2015_ERAI_HH_1989-2014_1-4_float64_big.parquet"

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 27
era_vars = {
    'TA_ERA': 'TA_ERA',
    'SW_IN_ERA': 'SW_IN_ERA',
    'VPD_ERA': 'VPD_ERA'
}

era_vars_big = {f"{var}_ERA" : f"{var}_ERA"  for var in ['TA', 'SW_IN','VPD', 'PA', 'P', 'WS', 'LW_IN',]}

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 36
control_map = {f"{var}_ERA" : var  for var in ['TA', 'SW_IN','VPD', 'PA', 'P', 'WS', 'LW_IN',]}

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 39
import altair as alt

# %% ../lib_nbs/Fluxnet/Hainich.ipynb 41
dark2 = ['#1B9E77', '#D95F02', '#7570B3', '#E7298A', '#66A61E', '#E6AB02', '#A6761D', '#666666']

scale_meteo = alt.Scale(domain = ['TA', 'SW_IN', 'LW_IN', 'VPD', 'WS', 'PA', 'SWC', 'TS', 'P'], range = dark2)
