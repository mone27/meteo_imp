# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/kalman/10_fastai.ipynb.

# %% auto 0
__all__ = ['rmse_mask', 'rmse_gap', 'multi_r2', 'r2_mask', 'r2_gap', 'imp_metrics', 'BlockIndexTransform', 'DataControl',
           'BlockDfTransform', 'gen_gap_len', 'gen_var_sel', 'as_generator', 'MeteoImpDf', 'AddGapTransform',
           'find_gap_limits', 'plot_missing_area', 'plot_points', 'facet_variable', 'MeteoImpTensor',
           'MeteoImpDf2Tensor', 'NormalsParams', 'get_stats', 'MeteoImpNormalize', 'ToTuple', 'imp_pipeline',
           'imp_dataloader', 'KalmanLoss', 'ImpMetric', 'SaveParams', 'Float64Callback', 'NormalsDf', 'preds2df',
           'predict_items', 'plot_result', 'plot_results', 'get_results', 'show_results', 'results_custom_gap',
           'interact_results']

# %% ../../lib_nbs/kalman/10_fastai.ipynb 3
from ..utils import *
from ..gaussian import *
from ..data import *

from fastcore.transform import *
from fastcore.basics import *
from fastcore.foundation import *
from fastcore.all import *
from fastai.tabular import *
from fastai.tabular.core import *
from fastai.data.core import *
from fastai.data import *
from fastai.torch_core import default_device, to_device
from dataclasses import dataclass

import torch

import collections

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# %% ../../lib_nbs/kalman/10_fastai.ipynb 10
from dominate.tags import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 11
@patch
def _repr_html_(self: Transform, as_str=True):
    with div() as out:
        p(strong(self.name))
        p(repr(self.encodes))
        p(repr(self.decodes))
    out = str(out) if as_str else out
    return out

# %% ../../lib_nbs/kalman/10_fastai.ipynb 12
@patch
def _repr_html_(self: TfmdLists):
    with div() as out:
        span("TfmdLists. Items:")
        pre(coll_repr(self.items))
        ol([li(f._repr_html_(as_str=False)) for f in self.fs], start="0")
    return str(out)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 15
class BlockIndexTransform(Transform):
    """divide timeseries DataFrame index into blocks"""
    def __init__(self, idx: pd.DatetimeIndex, block_len:int =200, offset=1):
        store_attr()
        self.n = len(idx)
        
    def encodes(self, i:int) -> pd.DatetimeIndex:       
        start = i * self.block_len + self.offset
        end = (i+1) * self.block_len + self.offset
        assert end <= self.n 
        
        return self.idx[start:end] 

# %% ../../lib_nbs/kalman/10_fastai.ipynb 22
@dataclass
class DataControl:
    data: pd.DataFrame
    control: pd.DataFrame
    def _repr_html_(self):
            return row_dfs({'data': self.data, 'control': self.control}, title="Data Control", hide_idx=False)
    def __iter__(self): return iter((self.data, self.control,))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 24
def _rename_lag(lag):
    def _inner(col_name):
        return f"{col_name}_lag_{lag}"
    return _inner

# %% ../../lib_nbs/kalman/10_fastai.ipynb 26
def _lag_df(df, lag):
    "add lagged columns"
    df_lag = df.shift(lag).rename(columns = _rename_lag(lag))
    return df_lag
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 28
def _add_lags_df(df, lags):
    df_lagged = df
    for lag in listify(lags):
        df_lagged = pd.merge(df_lagged, _lag_df(df, lag), left_index=True, right_index=True)
    return df_lagged

# %% ../../lib_nbs/kalman/10_fastai.ipynb 30
class BlockDfTransform(Transform):
    """divide timeseries DataFrame index into blocks"""
    def __init__(self, data: pd.DataFrame, control: pd.DataFrame, control_lags: int|Iterable[int]):
        store_attr()
        self.control = _add_lags_df(control, control_lags)
    def encodes(self, idx: pd.DatetimeIndex) -> DataControl:
        return DataControl(self.data.loc[idx], self.control.loc[idx])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 43
