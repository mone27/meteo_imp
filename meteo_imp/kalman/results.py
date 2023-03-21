# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/20_results.ipynb.

# %% auto 0
__all__ = ['path_r', 'rmse_mask', 'var_type', 'method_type', 'base_path', 'method_scale', 'meteo_scale', 'plot_formatter',
           'renames_table_latex', 'renames_table_latex_stand', 'err_type', 'err_type_rev', 'PredictLossVar',
           'PredictLikelihoodVar', 'MultiMetrics', 'KalmanImputation', 'KalmanImputationVar', 'importr_install',
           'setupR', 'pd2R', 'R2pd', 'add_buffer', 'item2REddy', 'gap_fill_item', 'MDSImputation', 'ERAImputation',
           'MaskedMetric', 'rmse', 'normalize', 'NormalizedMetric', 'format_gap_len', 'prep_df', 'timeseriesAgg',
           'RMSEAgg', 'ImpComparison', 'l_model', 'KalmanImpComparison', 'facet_wrap', 'facet_grid', 'PlotFormatter',
           'the_plot', 'the_plot_stand', 'the_plot_stand2', 'custom_boxplot_nooutlier', 'the_plot_stand3',
           'agg_gap_len', 'plot_gap_len', 'plot_compare', 'unnest_predictions', 'plot_timeseries',
           'highlight_min_method', 'style_the_table', 'the_table', 'the_table_latex', 'table_compare',
           'table_compare_latex', 'table_compare3', 'table_compare3_latex', 'table_gap_len', 'table_gap_len_latex']

# %% ../../lib_nbs/20_results.ipynb 6
from fastcore.test import *
from fastcore.basics import *
from ..utils import *
from ..gaussian import *
from .filter import *
from .filter import get_test_data
from ..data import *
from .training import *
from .training import _n_tuple
from fastcore.transform import *
from fastai.learner import *
from pyprojroot import here

import pykalman
from typing import *

import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype
import torch
from torch import Tensor
from torch.distributions import MultivariateNormal

from timeit import timeit
import polars as pl
import altair as alt

from tqdm.auto import tqdm

import io
from contextlib import redirect_stderr
import random
from math import floor

from dataclasses import dataclass
from functools import partial
from itertools import zip_longest

# %% ../../lib_nbs/20_results.ipynb 22
def _extract_var(preds, var_idx, max_len):
    "extract prediction only from one var"
    preds_new = []
    for b_pred in preds:
        b_pred_new = []
        for pred in b_pred:
            if len(pred) == 1: pred_new = pred
            elif len(pred) == max_len: pred_new = pred[var_idx:var_idx+1] if pred.dim() == 1 else pred[var_idx:var_idx+1, var_idx:var_idx+1]
            else: raise ValueError("supports only gaps for 1 or all variables")
            b_pred_new.append(pred_new)
        preds_new.append(b_pred_new)
    return preds_new
         

# %% ../../lib_nbs/20_results.ipynb 31
class PredictLossVar:
    """loss (negative log likelihood) for only for one variable for each batch"""
    def __init__(self, only_gap:bool, var: int):
        self.loss_func = KalmanLoss(only_gap)
        self.var = var
    def __call__(self, preds, targs):
        sel_idx = [idx for idx in range(targs[1].shape[-1]) if idx != self.var]
        mask_new = targs[1].clone()
        mask_new[:, :, sel_idx] = True # make all other variables present
        targs_new = (targs[0], mask_new, targs[2])
        preds_new = (_extract_var(preds.mean, self.var, targs[1].shape[-1]), _extract_var(preds.cov, self.var, targs[1].shape[-1])) 
        # return preds_new
        # return self.loss_func(preds_new, targs_new)
        losses = []
        for i in range(len(preds_new[0])):
            losses.append(self.loss_func(_n_tuple(preds_new, i), _n_tuple(targs_new, i)))
        return losses

# %% ../../lib_nbs/20_results.ipynb 34
class PredictLikelihoodVar:
    """mean between timesteps of Likelihood for only for one variable for each batch"""
    def __init__(self, only_gap:bool, var: int):
        self.loss_func = KalmanLoss(only_gap, reduction_inbatch='none', reduction = 'none')
        self.var = var
    def __call__(self, preds, targs):
        sel_idx = [idx for idx in range(targs[1].shape[-1]) if idx != self.var]
        mask_new = targs[1].clone()
        mask_new[:, :, sel_idx] = True # make all other variables present
        targs_new = (targs[0], mask_new, targs[2])
        preds_new = (_extract_var(preds.mean, self.var, targs[1].shape[-1]), _extract_var(preds.cov, self.var, targs[1].shape[-1])) 
        # return preds_new
        # return self.loss_func(preds_new, targs_new)
        likelihoods = []
        for i in range(len(preds_new[0])):
            loss = self.loss_func(_n_tuple(preds_new, i), _n_tuple(targs_new, i))[0]
            lh = (torch.exp(-loss[0])).mean()
            likelihoods.append(lh)
        return likelihoods

# %% ../../lib_nbs/20_results.ipynb 36
class MultiMetrics():
    def __init__(self, **metrics): self.metrics = metrics
    def __call__(self, preds, targs): return {name: metric(preds, targs) for name, metric in self.metrics.items()}

