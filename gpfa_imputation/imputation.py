# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/03_Imputation.ipynb.

# %% auto 0
__all__ = ['GPFAImputation', 'GPFAImputationExplorer', 'GPFAResult']

# %% ../lib_nbs/03_Imputation.ipynb 4
from .learner import *
from .data_preparation import *

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
        units = None # Dict of unit for each column. Used for plotting
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
        
        self.learner = GPFALearner(X = self.train_data, T = self.train_T, latent_dims=latent_dims)
        

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
    ):
        self.data = data
        self.latent_dims = latent_dims
        
        device = 'cuda' if cuda else 'cpu'
        
        self.T = torch.arange(0, len(data), dtype=torch.float32, device=device) # time is encoded with a increase of 1
        
        # Training data
        self.train_idx = ~self.data.isna().any(axis=1)
        self.train_data = torch.tensor(self.data[self.train_idx].to_numpy().astype(np.float32), device=device)
        self.train_T = self.T[self.train_idx]
        
        self.learner = GPFALearner(X = self.train_data, T = self.train_T, latent_dims=latent_dims)
        
        
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

# %% ../lib_nbs/03_Imputation.ipynb 45
class GPFAResult:
    def __init__(self,
                 data_imputed, #imputed data in tidy format
                 data_complete, # complete data in tidy format
                 learner, # learner for parameters display
                 units = None, # units for plots
                ):
        store_attr()
        
    

# %% ../lib_nbs/03_Imputation.ipynb 47
@patch
def to_result(self: GPFAImputation, data_complete, units=None):
    return GPFAResult(self.impute(add_time=True), data_complete, self.learner, units)

# %% ../lib_nbs/03_Imputation.ipynb 48
@patch
def to_result(self: GPFAImputationExplorer, data_complete, units=None):
    return GPFAResult(self.predict(), data_complete, self.learner, units)

# %% ../lib_nbs/03_Imputation.ipynb 52
@patch
def compute_metric(self: GPFAResult,
                   metric, # function that takes as argument true and pred and returns the metric
                   metric_name = 'metric',
                   all_data = False # whether to consider whole dataset or only where there is the gap
                  ):
    df = pd.merge(self.data_imputed, self.data_complete, on = ['time','variable'])
    
    vars = []
    
    for var in df.variable.unique():
        mask = (df.variable == var) & (df.is_missing == True) if not all_data else df.variable == var
        df_var = df[mask]
        vars.append({'variable': var,
                      metric_name: metric(df_var['value'], df_var['mean'])})
    
    return pd.DataFrame(vars)

# %% ../lib_nbs/03_Imputation.ipynb 53
@patch
def rmse(self: GPFAResult, all_data=False):
    return self.compute_metric(lambda x, y: np.sqrt(mean_squared_error(x,y)), "rmse", all_data=all_data)
    

# %% ../lib_nbs/03_Imputation.ipynb 56
@patch
def r2(self: GPFAResult, all_data=True):
    return self.compute_metric(r2_score, "r2", all_data)

# %% ../lib_nbs/03_Imputation.ipynb 59
def _plot_variable(imp, complete, variable, y_label="", sel=None, properties = {}):
    
    imp = imp[imp.variable == variable]

    
    error = alt.Chart(imp).mark_errorband().encode(
        x = "time",    
        y = alt.Y("err_low:Q", title = y_label, scale=alt.Scale(zero=False)),
        y2 = "err_high:Q",
        color=alt.Color("variable",
                        legend = alt.Legend(title=["Line: pred. mean", "area: +/- 2 std", "(variable)"])
                       ),
        tooltip = alt.Tooltip(['std', 'mean'], format=".4")
    ).transform_calculate(
        err_low = "datum.mean - 2 * datum.std",
        err_high = "datum.mean + 2 * datum.std"
    ).properties( **properties)

    pred = alt.Chart(imp).mark_line().encode(
        x = "time",    
        y = alt.Y("mean:Q", title = y_label, scale=alt.Scale(zero=False)),
        color="variable",
    ).add_selection(
        sel if sel is not None else alt.selection_interval(bind="scales")
    ).properties(title = variable)

    base_plot = error + pred
    
    if complete is not None:

        complete = complete[complete.variable == variable]
        truth_plt = alt.Chart(complete).mark_point(
            color='black',
            strokeWidth = 1,
            fillOpacity = 1
        ).encode(
            x = "time",
            y = alt.Y("value", title = y_label, scale=alt.Scale(zero=False)),
            fill= alt.Fill("is_missing", scale = alt.Scale(range=["#ffffff00", "black"]),
                           legend = alt.Legend(title =["Observed data","(is missing)"])),
            shape = "is_missing",
        )

        base_plot = truth_plt + base_plot
        
    return base_plot
    