def _make_random_gap(
    gap_length: int, # The length of the gap
    total_length: int, # The total number of observations
    gap_start: Optional[int] = None # Optional start of gap
)-> np.ndarray: # [total_length] array of bools to indicicate if the data is missing or not
    "Add a continous gap of given length at random position"
    if(gap_length >= total_length):
        return np.repeat(True, total_length)
    gap_start = np.random.randint(total_length - gap_length) if gap_start is None else gap_start
    return np.hstack([
        np.repeat(False, gap_start),
        np.repeat(True, gap_length),
        np.repeat(False, total_length - (gap_length + gap_start))
    ])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 57
def gen_gap_len(mean: float, min_v = 1): 
    scale = mean*.6
    shape = mean/scale
    while True:
        yield max(int(np.random.gamma(scale=scale, shape=shape)), min_v)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 63
def gen_var_sel(vars):
    while True:
        n_var = np.random.randint(1,1+len(vars))
        yield np.random.choice(np.array(vars), size=n_var, replace=False)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 71
from collections.abc import Iterable, Generator

# %% ../../lib_nbs/kalman/10_fastai.ipynb 72
def as_generator(x: Generator|object):
    """Maybe convert iterable to generator"""
    if isinstance(x, Generator): return x
    else: return cycle((x,))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 76
class MeteoImpDf:
    def __init__(self,*args):
        self.data = args[0]
        self.mask = args[1]
        self.control = args[2]
    def __iter__(self): return iter((self.data, self.mask, self.control,))
    __repr__ = basic_repr("data, mask, control")
    def _repr_html_(self):
        return row_dfs({'data': self.data, 'mask': self.mask, 'control': self.control}, title="Meteo Imp Df", hide_idx=False)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 77
class AddGapTransform(Transform):
    """Adds a random gap to a dataframe"""
    def __init__(self,
                variables,
                gap_length,
                ):
        self.gen_var, self.gen_gap = as_generator(variables), as_generator(gap_length)
    def _yield_gens(self):
        self.variables, self.gap_length = next(self.gen_var), next(self.gen_gap)
        return self
    def encodes(self, dc: DataControl) -> MeteoImpDf:
        df, control = dc
        self._yield_gens()
        gap = _make_random_gap(self.gap_length, df.shape[0])
        mask = np.ones_like(df, dtype=bool)
        col_sel = L(*df.columns).argwhere(lambda x: x in self.variables)
        mask[np.argwhere(gap), col_sel] = False
        mask = pd.DataFrame(mask, index=df.index, columns=df.columns)
        return MeteoImpDf(df, mask, control)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 92
@patch
def tidy(self: MeteoImpDf):
    data = self.data.reset_index().melt("time")
    mask = self.mask.reset_index().melt("time", value_name="is_present")
    
    return pd.merge(data, mask, on=["time", "variable"])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 95
import altair as alt
from altair import datum

# %% ../../lib_nbs/kalman/10_fastai.ipynb 96
def def_selection():
    return alt.selection_interval(bind="scales")

# %% ../../lib_nbs/kalman/10_fastai.ipynb 98
def plot_rug(df, sel = def_selection(), props = {}):
    if 'height' in props:
        props = props.copy() 
        props.pop('height') # rug should have default heigth
    return alt.Chart(df).mark_tick(
            color='black',
        ).encode(
            x = "time",
            color = alt.condition(datum.is_present, alt.value('white'), alt.value('black'))
        ).add_params(
            sel
        ).properties(**props) 