# %% ../../lib_nbs/20_results.ipynb 37
class KalmanImputation:
    name = "Kalman Filter"
    def __init__(self, model): store_attr()
    def __call__(self, item, dls):
        pred, targ = predict_items(self.model, dls=dls, items = [item])
        pred[0].mean[targ[0].mask] = targ[0].data[targ[0].mask]
        return pred[0].mean
    def preds_all(self, items, dls):
        return predict_items(self.model, dls=dls, items = items)
    def preds_all_loss(self, items, dls, var):
        return predict_items(self.model, dls=dls, items = items, metric_fn = PredictLossVar(only_gap=self.model.pred_only_gap, var = var))
    def preds_all_metrics(self, items, dls, metrics):
        return predict_items(self.model, dls=dls, items = items, metric_fn = metrics)

# %% ../../lib_nbs/20_results.ipynb 42
class KalmanImputationVar:
    name = "Kalman Filter"
    def __init__(self, models # dataframe with 2 columns `model` and `var`
                ): store_attr()
    def __call__(self, var, item, dls):
        model = self._select_model(var)
        pred, targ = predict_items(model, dls=dls, items = [item])
        pred[0].mean[targ[0].mask] = targ[0].data[targ[0].mask]
        return pred[0].mean
    def _select_model(self, var):
        return self.models[self.models['var'] == var].model.iloc[0]
    def preds_all(self, var:str, items:list, dls):
        model = self._select_model(var)
        return predict_items(model, dls=dls, items = items)

# %% ../../lib_nbs/20_results.ipynb 48
import rpy2.robjects
from rpy2.robjects import r
import rpy2.robjects as ro
from rpy2.robjects.packages import importr
from rpy2.robjects import pandas2ri

# %% ../../lib_nbs/20_results.ipynb 50
path_r = str(here("R/REddyProc_tools.R"))

r.source(path_r);

# %% ../../lib_nbs/20_results.ipynb 51
def importr_install(pkg):
    try:
        importr(pkg)
    except:
        utils = importr('utils')
        utils.chooseCRANmirror(ind=1)
        utils.install_packages(pkg)
        importr(pkg) 

# %% ../../lib_nbs/20_results.ipynb 52
def setupR():
    importr_install('tidyverse')
    importr_install('REddyProc')
    importr('lubridate')
    path_r = str(here("R/REddyProc_tools.R"))
    r.source(path_r) # R functions
    r("""toR_timestamp <- function(x){
   x$TIMESTAMP_END = as_datetime(x$TIMESTAMP_END) 
    x
     }""")

# %% ../../lib_nbs/20_results.ipynb 53
def pd2R(x):
    with ro.default_converter + pandas2ri.converter:
        return ro.conversion.py2rpy(x) 

def R2pd(x):
    with ro.default_converter + pandas2ri.converter:
        return ro.conversion.rpy2py(x) 

# %% ../../lib_nbs/20_results.ipynb 54
setupR() #start the R process and load depenencies

# %% ../../lib_nbs/20_results.ipynb 58
def add_buffer(index, inner_index, n):
    """Adds  a buffer of after and after index so length is at least """
    start = int(np.argwhere(index == inner_index[0]).squeeze())
    end = int(np.argwhere(index == inner_index[-1]).squeeze())
    start = start - n //2
    end = end + n//2
    if start < 0:
        end += -start
        start = 0
    if end > len(index):
        start -= end - len(index)
        end = len(index)
    
    index = index[start:end]
    
    assert len(index) > n
    
    return index

# %% ../../lib_nbs/20_results.ipynb 60
def item2REddy(item, var, df):
    " Add context around item for supporting REddyProc"
    index = add_buffer(df.index, item.data.index, 90 * 24 * 2)
    REddy_df = df.loc[index].assign(gap = (~item.mask[var]).astype(int)).fillna({'gap': 0})
    return REddy_df.reset_index().astype({'time': str}).rename(columns={'time': 'TIMESTAMP_END'})

# %% ../../lib_nbs/20_results.ipynb 66
def gap_fill_item(item, REddy_df, var, filled):
    
    filled = filled.set_index(pd.to_datetime(REddy_df.TIMESTAMP_END))
    filled_item = filled.loc[item.data.index]

    pred = item.data.copy()
    pred.loc[~item.mask[var], var] = filled_item[f"{var}_f"][~item.mask[var]]
    return pred

# %% ../../lib_nbs/20_results.ipynb 69
class MDSImputation:
    name = "MDS"
    def __init__(self, var, df):
        store_attr()
        self.out = io.StringIO()
    def __call__(self, item):
        REddy_df = item2REddy(item, self.var, self.df)
        REddy_df_r = r.toR_timestamp(pd2R(REddy_df))
        with redirect_stderr(self.out):
            filled = R2pd(r.fill_gaps_EProc(REddy_df_r, self.var))
        return gap_fill_item(item, REddy_df, self.var, filled)

# %% ../../lib_nbs/20_results.ipynb 73
class ERAImputation:
    name = "ERA-I"
    def __call__(self, item):
        pred = item.control.copy()
        names = [col for col in pred.columns if not col.endswith("_lag_1")]
        pred = pred.filter(names)
        pred = pred.rename(columns=lambda x: x.replace("_ERA", ""))
        # columns that cannot be predicted get a NA        
        for col in item.data.columns:
            if col not in pred.columns:
                pred[col] = np.nan 
        return pred

