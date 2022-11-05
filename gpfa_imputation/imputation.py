# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/03_Imputation.ipynb.

# %% auto 0
__all__ = ['GPFAImputation', 'GPFAImputationExplorer']

# %% ../lib_nbs/03_Imputation.ipynb 4
from .learner import *
from .data_preparation import *
from .gpfa import GPFA

import torch

import pandas as pd
import numpy as np
import sklearn
from sklearn.metrics import mean_squared_error, r2_score

from fastcore.foundation import patch, patch_to
from fastcore.meta import delegates
from fastcore.basics import store_attr, listify
from fastcore.test import test_close
from itertools import zip_longest

import matplotlib.pyplot as plt
import altair as alt
from altair import datum

from functools import lru_cache

# %% ../lib_nbs/03_Imputation.ipynb 18
class GPFAImputation:
    def __init__(
        self,
        data: pd.DataFrame , #observed data with missing data as NA
        latent_dims = 1,
        cuda = False, # Use GPU?
        units = None, # Dict of unit for each column. Used for plotting
        model = GPFA # sub-class of `GPFA` 
    ):
        self.data = data.copy()
        self.units=units
        self.latent_dims = latent_dims
        
        
        device = 'cuda' if cuda else 'cpu'
        
        self.T = torch.arange(0, len(data), dtype=torch.float32, device=device) # time is encoded with a increase of 1
        
        # Training data
        self.train_idx = ~self.data.isna().any(axis=1)
        self.train_data = torch.tensor(self.data[self.train_idx].to_numpy().astype(np.float32), device=device)
        self.train_T = self.T[self.train_idx]
        
        self.learner = GPFALearner(X = self.train_data, T = self.train_T, latent_dims=latent_dims, model=model)
        

        # Prediction data
        self.pred_T = self.T[~self.train_idx]
        self.cond_idx = torch.tensor(~self.data[~self.train_idx].isna().to_numpy().flatten(), device=device) # conditional obsevations
        self.cond_obs = torch.tensor(self.data[~self.train_idx].to_numpy().astype(np.float32).flatten()[self.cond_idx.cpu()], device=device)
        
        if cuda: self.learner.cuda()
        
    def fit(self):
        "Fit learner to training data"
        self.learner.train()
        return self

    def impute(self,
               add_time = True, # add column with time?
               tidy = True, # tidy data?
               ):
        
        self.pred = self.learner.predict(self.pred_T, obs = self.cond_obs, idx = self.cond_idx)
        if not hasattr(self, "pred"):
            self.fit()

        
        if tidy: return self._impute_tidy(add_time)
        else: return self._impute_wide(add_time)
        
        
    def _impute_wide(self, add_time):
        """ Impute in wide format"""
        
        imp_data = self.data.copy()
        for col_idx, col_name in enumerate(imp_data.columns):
            imp_data.loc[~self.train_idx, col_name] = self.pred.mean[:, col_idx].cpu().numpy()
            imp_data.loc[~self.train_idx, col_name + "_std"] = self.pred.std[:, col_idx].cpu().numpy()
        
        if add_time:
            imp_data["time"] = self.T.cpu()
        
        return imp_data 
    
    def _impute_tidy(self, add_time):
        """ transform the pred output into a tidy dataframe suitable for plotting"""
        feature_names = self.data.columns

        pred_mean = pd.DataFrame(self.pred.mean.cpu(), columns = feature_names).assign(time = self.pred_T.cpu()).melt("time", value_name="mean")
        pred_std = pd.DataFrame(self.pred.std.cpu(), columns = feature_names).assign(time = self.pred_T.cpu()).melt("time", value_name="std")
        
        pred = pd.merge(pred_mean, pred_std, on=['time', 'variable'])  
        
        train_data = self.data[self.train_idx].assign(time = self.train_T.cpu()).melt("time", value_name = "mean")
               
        imp_data = pd.concat((train_data, pred))
        
        self.pred_wide = imp_data
        
        return imp_data

# %% ../lib_nbs/03_Imputation.ipynb 33
@patch
def __repr__(self: GPFAImputation):
    return f"""GPFA Imputation:
    N obs: {self.data.shape[0]}
    N features {self.data.shape[1]} ({', '.join(self.data.columns)})
    N missing observations {(~self.cond_idx).sum()}
    N latent: {self.learner.latent_dims}"""

@patch
def __str__(self: GPFAImputation):
    return self.__repr__()

# %% ../lib_nbs/03_Imputation.ipynb 37
class GPFAImputationExplorer:
    def __init__(
        self,
        data: pd.DataFrame , #observed data with missing data as NA
        latent_dims = 1,
        cuda = False, # Use GPU?
        model = GPFA # sub-class of `GPFA` 
    ):
        self.data = data
        self.latent_dims = latent_dims
        
        device = 'cuda' if cuda else 'cpu'
        
        self.T = torch.arange(0, len(data), dtype=torch.float32, device=device) # time is encoded with a increase of 1
        
        # Training data
        self.train_idx = ~self.data.isna().any(axis=1)
        self.train_data = torch.tensor(self.data[self.train_idx].to_numpy().astype(np.float32), device=device)
        self.train_T = self.T[self.train_idx]
        
        self.learner = GPFALearner(X = self.train_data, T = self.train_T, latent_dims=latent_dims, model=model)
        
        
        # There is no conditional observation here since it probably doesn't make much sense here
               
        if cuda: self.learner.cuda()
        
    def fit(self):
        "Fit learner to training data"
        self.learner.train()
        return self

    def predict(self):
        
        # return always tidy df
        
        self.pred = self.learner.predict(self.T)
        
        feature_names = self.data.columns
        pred_mean = pd.DataFrame(self.pred.mean.cpu(), columns = feature_names).assign(time = self.T.cpu()).melt("time", value_name="mean")
        pred_std = pd.DataFrame(self.pred.std.cpu(), columns = feature_names).assign(time = self.T.cpu()).melt("time", value_name="std")
        
        return pd.merge(pred_mean, pred_std, on=['time', 'variable'])
    
    def fit_predict(self):
        self.fit()
        return self.predict()

# %% ../lib_nbs/03_Imputation.ipynb 39
@patch
def __repr__(self: GPFAImputationExplorer):
    return f"""GPFA Imputation Explorer:
    N obs: {self.data.shape[0]}
    N features {self.data.shape[1]} ({', '.join(self.data.columns)})
    N missing observations {self.data.isna().to_numpy().flatten().sum()}
    N latent: {self.learner.latent_dims}"""

@patch
def __str__(self: GPFAImputationExplorer):
    return self.__repr__()