# %% ../../lib_nbs/kalman/10_fastai.ipynb 111
def find_gap_limits(df):
    gap_starts, gap_ends = [], []
    for i in range(len(df)):
        prev = df.iloc[i-1].is_present if i>0 else True 
        _next = df.iloc[i+1].is_present if i<(len(df)-1) else True 
        curr = df.iloc[i]
        if not curr.is_present and prev: gap_starts.append(curr.time)
        if not curr.is_present and _next: gap_ends.append(curr.time)
    return pd.DataFrame({'gap_start': gap_starts, 'gap_end': gap_ends})
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 113
def plot_missing_area(df, sel = def_selection(), props={}):
    gap_limits = find_gap_limits(df)
    start = alt.Chart(gap_limits).mark_rule().encode(
        x = alt.X('gap_start', axis=alt.Axis(domain=False, labels = False, ticks=False, title=None)),
    )
    end = alt.Chart(gap_limits).mark_rule().encode(
        x = alt.X('gap_end', axis=alt.Axis(domain=False, labels = False, ticks=False, title=None))
    )
    area = alt.Chart(gap_limits).mark_rect(color='black', opacity=.15).encode(
        x = alt.X('gap_start', axis=alt.Axis(domain=False, labels = False, ticks=False, title=None)),
        x2 = 'gap_end'
    )
    return (start + end + area)#.add_params(sel).properties(**props)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 116
def plot_points(df, y = "value", y_label = "", sel = def_selection(), props = {}):
    return alt.Chart(df).mark_point(
            color='black',
            strokeWidth = 1,
            fillOpacity = 1
        ).encode(
            x = alt.X("time", axis=alt.Axis(domain=True, labels = True, ticks=True, title="time")),
            y = alt.Y(y, title = y_label, scale=alt.Scale(zero=False)),
            fill= alt.Fill("is_present", scale = alt.Scale(range=["black", "#ffffff00"]),
                           legend = alt.Legend(title =["Observed data"])),
            shape = "is_present",
        )

# %% ../../lib_nbs/kalman/10_fastai.ipynb 119
def plot_line(df, only_present=True, y="value", y_label = "", sel = def_selection(), props = {}):
    # df = df[df.is_present] if only_present else df
    # TODO remove onle_present
    return alt.Chart(df).mark_line().encode(
        x = "time",    
        y = alt.Y(y, title = y_label, scale=alt.Scale(zero=False)),
        color='variable'
    ).add_params(
        sel
    ).properties(
        **props
    )#.transform_filter(
    #     datum.is_present
    # )

    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 122
def plot_error(df, y = "value", y_label = "", sel = def_selection(), props = {}):
    df.loc[:,'err_low'] = df[y] - 2 * df['std']
    df.loc[:,'err_high'] = df[y] + 2 * df['std']
    return alt.Chart(df).mark_errorband().encode(
        x = "time",    
        y = alt.Y("err_low:Q", title = y_label, scale=alt.Scale(zero=False)),
        y2 = "err_high:Q",
        color=alt.Color("variable",
                        legend = alt.Legend(title=["Line: pred. mean", "area: +/- 2 std"])
                       )
    ).add_params(
        sel
    ).properties(
        **props
    )
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 125
def plot_variable(df, variable, ys=["value", "value"], title="", y_label="", sel = None, error=False, props = {}):
    df = df[df.variable == variable].copy()
    sel = ifnone(sel, def_selection())
    # rug = plot_rug(df, sel, props)
    points = plot_points(df, ys[0], y_label, sel, props)
    if not df.is_present.all(): points += plot_missing_area(df, sel, props) # there is a gap
    line = plot_line(df, True, ys[1], y_label, sel, props)
    if error: line = plot_error(df, y=ys[1], y_label=y_label, sel=sel, props=props) + line
    
    return (points + line).properties(title=title)
    
    # return alt.VConcatChart(vconcat=[(points + line), rug], spacing=-10).properties(title=title)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 129