# %% ../../lib_nbs/20_results.ipynb 78
class MaskedMetric:
    def __init__(self, metric): store_attr()
    def __call__(self, targ, pred):
        if isinstance(pred, NormalsDf): pred = pred.mean
        row_sel, col_sel = ~targ.mask.all(1), ~targ.mask.all(0)
        assert not targ.mask.loc[row_sel,col_sel].any().all() # gap is a rectangle
        data, pred = targ.data.loc[row_sel,col_sel], pred.loc[row_sel,col_sel]
        return self.metric(data, pred) if not np.isnan(pred).all().all() else np.array([np.nan])

# %% ../../lib_nbs/20_results.ipynb 79
from sklearn.metrics import mean_squared_error

# %% ../../lib_nbs/20_results.ipynb 80
def rmse(y_true, y_pred):
    return np.sqrt(mean_squared_error(y_true, y_pred, multioutput='raw_values'))

# %% ../../lib_nbs/20_results.ipynb 81
def normalize(x, mean, std): return (x - mean) / std 
class NormalizedMetric:
    def __init__(self, metric: MaskedMetric, mean, std):
        self.mean = np.array(mean)
        self.std = np.array(std)
        self.metric = metric
    def __call__(self, targ, pred, var:int|None = None):
        targ = targ.copy()
        norm_conf = (self.mean if var is None else self.mean[var], self.std if var is None else self.std[var])
        targ.data = normalize(targ.data, *norm_conf)
        if isinstance(pred, NormalsDf): pred = pred.mean
        pred = normalize(pred, *norm_conf)
        return self.metric(targ, pred)

# %% ../../lib_nbs/20_results.ipynb 82
rmse_mask = MaskedMetric(rmse)

# %% ../../lib_nbs/20_results.ipynb 93
import random
import polars as pl
from tqdm.auto import tqdm

# %% ../../lib_nbs/20_results.ipynb 95
def format_gap_len(
    gap_len: int # gap length in num observations (30 mins)
):
    """Nice formatting for gap lengths"""
    gap_h = round(gap_len / 2) # to hours
    if gap_h < 24:
        return f"{gap_h} h"
    elif gap_h < 24 * 7: # days
        gap_d = round(gap_h / 24)
        label = "days" if gap_d > 1 else "day"
        return f"{gap_d} {label} ({gap_h} h)"
    else: # weeks
        gap_w = round(gap_h / (24 * 7))
        label = "weeks" if gap_w > 1 else "week"
        return f"{gap_w} {label} ({gap_h} h)"

# %% ../../lib_nbs/20_results.ipynb 97
var_type = CategoricalDtype(categories=['TA', 'SW_IN', 'LW_IN', 'VPD', 'WS', 'PA', 'P', 'SWC', 'TS'], ordered=True)

method_type = CategoricalDtype(categories=["Kalman Filter", "ERA-I", "MDS"], ordered=True)

# %% ../../lib_nbs/20_results.ipynb 98
def _as_category(df: pd.DataFrame):
    # print([format_gap_len(g) for g in np.sort(df.gap_len.unique())])
    df = df.assign(
        var = df['var'].astype(var_type),
        gap_len_f = df['gap_len_f'].astype(CategoricalDtype(categories = [format_gap_len(g) for g in np.sort(df.gap_len.unique())], ordered=True)))
    if 'method' in df.columns: df = df.assign(method = df['method'].astype(method_type))
    return df.sort_values(['var', 'gap_len', 'method'] if 'method' in df.columns else ['var', 'gap_len'] )