# %% ../lib_nbs/03_Imputation.ipynb 61
@patch()
def plot_pred(
    self: GPFAResult,
    n_cols: int = 2,
    bind_interaction: bool =True, # Whether the sub-plots for each variable should be connected for zooming/panning
    properties:dict = {} # additional properties (eg. size) for altair plot
):
    "Plot the prediction for each variable"
   
    plot_list = [alt.hconcat() for _ in range(0, self.data_imputed.shape[0], n_cols)]
    selection_scale = alt.selection_interval(bind="scales", encodings=['x']) if bind_interaction else None
    for idx, variable in enumerate(pd.unique(self.data_imputed.variable)):
        plot_list[idx // n_cols] |= _plot_variable(self.data_imputed,
                                                   self.data_complete,
                                                   variable,
                                                   y_label = f"{variable} [{self.units[variable]}]" if self.units is not None else variable,
                                                   sel = selection_scale, properties=properties)
    
    plot = alt.vconcat(*plot_list)
    
    return plot

# %% ../lib_nbs/03_Imputation.ipynb 65
from IPython.display import HTML

from ipywidgets import HBox, VBox, interact, widgets
from ipywidgets.widgets import Output

# %% ../lib_nbs/03_Imputation.ipynb 66
def _display_as_row(dfs, titles=None):
    """display multiple dataframes in the same row"""
    dfs =  listify(dfs)
    titles = listify(titles)
    out = []
    for df, title in zip_longest(dfs, titles, fillvalue=""):
        out.append(f"<div> <p style='font-size: 1.3rem; font-decoration: bold'>{title}<p> {df.to_html()} </div>")
    out = f"<div style=\"display: flex; gap: 20px;\"> {''.join(out)}</div>"
    display(HTML("".join(out)))

def _style_df(df):
    """style dataframe for better printing """
    return df.style.hide(axis="index").format(precision = 4)

# %% ../lib_nbs/03_Imputation.ipynb 70
@patch 
def display_results(self: GPFAResult, plot_args={}):
    plot_args = {'properties': {'height': 150 , 'width': 300}, **plot_args} # set default plot size
    plot = self.plot_pred(**plot_args)
    
    r2 = self.r2()
    
    # there is no GPFA leaner so don't display metrics and return early
    if self.learner is None:
        display(plot)
        _display_as_row(_style_df(r2), "r2")
        return
    
    variables = pd.DataFrame({'variable': self.data_imputed.columns})
    latent_names = [f"z{i}" for i in range(self.learner.latent_dims)]

    
    Lambda = pd.concat([
        variables,
        pd.DataFrame(
            self.learner.model.covar_module.Lambda.detach().cpu().numpy(),
            columns=latent_names)
    ], axis=1)
    
    
    lengthscale = pd.DataFrame({
        'latent': latent_names,
        'lengthscale': [self.learner.model.covar_module.latent_kernels[i].lengthscale.detach().item() for i in range(self.learner.latent_dims)]
    })
    
    #loss = plt.plot(self.learner.losses)
    
    
    display(plot)
    _display_as_row([_style_df(df) for df in [r2, Lambda, lengthscale]], ["r2", "Λ", "Lengthscale"])
    