def facet_variable(df, # tidy dataframe
                   n_cols: int = 3,
                   bind_interaction: bool =True, # Whether the sub-plots for each variable should be connected for zooming/panning
                   error:bool=False, # plot error bar
                   ys:list=["value", "value"],
                   props:dict|None = None, # additional properties for altair plot (eg. size)
                   ) -> alt.Chart:
    """Plot all values of the column `variable` in different subplots"""
    props = ifnone(props, {'width': 200, 'height': 150})
    vars = df.variable.unique()
    plot_list = [alt.hconcat() for _ in range(0, len(vars), n_cols)]
    selection_scale = alt.selection_interval(bind="scales", encodings=['x']) if bind_interaction else None
    for idx, variable in enumerate(vars):
        plot = plot_variable(df,
                            variable,
                            ys = ys,
                            title = variable,
                            y_label = variable,
                            sel = selection_scale,
                            props=props,
                            error=error)
        
        plot_list[idx // n_cols] |= plot
    
    plot = alt.vconcat(*plot_list)
    
    return plot

# %% ../../lib_nbs/kalman/10_fastai.ipynb 131
@patch
def show(self: MeteoImpDf, ax=None, ctx=None, 
        n_cols: int = 3,
        bind_interaction: bool =True, # Whether the sub-plots for each variable should be connected for zooming/panning
        props:dict = None # additional properties (eg. size) for altair plot
       ) -> alt.Chart:
    
    df = self.tidy()
    return facet_variable(df, n_cols, bind_interaction, props)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 137
class MeteoImpTensor(collections.abc.Sequence):
    def __init__(self,*args):
        if len(args)==3:
            self.data = args[0]
            self.mask = args[1]
            self.control = args[2]
        elif len(args)==1 and len(args[0])==2:
            self.data = args[0][0]
            self.mask = args[0][1]
        else:
            raise ValueError(f"Incorrect number of arguments. got {len(args)} args")

    def __iter__(self): return iter((self.data, self.mask,self.control))
    __len__ = 3
    def __getitem__(self, key):
        if key == 0: return self.data
        elif key == 1: return self.mask
        elif key == 2: return self.control
        else: raise IndexError("index bigger than 2")
    __repr__ = basic_repr('data, mask, control')
    def _repr_html_(self):
        return row_items(data = self.data, mask = self.mask, control = self.control)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 138
class MeteoImpDf2Tensor(Transform):
    def setups(self, items):
        self.columns = list(items[0].data.columns)
    def encodes(self, df: MeteoImpDf) -> MeteoImpTensor:
        data = torch.tensor(df.data.to_numpy())
        mask = torch.tensor(df.mask.to_numpy())
        control = torch.tensor(df.control.to_numpy())
        return MeteoImpTensor(data, mask, control)
        
    # def decodes(self, x: MeteoImpTensor) -> MeteoImpDf:
    #     data = pd.DataFrame(x.data.detach().cpu().numpy(), columns = self.columns)
    #     mask = pd.DataFrame(x.mask.cpu().numpy(), columns = self.columns)
    #     control = pd.DataFrame(x.control.cpu().numpy(), columns = self.columns)
    #     return MeteoImpDf(data, mask, control)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 149
from ..utils import *
from fastai.torch_core import to_cpu

from torch import Tensor

# %% ../../lib_nbs/kalman/10_fastai.ipynb 153
class NormalsParams(list):
    def __init__(self,*args):
        if len(args)==2:
            self.mean = args[0]
            self.std = args[1]
        elif isinstance(args[0], Generator):
            args = list(args[0])
            self.mean = args[0]
            self.std = args[1]
        elif len(args)==1 and len(args[0])==2:
            self.mean = tuple(args[0])[0]
            self.std = tuple(args[0])[1]                     
        else:
            raise ValueError(f"Incorrect number of arguments. got {len(args)} args")
    def __iter__(self): return iter((self.mean, self.std,))
    def __next__(self): return next(self.__iter__())
    def __len__(self): return 2
    def __getitem__(self, key):
        if key == 0: return self.mean
        elif key == 1: return self.std
        else: raise IndexError("index bigger than 2")
    __repr__ = basic_repr('mean, std')

# %% ../../lib_nbs/kalman/10_fastai.ipynb 155
def get_stats(df, repeat=1, device='cpu'):
    return torch.tensor(df.mean(axis=0).to_numpy(), device=device).repeat(repeat), torch.tensor(df.std(axis=0).to_numpy(), device=device).repeat(repeat)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 156
class MeteoImpNormalize(Transform):
    "Normalize/denorm MeteoImpTensor column-wise "
    @property
    def name(self): return f"{super().name} -- {getattr(self,'__stored_args__',{})}"

    def __init__(self, mean_data, std_data, mean_control, std_control): store_attr()

    def encodes(self, x:MeteoImpTensor)-> MeteoImpTensor:
        return MeteoImpTensor((x.data -self.mean_data) / self.std_data, x.mask, (x.control - self.mean_control)/self.std_control)

    def decodes(self, x:MeteoImpTensor)->MeteoImpTensor:
        f = partial(to_device, device=(x[0].device))
        return MeteoImpTensor(x.data * f(self.std_data) + f(self.mean_data), x.mask, x.control * f(self.std_control) + f(self.mean_control))
    
    def decodes(self, x:NormalsParams):
        f = partial(to_device, device=(x[0].device))
        mean = x.mean * f(self.std_data) + f(self.mean_data)
        std = x.std * f(self.std_data)
        
        return NormalsParams(mean, std)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 171
class ToTuple(Transform):
    def encodes(self, x): return tuple(x),  tuple(x)
    def decodes(self, x): return MeteoImpTensor(x[0])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 176
from fastai.data.transforms import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 178
def imp_pipeline(df,
                 control,
                 var_sel,
                 gap_len,
                 block_len,
                 control_lags
                ):
    offset = max(control_lags)
    block_ids = list(range(offset, (len(df) // block_len) - 1))
    return [BlockIndexTransform(df.index, block_len=block_len, offset=offset),
            BlockDfTransform(data = df, control = control,  control_lags = control_lags),
            AddGapTransform(var_sel, gap_len),
            MeteoImpDf2Tensor,
            MeteoImpNormalize(*get_stats(df), *get_stats(control, 1+len(control_lags))),
            ToTuple
           ], block_ids

# %% ../../lib_nbs/kalman/10_fastai.ipynb 196
def imp_dataloader(df,
                 control,
                 var_sel,
                 gap_len,
                 block_len,
                 control_lags,
                 bs):
    pipeline, block_ids = imp_pipeline(df, control, var_sel, gap_len, block_len, control_lags)
    splits = RandomSplitter()(block_ids)
    ds = TfmdLists(block_ids, pipeline, splits=splits)
    
    return ds.dataloaders(bs=bs)
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 204
from .filter import *
from torch.distributions import MultivariateNormal

# %% ../../lib_nbs/kalman/10_fastai.ipynb 205
@patch
def _predict_filter(self: KalmanFilter, data, mask, control):
    """Predict every obsevation using only the filter step"""
    # use the predicted state not the filtered state!
    pred_state_mean, pred_state_cov, _, _ = self._filter_all(data, mask, control)
    mean, cov = self._obs_from_state(ListMNormal(pred_state_mean.squeeze(-1), pred_state_cov))
    
    return ListNormal(mean, cov2std(cov))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 210
@patch
def forward(self: KalmanFilter, meteo_data: MeteoImpTensor):
    data, mask, control = meteo_data
    assert not data.isnan().any()
    use_smooth = self.use_smooth if hasattr(self, 'use_smooth') else True
    
    mean, std = (self.predict(obs=data, mask=mask, control=control, smooth=True) if use_smooth
                        else self._predict_filter(data, mask, control))
    return NormalsParams(mean, std) # to have fastai working this needs to be a tuple subclass

# %% ../../lib_nbs/kalman/10_fastai.ipynb 240
class KalmanLoss():
    def __init__(self,
                 only_gap:bool=True, # loss for all predictions or only gap
                 reduction:str='mean' # one of ['sum', 'mean', 'none']
                ):
        store_attr()
    
    def __call__(self, pred: NormalsParams, target: MeteoImpTensor):
        data, mask, contr = target
        means, stds = pred        
        assert not stds.isnan().any()
        losses = torch.empty(data.shape[0], device=data.device, dtype=data.dtype)
        for i, (d, m, mean, std) in enumerate(zip(data, mask, means, stds)):
            losses[i] = self._loss_batch(d,m,mean, std)
        if self.reduction == 'none': return losses
        elif self.reduction == 'mean': return losses.mean()
        elif self.reduction == 'sum': return losses.sum()
    
    def _loss_batch(self, data, mask, mean, std):
        # make a big vector with all variables and observations and compute ll
        mask = ~mask.flatten() if self.only_gap else torch.fill(mask, True).flatten()
        obs = data.flatten()[mask]
        mean = mean.flatten()[mask]
        std = std.flatten()[mask] 
        
        return - MultivariateNormal(mean, torch.diag(std)).log_prob(obs)
        

# %% ../../lib_nbs/kalman/10_fastai.ipynb 261
from sklearn.metrics import r2_score, mean_squared_error

# %% ../../lib_nbs/kalman/10_fastai.ipynb 273
from fastai.metrics import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 283
class ImpMetric:
    def __init__(self, metric, name, only_gap=False, flatten=False):
        store_attr()
    @property
    def __name__(self): return  self.name + ("_gap" if self.only_gap else "")
    def _metric_batch(self, pred, targ):
        return self.metric(pred, targ)
    def _metric_batch_gap(self, pred, targ, mask):
        row_sel, col_sel = ~mask.all(1), ~mask.all(0)
        assert not mask[:, col_sel][row_sel, :].any() # all data is missing in mask
        return self.metric(pred[:, col_sel][row_sel, :], targ[:, col_sel][row_sel, :])
    def __call__(self, pred: NormalsParams, targ: MeteoImpTensor):
        mean, _ = pred
        data, mask, _ = targ
        metric_values = torch.empty(mean.shape[0])
        for i in range(metric_values.shape[0]):
            metric_values[i] = (self._metric_batch_gap(mean[i], data[i], mask[i]) if self.only_gap
            else self._metric_batch(mean[i], data[i]))
        return metric_values.mean().item()
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 284
rmse_mask = ImpMetric(rmse, 'rmse')
rmse_gap = ImpMetric(rmse, 'rmse', only_gap=True)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 288
multi_r2 = skm_to_fastai(r2_score, flatten=False)
r2_mask = ImpMetric(multi_r2, 'r2')
r2_gap = ImpMetric(multi_r2, 'r2', only_gap=True)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 291
imp_metrics =  [rmse_mask, rmse_gap, r2_mask, r2_gap]

# %% ../../lib_nbs/kalman/10_fastai.ipynb 294
from fastai.callback.all import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 295
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 296
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 300
from fastai.learner import * 

from fastai.tabular.all import *

from fastai.tabular.learner import *

from fastai.callback.progress import ShowGraphCallback

# %% ../../lib_nbs/kalman/10_fastai.ipynb 316
class Float64Callback(Callback):
    order = Recorder.order + 10 # run after Recorder 
    def before_fit(self):
        self.recorder.smooth_loss.val = torch.tensor(0, dtype=torch.float64) # default is a float 32

# %% ../../lib_nbs/kalman/10_fastai.ipynb 328
class NormalsDf:
    """DataFrames of Normal parameters (mean and std)"""
    def __init__(self, mean, std): store_attr()
    def tidy(self, prefix=""):
        """Tidy version"""
        mean = self.mean.reset_index().melt("time", value_name=prefix + "mean")
        std = self.std.reset_index().melt("time", value_name=prefix + "std")
        return pd.merge(mean, std, on=["time", "variable"])
    __repr__ = basic_repr("mean, std")

# %% ../../lib_nbs/kalman/10_fastai.ipynb 333
def preds2df(preds, targs):
    """Final step to decode preds by getting a dataframe"""
    # preds this is a tuple (data, mask)
    out = []
    for pred, targ in zip(preds, targs):
        # convert to dataframe using structure for
        mean = pd.DataFrame(pred[0].squeeze(0).detach().cpu().numpy(), columns = targ.data.columns, index=targ.data.index)
        std = pd.DataFrame(pred[1].squeeze(0).detach().cpu().numpy(), columns = targ.data.columns, index=targ.data.index)
        out.append(NormalsDf(mean, std))
    return out

# %% ../../lib_nbs/kalman/10_fastai.ipynb 334
def predict_items(items, learn, pipe0, pipe1):
    pipe0, pipe1 = Pipeline(pipe0), Pipeline(pipe1)
    preds, targs, losses = [], [], []
    for item in items:
        targ = pipe0(item)
        data, mask, control = pipe1(targ)
        input = MeteoImpTensor(data.cuda().unsqueeze(0), mask.cuda().unsqueeze(0), control.cuda().unsqueeze(0))
        pred = learn.model(input)
        loss = learn.loss_func(pred, input)
        # denormalize
        pred = pipe1.decode(pred)
        preds.append(pred), targs.append(targ), losses.append(loss)
        
    return preds2df(preds, targs), targs, losses
        

# %% ../../lib_nbs/kalman/10_fastai.ipynb 338
def plot_result(pred, targ, loss, **kwargs):
    df = pd.merge(targ.tidy(), pred.tidy(), on=["time", "variable"])
    # return df
    return facet_variable(df, ys=["value", "mean"], error=True, **kwargs).properties(title=f"loss: {loss.item():.6f}")

# %% ../../lib_nbs/kalman/10_fastai.ipynb 341
def plot_results(preds, targs, losses, **kwargs):
    plots = [plot_result(targ, pred, loss, n_cols=1, **kwargs) for targ, pred, loss in zip(preds, targs, losses)]
    return alt.hconcat(*plots)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 345
def get_results(learn, n=3, items=None, dls=None):
    dls = ifnone(dls, learn.dls)
    items = ifnone(items, random.choices(dls.items, k=3))
    pipe0, pipe1 = dls.fs[0,1,2], dls.fs[3,4]
    return predict_items(items, learn, pipe0, pipe1)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 346
def show_results(learn, n=3, items=None, **kwargs):
    return plot_results(*get_results(learn,n,items), **kwargs)
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 352
from ipywidgets import IntSlider, interact_manual, Text

# %% ../../lib_nbs/kalman/10_fastai.ipynb 353
def results_custom_gap(learn, df, control, items_idx, var_sel, gap_len, block_len, control_lags):
    pipeline,_ = imp_pipeline(df, control, var_sel, gap_len, block_len, control_lags)
    
    dls = TfmdLists(items_idx, pipeline).dataloaders(bs=len(items_idx))
    return get_results(learn, items=items_idx, dls=dls)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 355
def interact_results(learn, df, control):
    interact_args = {
        'gap_len': IntSlider(10, 1, 100),
        'items_idx': Text(value='10, 100', placeholder="comma separated indices"),
        'control_lags': Text(value='1', label="comma lag control"),
        'block_len': IntSlider(200, 10, 1000, 10),
        **{var_name: True for var_name in df.columns}
    }
    
    def _inner(gap_len, items_idx, control_lags, block_len, **var_names):
        var_sel = [var_name for var_name, var_use in var_names.items() if var_use]
        items_idx = list(map(int, items_idx.split(",")))
        control_lags = list(map(int, control_lags.split(",")))
        return plot_results(*results_custom_gap(learn=learn, df=df, control=control, var_sel=var_sel, gap_len=gap_len, items_idx=items_idx, block_len=block_len, control_lags=control_lags))
    return interact_manual(_inner, **interact_args)