# %% ../../lib_nbs/20_results.ipynb 99
def prep_df(df): 
    df = df.assign(gap_len_f = df.gap_len.apply(format_gap_len))
    df =  _as_category(df)
    return df.assign(gap_len = df.gap_len // 2) # need to do after category conversion

# %% ../../lib_nbs/20_results.ipynb 104
def timeseriesAgg(targ, pred, *args): return {'pred': [pred], 'targ': [targ]}

class RMSEAgg:
    """Aggregate to rmse and normalized rmse"""
    def __init__(self, df):
        self.std = df.std(axis=0)
    def __call__(self, targ, pred, var):
        rmse = rmse_mask(targ, pred).item()
        rmse_stand = rmse / self.std[var]
        return {'rmse': rmse,'rmse_stand': rmse_stand,}

# %% ../../lib_nbs/20_results.ipynb 106
class ImpComparison():
    def __init__(self, models: pd.DataFrame, df, control, block_len, rmse=True, time_series = False):
        store_attr()
        self.k_imp = KalmanImputationVar(models)
        self.era_imp = ERAImputation()
        self.mds_imp = MDSImputation("", df)
        self.methods = [self.k_imp, self.era_imp, self.mds_imp]
        aggrs = []
        if rmse: aggrs.append(RMSEAgg(df))
        if time_series: aggrs.append(timeseriesAgg) 
        self.aggrs = aggrs
        
    def _compare_single(self, gap_len, var, n_rep):
        """Compares `n_rep` times the imputation methods, for gap in `var` with len `gap_len`"""
        dls = imp_dataloader(self.df, self.control, var_sel = var, gap_len=gap_len, block_len=self.block_len, control_lags = [1], n_rep=1, bs=1).cpu()
        self.mds_imp.var = var
        
        outs = []
        for i in tqdm(range(n_rep), leave=False):
            item = random.choice(dls.items)
            pred_k, targ = self.k_imp.preds_all(var = var, items = [item], dls=dls)
            pred_k, targ = pred_k[0], targ[0]
            for imp in self.methods:
                pred = imp(targ) if imp is not self.k_imp else pred_k
                out = {
                    'method': imp.name,
                    'var': var,
                    'gap_len': gap_len,
                    'idx_rep': i,
                }
                for aggr in self.aggrs:
                    out = out | aggr(targ, pred, var)
                outs.append(out)
        return pd.DataFrame(outs)
    
    def compare(self, gap_len, var, n_rep, raw=False):
        """Compare imputation performance for all combination of parameters"""
        arg_sets = list(product_dict(gap_len=tuplify(gap_len), var=tuplify(var)))
        out = []
        for arg_set in tqdm(arg_sets):
            out.append(self._compare_single(**arg_set, n_rep=n_rep))
        return prep_df(pd.concat(out)) if not raw else pd.concat(out)
        

# %% ../../lib_nbs/20_results.ipynb 107
base_path = here("analysis/results/trained_models")
def l_model(x, base_path=base_path): return torch.load(base_path / x)

# %% ../../lib_nbs/20_results.ipynb 115
class KalmanImpComparison():
    """Compare different Kalman filters"""
    def __init__(self,
                 models: pd.DataFrame, # model, gap_single_var, 
                 df: pd.DataFrame,
                 control: pd.DataFrame,
                 block_len:int,
                 rmse:bool=True,
                 time_series:bool = False):
        store_attr()
        self.imps = models.assign(imp = models.model.map(lambda model: KalmanImputation(model)))
        self.columns = list(df.columns)
        aggrs = []
        if rmse: aggrs.append(RMSEAgg(df))
        if time_series: aggrs.append(timeseriesAgg) 
        self.aggrs = aggrs
        
    def _compare_single(self, n_rep:int, gap_len:int, var:list[str]):
        """Compares `n_rep` times the imputation methods, for gap in `var` with len `gap_len`"""
        outs = []
        imps = imps = self.imps[self.imps['var'] == var] if 'var' in self.imps.columns else self.imps
        
       
        dls = imp_dataloader(self.df, self.control,
                                 var_sel = var,
                                 gap_len=gap_len, block_len=self.block_len, control_lags = [1], n_rep=1, bs=1,
                                 shifts = gen_shifts(50),
                                ).cpu()

        items_orig = random.choices(dls.items, k=n_rep)
             
        for (_,imp) in imps.iterrows():
            
            if not ( imp.gap_single_var if hasattr(imp, 'gap_single_var') else True):
                items = [MeteoImpItem(i = i.i, shift = i.shift, var_sel = self.columns, gap_len = i.gap_len) for i in items_orig]
            else:
                items = items_orig.copy()
            

            var_idx = _index_var(self.df, [var])[0]
            metrics_fn = MultiMetrics(loss = PredictLossVar(only_gap=True, var = var_idx), likelihood = PredictLikelihoodVar(only_gap=True, var = var_idx) )

            for i in range(n_rep):
                pred, targ, metric = imp.imp.preds_all_metrics(items = [items[i]], dls=dls, metrics=metrics_fn)
                pred, targ = pred[0], targ[0]
                pred = pred.mean.iloc[:, [var_idx]]
                targ = MeteoImpDf(targ.data.iloc[:, [var_idx]], targ.mask.iloc[:, [var_idx]], targ.control.iloc[:, [var_idx]])
                out = {
                    'var': var,
                    'loss': metric['loss'][0].item(),
                    'likelihood': metric['likelihood'][0].item(),
                    'gap_len': gap_len,
                    'idx_rep': i,
                } | imp.drop(index=["model", "imp"]).to_dict()
                for aggr in self.aggrs:
                    out = out | aggr(targ, pred, var)
                outs.append(out)
        return pd.DataFrame(outs)
    
    def compare(self, n_rep:int, gap_len:list[int], var:list[list[str]]):
        """Compare imputation performance for all combination of parameters"""
        arg_sets = list(product_dict(gap_len=tuplify(gap_len), var=tuplify(var)))
        out = []
        for arg_set in tqdm(arg_sets):
            out.append(self._compare_single(**arg_set, n_rep=n_rep))
        return prep_df(pd.concat(out))
        

# %% ../../lib_nbs/20_results.ipynb 119
from .training import _index_var

# %% ../../lib_nbs/20_results.ipynb 124
import altair as alt

# %% ../../lib_nbs/20_results.ipynb 126
def facet_wrap(data: pd.DataFrame, # full dataset
               plot_fn,# function that makes the plot, takes 2 arguments: data and y_label
               col: str, # column to facet
               y_labels: list[str]|None =None, # custom labels y axis 
               n_cols=3,
               y_resolve='independent'
              ):
    col_vals = data[col].unique()
    plot_list = [alt.hconcat() for _ in range(0, len(col_vals), n_cols)]
    for i, col_v in enumerate(col_vals):
        plot = plot_fn(data[data[col]==col_v].copy(),
                       y_labels[i] if y_labels is not None else col_v
                      ).properties(title=str(col_v))
        plot_list[i // n_cols] |= plot
    return alt.vconcat(*plot_list).resolve_scale(xOffset='independent')#.resolve_scale(
        #y=y_resolve
    #)
    

# %% ../../lib_nbs/20_results.ipynb 127
def facet_grid(data: pd.DataFrame, # full dataset
               plot_fn,# function that makes the plot, takes 2 arguments: data and y_label
               col: str, # column to facet,
               row: str,
               y_labels: list[str]|None = None, # custom labels y axis
              ):
    row_vals = data[row].unique()
    n_cols = len(data[col].unique())
    plots = []
    for row_val, y_label in zip_longest(row_vals, listify(y_labels)):
        plot = facet_wrap(data[data[row]==row_val].copy(), plot_fn, col, [y_label]*n_cols, n_cols=n_cols).properties(title=row_val)
        plots.append(plot)
    return alt.vconcat(*plots)

# %% ../../lib_nbs/20_results.ipynb 134
method_scale = alt.Scale(domain=["Kalman Filter", "ERA-I", "MDS"], scheme='dark2')
meteo_scale = alt.Scale(domain = ['TA', 'SW_IN', 'LW_IN', 'VPD', 'WS', 'PA', 'P', 'SWC', 'TS'], scheme='dark2')

# %% ../../lib_nbs/20_results.ipynb 135
def _get_labels(data, y, y_labels):
    """Get optimal labels depending on the `y`"""
    if y_labels is None:
        if y == "rmse_stand": return [f"Standardized RMSE" for var in data['var'].unique()]
        elif y == "rmse": return [f"RMSE {var} [{units_big[var]}]" for var in data['var'].unique()]
        elif y == "mean": return [f"{var} [{units_big[var]}]" for var in data['var'].unique()]
        else: return [y for var in data['var'].unique()]
    else:
        return y_labels

# %% ../../lib_nbs/20_results.ipynb 136
@patch
def pipe(self: alt.Chart|alt.VConcatChart|alt.HConcatChart, f: Callable):
    """applies `f` to `self`"""
    return f(self)

@dataclass
class PlotFormatter():
    """Format altair plot by setting font sizes/legend position """
    font_size: int = 18
    legend_font_size: int = 18 
    title_font_size: int = 20
    legend_label_limit = 300
    legend_symbol_size = 150
    def __call__(self, plot: alt.Chart):
        return (plot
            .configure_legend(orient="bottom", labelFontSize=self.font_size, titleFontSize=self.legend_font_size)
            .configure_axis(labelFontSize=self.font_size, titleFontSize=self.font_size )
            .configure_title(fontSize=self.title_font_size))
    
    @property
    def color_legend(self):
        """Settings for color legend"""
        return alt.Legend(labelLimit=self.legend_label_limit, symbolSize=self.legend_symbol_size)
    
plot_formatter = PlotFormatter()

# %% ../../lib_nbs/20_results.ipynb 141
def _the_plot(data, y_label='rmse', y = 'rmse'):
    xoffset_domain = ["Kalman Filter", "ERA-I", "MDS"] 
    return alt.Chart(data).mark_boxplot(extent="min-max").encode(
        x = alt.X('gap_len:N', title='Gap length [h]', axis=alt.Axis(labelAngle=0)),
        y = alt.Y(y, title=y_label, axis=alt.Axis(grid=True)),
        color=alt.Color('method:N', title = "Method", scale=method_scale, legend=plot_formatter.color_legend),
        xOffset=alt.XOffset('method', scale=alt.Scale(domain=xoffset_domain)),
        # column=alt.Column('var')
    ).properties(width=250, height=200)

# %% ../../lib_nbs/20_results.ipynb 142
def the_plot(data):
     return (facet_wrap(data, _the_plot, "var",
                       y_labels = [f"RMSE {var} [{units_big[var]}]" for var in data['var'].unique()])
            .pipe(plot_formatter))

# %% ../../lib_nbs/20_results.ipynb 144
def the_plot_stand(data):
    # data = data.query("method == 'KalmanFilter'")
    return alt.Chart(data).mark_boxplot(extent="min-max").encode(
        x = alt.X('var', title='Variable', axis=alt.Axis(labelAngle=0)),
        y = alt.Y('rmse_stand', title="Standardized RMSE", axis=alt.Axis(grid=True)),
        color=alt.Color('method', title="Method", scale=method_scale, legend=plot_formatter.color_legend),
        xOffset=alt.XOffset('method:N', scale= alt.Scale(domain=method_scale.domain)),
    ).properties(width=600, height=300)#.pipe(plot_formatter)

# %% ../../lib_nbs/20_results.ipynb 146
def the_plot_stand2(data):
     return _the_plot(data, y='rmse_stand', y_label="Standardized RMSE").facet(alt.Row('var',sort=list(var_type.categories)) , columns=3)

# %% ../../lib_nbs/20_results.ipynb 154
def custom_boxplot_nooutlier(data: pd.DataFrame,x:alt.X,y:alt.Y, color:alt.Color, xOffset:alt.XOffset):
    data = data.groupby(['var', 'method']).agg(
        median = pd.NamedAgg(y.shorthand, 'median'),
        q1 = pd.NamedAgg(y.shorthand,lambda x: x.quantile(.25)),
        q3 = pd.NamedAgg(y.shorthand,lambda x: x.quantile(.75))).reset_index().astype({'var': str})
    y_label= 'Standaridized RMSE'
    bar = alt.Chart(data).mark_bar(size=14).encode(alt.Y('q1', title=y_label), alt.Y2('q3', title=y_label), x, color, xOffset)
    tick = alt.Chart(data).mark_tick(color='white', size=14).encode(alt.Y('median'), x, xOffset)
    return bar + tick

# %% ../../lib_nbs/20_results.ipynb 155
def the_plot_stand3(data):
    return custom_boxplot_nooutlier(data,
                                    alt.X('var:N', title='variable',axis=alt.Axis(labelAngle=0), scale=alt.Scale(domain=meteo_scale.domain)),
                                    alt.Y('rmse_stand'),
                                    alt.Color('method:N', scale=method_scale),
                                    alt.XOffset('method', )).properties(width=600)

# %% ../../lib_nbs/20_results.ipynb 163
def agg_gap_len(data):
    return data.groupby(["var", "gap_len"]).agg({'rmse': [
        'median',
        ("Q1", lambda x: x.quantile(.25)),
        ("Q3", lambda x: x.quantile(.75))]}).droplevel(0, axis=1).reset_index()

# %% ../../lib_nbs/20_results.ipynb 167
def _get_era_rmse(df, control):
    """Average RMSE for ERA"""
    names = [col for col in control.columns if not col.endswith("_lag_1")]
    control = control.copy().filter(names)
    control = control.rename(columns=lambda x: x.replace("_ERA", "")).loc[df.index]
    rmse_df = np.sqrt((df[control.columns] - control).pow(2).mean(axis=0))
    rmse_df = rmse_df.to_frame().reset_index()
    rmse_df.columns = ["var", "era_rmse"] 
    return rmse_df.astype({'var': var_type})

# %% ../../lib_nbs/20_results.ipynb 172
def _plot_gap_len(data, y_label):
    median = alt.Chart(data).mark_line().encode(
        x = alt.X('gap_len', title="Gap length [h]", axis=alt.Axis(labelAngle=0)),
        y = alt.Y('median', title=y_label),
        color=alt.Color('var', scale=meteo_scale)
    ).properties(width=250, height=200)
    Qs = alt.Chart(data).mark_errorband().encode(x = 'gap_len', y = alt.Y('Q1', title=y_label), y2= 'Q3', color='var')
    # min = alt.Chart(gap_len_agg).mark_point().encode(x = 'gap_len', y = 'min', color='var')
    # max = alt.Chart(gap_len_agg).mark_point().encode(x = 'gap_len', y = 'max', color='var')
    plot = (median + Qs)
    if not np.isnan(data.era_rmse.iloc[0]): plot += alt.Chart().mark_rule(strokeDash=[2,4]).encode(y=alt.datum(data.era_rmse.iloc[0]))

    return plot

# %% ../../lib_nbs/20_results.ipynb 175
def plot_gap_len(data, df, control):
    data = agg_gap_len(data)
    data = pd.merge(data, _get_era_rmse(df, control), on='var', how='left')
    return (facet_wrap(data, _plot_gap_len, 'var',
                       y_labels = [f"RMSE {var} [{units_big[var]}]" for var in data['var'].unique()])
            .pipe(plot_formatter))

# %% ../../lib_nbs/20_results.ipynb 179
def _plot_compare(data, y_label='rmse', compare:str="", y = "rmse_stand", scale_domain=None):
    domain = ifnone(scale_domain, data[compare].unique())
    return alt.Chart(data).mark_boxplot(extent="min-max").encode(
        x = alt.X('gap_len:N', title='Gap length [h]', axis=alt.Axis(labelAngle=0)),
        y = alt.Y(y, title=y_label, scale= alt.Scale(zero=False)),
        color=alt.Color(compare, scale=alt.Scale(domain = domain, scheme='accent'),legend=plot_formatter.color_legend),
        xOffset=alt.XOffset(compare, scale=alt.Scale(domain = domain)),
        # column=alt.Column('var')
    ).properties(width=250, height=200)

# %% ../../lib_nbs/20_results.ipynb 180
def plot_compare(data: pd.DataFrame,
                 compare: str,
                 y:str = "rmse_stand",
                 scale_domain: Sequence|None = None,
                 y_labels:Sequence|None = None
                ) -> alt.Chart:
    y_labels = _get_labels(data, y, y_labels) 
    return facet_wrap(data, partial(_plot_compare, compare=compare, scale_domain=scale_domain),
                       "var", y_labels = y_labels
                      ).pipe(plot_formatter)

# %% ../../lib_nbs/20_results.ipynb 196
def unnest_predictions(row_res: pd.Series, ctx_len:int=50):
    """Unnest predictions/target for each gap to plot timeseries """
    pred = row_res.pred[0]
    targ =  row_res.targ[0]
    var = row_res['var']
    if isinstance(pred, NormalsDf):
        mean = pred.mean[var]
        std = pred.std[var]
    else:
        mean = pred[var]
        std = np.nan
    
    
    measurement = targ.data[var]
    is_present = targ.mask[var]
    
    gap_len = (~is_present).sum()
    gap_start = np.argmin(is_present)
    ctx_start = is_present.index[gap_start - (ctx_len - gap_len) //2]
    ctx_end = is_present.index[gap_start + gap_len + (ctx_len - gap_len) //2]
    
    is_present = is_present[ctx_start:ctx_end]
    measurement = measurement[ctx_start:ctx_end]
    mean = mean[ctx_start:ctx_end]
    if type(std) != float: std = std[ctx_start:ctx_end] 
    
    mean[is_present] = np.nan # plot only predictions in gap
    
    other_cols = {name: row_res[name] for name in list(row_res.index) if name not in ['pred', 'targ']}
    
    out =  pd.DataFrame({'mean': mean, 'std': std, 'measurement': measurement, 'is_present': is_present} | other_cols)
    return out.reset_index()
    

# %% ../../lib_nbs/20_results.ipynb 199
from .training import def_selection, plot_points, plot_line, plot_error

# %% ../../lib_nbs/20_results.ipynb 204
def _plot_timeseries(data_plot, y_label="", scale_color=method_scale, compare = 'method', err_band=True):
    """data for one variable and one gap"""
    data_measure = data_plot[data_plot[compare] == data_plot[compare].unique()[0]]
    
    p = [plot_points(data_measure, y= "measurement", y_label=y_label)]
    p.append(plot_missing_area(data_measure))
    if err_band: p.append(plot_error(data_plot, y= "mean", color=compare, scale=scale_color, y_label=y_label))
    p.append(plot_line(data_plot, y= "mean", color=compare,
                     color_title = "Method",   
                     scale=scale_color, y_label=y_label, props={'height': 200, 'width': 300}))
    return alt.layer(*p)

# %% ../../lib_nbs/20_results.ipynb 208
def plot_timeseries(data, idx_rep:int|None=None, gap_len:int|None = None, max_idx:int = 3,
                    ctx_len={6.: 50, 12.: 50, 168.: 336+48},
                    scale_color=method_scale, compare='method'):
    
    if idx_rep == 'random': idx_rep = int(data['idx_rep'].sample())
    if gap_len is None and idx_rep is not None:
        data_plot = data.query(f'idx_rep == {idx_rep}').copy()
        facet_var = 'gap_len_f'
    elif gap_len is not None and idx_rep is None:
        data_plot = data.query(f'gap_len == {gap_len} and idx_rep < {max_idx}').copy()
        facet_var = 'idx_rep'
    else:
        raise ValueError(f"One and only one of idx_rep, gap_len should be None. got {idx_rep}, {gap_len}")
    data_plot = pd.concat([unnest_predictions(row, ctx_len[row.gap_len]) for _, row in data_plot.iterrows()])
    data_plot = data_plot.astype({'idx_rep': str, 'gap_len_f': str})
    data_plot['gap_len_f'] = data_plot['gap_len_f'].apply(lambda x: "Gap " + x)
    y_labels = _get_labels(data, 'mean', None)
    return (facet_grid(data_plot, partial(_plot_timeseries, scale_color=scale_color, compare=compare),
                      row="var", col=facet_var, y_labels=y_labels)
            .pipe(plot_formatter))
        
    

# %% ../../lib_nbs/20_results.ipynb 211
def _plot_scatter(df, only_present=True, x = "value", y="mean", x_label="", y_label = "", color = 'method', scale=method_scale, props = {}):
    # df = df[df.is_present] if only_present else df
    # TODO remove onle_present
    return alt.Chart(df).mark_point().encode(
        x = alt.X(x, title=x_label),    
        y = alt.Y(y, title = y_label),
        color=alt.Color(color, scale= scale),
        shape = color
    ).properties(
        **props
    )

    

# %% ../../lib_nbs/20_results.ipynb 220
def highlight_min_method(row, props, cols): 
    # select even columns that are the mean
    return np.where(row == np.min(row.iloc[cols]), props, '')

def style_the_table(style, cols=[0,2,4]):
    return (style.apply(highlight_min_method, props="font-weight: bold", cols=cols, axis=1)
                .format_index(precision=0).format(precision=3, na_rep='-'))

# %% ../../lib_nbs/20_results.ipynb 222
renames_table_latex = {name: f"\\parbox{{2.1cm}}{{{val}}}" for name, val in 
                 {'SW_IN': "\\textbf{SW\\_IN} [\\si{W/m^2}]",
               'LW_IN': '\\textbf{LW\\_IN} [\\si{W/m^2}]',
               'TA': "\\textbf{TA} [\\si{°C}]",
               'VPD': "\\textbf{VPD} [\\si{hPa}]",
               'PA': "\\textbf{PA} [\\si{hPa}]",
               'P': "\\textbf{P} [\\si{mm}]",
               'WS': "\\textbf{WS} [\\si{m/s}]",
               'TS': "\\textbf{TS} [\\si{°C}]",
               'SWC': "\\textbf{SWC} [\\si{\%}]",
          }.items()}

# %% ../../lib_nbs/20_results.ipynb 223
renames_table_latex_stand = {'SW_IN': "\\textbf{SW\\_IN}",
               'LW_IN': '\\textbf{LW\\_IN}',
               'TA': "\\textbf{TA}",
               'VPD': "\\textbf{VPD}",
               'PA': "\\textbf{PA}",
               'P': "\\textbf{P}",
               'WS': "\\textbf{WS}",
               'TS': "\\textbf{TS}",
               'SWC': "\\textbf{SWC}",
          }

# %% ../../lib_nbs/20_results.ipynb 228
from fastcore.basics import noop

# %% ../../lib_nbs/20_results.ipynb 230
err_type = CategoricalDtype(categories=["mean", "std", "se", "diff."], ordered=True)
err_type_rev = CategoricalDtype(categories=["se", "std", "mean", "diff."], ordered=True)

# %% ../../lib_nbs/20_results.ipynb 231
def the_table(data, y='rmse', y_name="RMSE"):
    data = data.groupby(['method', 'var', 'gap_len_f']).agg({y: ['mean', 'std']}).unstack(level=0)

    data_cols = data.columns.droplevel()
    data_cols.names = [y_name, None]
    data_cols = pd.MultiIndex.from_frame(data_cols.to_frame().astype({y_name: err_type}))
    data_cols.names = [y_name, None]
    data.columns = data_cols
    
    data.index.names = ["Variable", "Gap"]
        
    return data.sort_index(axis=1, level=1).swaplevel(axis=1)   

# %% ../../lib_nbs/20_results.ipynb 233
def the_table_latex(table, file, caption="", label="", stand=False):
    renames = renames_table_latex if not stand else renames_table_latex_stand
    styled = table.rename(index = renames).style.pipe(style_the_table).format(na_rep="-", precision=3)
    latex = styled.to_latex(convert_css=True, hrules=True, clines="skip-last;data",
                            column_format="p{2.1cm}l|rr|rr|rr", caption=caption, label=label, position_float="centering")
    with open(file, 'w') as f:
        f.write(latex)
    return file

# %% ../../lib_nbs/20_results.ipynb 236
def table_compare(data, compare:str, y = 'rmse_stand', compare_ascending=True):
    data = data.groupby([compare, 'var', 'gap_len_f']).agg({y: ['mean', 'std', ('se', 'sem')]}).unstack(level=0).droplevel(level=0, axis=1)
    
    data["diff."] = (data.iloc[:, 0] - data.iloc[:, 1])
    
    data_cols = data.columns
    data_cols.names = ['Stand. RMSE', compare]
    # support custom sorting order
    data.columns = pd.MultiIndex.from_frame(data_cols.to_frame().astype({'Stand. RMSE': err_type_rev}))
    data.index.names = ["Variable", "Gap"]
    return data.sort_index(axis=1, level=1, ascending=False).swaplevel(axis=1) 

# %% ../../lib_nbs/20_results.ipynb 238
def table_compare_latex(table, file, caption="", label=""):
    styled = table.rename(index = renames_table_latex_stand).style.pipe(partial(style_the_table, cols=[0,3]))
    latex = styled.to_latex(convert_css=True, hrules=True, clines="skip-last;data",
                            column_format="p{2.1cm}l|rrr|rrr|r", caption=caption, label=label, position_float="centering")
    with open(file, 'w') as f:
        f.write(latex)
    return file

# %% ../../lib_nbs/20_results.ipynb 241
def table_compare3(data, compare:str, y = 'rmse_stand', compare_ascending=True):
    data = data.groupby([compare, 'var', 'gap_len_f']).agg({y: ['mean', 'std']}).unstack(level=0).droplevel(level=0, axis=1)
    
    data_cols = data.columns
    data_cols.names = ['Stand. RMSE', compare]
    data.index.names = ["Variable", "Gap [$h$]"]
    return data.sort_index(axis=1, level=1, ascending=True).swaplevel(axis=1) 

# %% ../../lib_nbs/20_results.ipynb 242
def table_compare3_latex(table, file, caption="", label=""):
    styled = table.rename(index = renames_table_latex_stand).style.pipe(partial(style_the_table, cols=[0,2,4]))
    latex = styled.to_latex(convert_css=True, hrules=True, clines="skip-last;data",
                            column_format="p{2.1cm}l|rr|rr|rr", caption=caption, label=label, position_float="centering")
    with open(file, 'w') as f:
        f.write(latex)
    return file

# %% ../../lib_nbs/20_results.ipynb 247
def table_gap_len(data, y = 'rmse_stand'):
    t = (data
         .groupby(['var', 'gap_len_f']).agg({y: ['mean', 'std']})
        .droplevel(level=0, axis=1)
         .reset_index()
         .melt(id_vars=['var', 'gap_len_f'], var_name='rmse_stand')
         .pivot(index = ['var', y], columns=['gap_len_f'])
         .droplevel(level=0, axis=1)
        ) 
    
    t.columns.names = ["Gap"]
    t.index.names = ("Variable", "Stand. RMSE")
    
    return t.sort_index(axis=1, level=1)

# %% ../../lib_nbs/20_results.ipynb 249
def table_gap_len_latex(table, file, caption="", label=""):
    # table.columns = [f"{col:.0f}" for col in list(table.columns)]
    styled = table.rename(index = renames_table_latex_stand).style.format(precision=3, na_rep='-')
    table_cols = '>{\\centering\\arraybackslash}p{0.07\\textwidth}' * len(table.columns)
    latex = styled.to_latex(convert_css=True, hrules=True, clines="skip-last;data",
                            column_format="lp{0.07\\textwidth}|" + table_cols, caption=caption, label=label, position_float="centering")
    with open(file, 'w') as f:
        f.write(latex)
    return file