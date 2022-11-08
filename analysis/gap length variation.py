from gpfa_imputation.imputation import *
from gpfa_imputation.data_preparation import *
from gpfa_imputation.results import *
from gpfa_imputation.results import _display_as_row 

import torch
import pandas as pd
import numpy as np
from pathlib import Path
from pyprojroot import here
import matplotlib.pyplot as plt

from gpfa_imputation.utils import cache_disk

from itertools import combinations, repeat, zip_longest

from ipywidgets import interact
from tqdm.auto import tqdm

from multiprocessing import Pool

from fastcore.basics import listify

import pickle

hai_path = Path("FLX_DE-Hai_FLUXNET2015_FULLSET_HH_2000-2012_1-4.csv")
hai_raw = pd.read_csv(here("data") / hai_path, na_values=["-9999", "-9999.99"], parse_dates=[0, 1], nrows=200)

meteo_vars = {
    "TA_F": "TA",
    "SW_IN_F": "SW_IN",
    #"LW_IN_F": "LW_IN",
    "VPD_F": "VPD",
    #"PA": "PA"
}

units = {
    'TA': '°C',
    'SW_IN': 'W m-2',
    'LW_IN': 'W m-2',
    'VPD': 'hPa'
}

hai = (hai_raw
       .rename(columns=meteo_vars)
       .set_index("TIMESTAMP_END")
       .loc[:, meteo_vars.values()])
hai

n_obs = 200
n_latent = 1
total_iter = 100

model_save_dir = here() / "analysis/trained_models"

model_path = model_save_dir / f"GPFA_l_{n_latent}_train_{total_iter}_1ker_{n_obs}_obs.pickle"

data = GPFADataTest(hai[:n_obs])

# inspired from https://datagy.io/python-combinations-of-a-list/
def all_comb(l):
    list_combinations = []
    for n in range(1, len(l) + 1):
        list_combinations += list(combinations(l, n))
    return list_combinations


def to_result_pretrained(gap_len, n_latent, var_sel, gap_start=None):
    data = GPFADataTest(hai[:n_obs]).add_gap(gap_len, var_sel, gap_start)
    imp = GPFAImputationExplorer(data.data, latent_dims = n_latent)
    model_path = model_save_dir / f"GPFA_l_{n_latent}_train_{total_iter}_1ker_{n_obs}_obs.pickle"
    imp.learner.load(model_path)
    return imp.to_result(data.data_compl_tidy, units=units)

gaps = [2, 5, 7, 10, 20, 30, 50, 100]
gap_starts = [0, 30, 60, 90]

path_base = here() / ".cache/diff_gap_partial"
# path_base.rmdir()

def process_var_sel(args, path_base=path_base):
    var_sel, n_lat = args # limitations in python map...
    f_name = path_base / f"{'-'.join(listify(var_sel))}__l_{n_lat}.pickle"
    if f_name.exists(): return
    out = {}
    for gap_len in gaps:
        out[gap_len] = {}
        for gap_start in gap_starts:
            out[gap_len][gap_start] = to_result_pretrained(gap_len, n_latent=n_lat, var_sel = var_sel, gap_start=gap_start) 
    with open(f_name, "wb") as f:
        pickle.dump(out, f)    

def compute_diff_gaps(gap_start=30):
    for n_lat in tqdm(range(1,4)):
        with Pool(processes=4) as pool:
            list(pool.imap(process_var_sel, zip(all_comb(meteo_vars.values()), repeat(n_lat,))))

compute_diff_gaps()
