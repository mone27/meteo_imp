# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/kalman/10_fastai.ipynb.

# %% auto 0
__all__ = ['hai_control', 'rmse_mask', 'rmse_gap', 'multi_r2', 'r2_mask', 'imp_metrics', 'BlockIndexTransform', 'DataControl',
           'BlockDfTransform', 'MeteoImpDf', 'AddGapTransform', 'find_gap_limits', 'plot_missing_area', 'plot_points',
           'plot_variable', 'facet_variable', 'MeteoImpTensor', 'MeteoImpDf2Tensor', 'MNormalsParams', 'NormalsParams',
           'get_stats', 'MeteoImpNormalize', 'ToTuple', 'as_generator', 'gen_gap_len', 'gen_var_sel', 'imp_pipeline',
           'imp_dataloader', 'get_only_gap', 'KalmanLoss', 'ImpMetric', 'imp_rmse', 'SaveParams', 'Float64Callback',
           'one_batch_with_items', 'CovStdTransform', 'buffer_pred_single', 'buffer_pred', 'maybe_buffer_pred',
           'orig_target', 'NormalsDf', 'preds2df', 'unsqueeze_maybe_list', 'PredMetrics', 'predict_items',
           'only_gap_ctx', 'format_metric', 'plot_result', 'plot_results', 'get_results', 'show_results',
           'results_custom_gap', 'CustomGap']

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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 19
class BlockIndexTransform(Transform):
    """divide timeseries DataFrame index into blocks"""
    def __init__(self, idx: pd.DatetimeIndex, block_len:int =200, offset=1):
        store_attr()
        self.n = len(idx)
        
    def encodes(self, item:MeteoImpItem
               ) -> MeteoImpIndex:       
        start = item.i * self.block_len + self.offset + item.shift
        end = (item.i+1) * self.block_len + self.offset + item.shift
        assert end <= self.n, f"Item index {item.i} too big for dataframe of length {self.n} with block len {self.block_len}"
        
        return MeteoImpIndex(self.idx[start:end], item.var_sel, item.gap_len)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 25
@dataclass
class DataControl:
    data: pd.DataFrame
    control: pd.DataFrame
    var_sel: list[str]
    gap_len: int
    def _repr_html_(self):
            return row_dfs({'data': self.data, 'control': self.control}, title=f"Data Control ({self.var_sel}, {self.gap_len})", hide_idx=False)
    def __iter__(self): return iter((self.data, self.control, self.var_sel, self.gap_len))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 28
def _rename_lag(lag):
    def _inner(col_name):
        return f"{col_name}_lag_{lag}"
    return _inner

# %% ../../lib_nbs/kalman/10_fastai.ipynb 30
def _lag_df(df, lag):
    "add lagged columns"
    df_lag = df.shift(lag).rename(columns = _rename_lag(lag))
    return df_lag
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 32
def _add_lags_df(df, lags):
    df_lagged = df
    for lag in listify(lags):
        df_lagged = pd.merge(df_lagged, _lag_df(df, lag), left_index=True, right_index=True)
    return df_lagged

# %% ../../lib_nbs/kalman/10_fastai.ipynb 34
class BlockDfTransform(Transform):
    """divide timeseries DataFrame index into blocks"""
    def __init__(self, data: pd.DataFrame, control: pd.DataFrame, control_lags: int|Iterable[int]):
        store_attr()
        self.control = _add_lags_df(control, control_lags)
    def encodes(self, idx: MeteoImpIndex) -> DataControl:
        return DataControl(self.data.loc[idx.index], self.control.loc[idx.index], idx.var_sel, idx.gap_len)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 47
def _make_random_gap(
    gap_length: int, # The length of the gap
    total_length: int, # The total number of observations
    gap_start: int # Optional start of gap
)-> np.ndarray: # [total_length] array of bools to indicicate if the data is missing or not
    "Add a continous gap of given length at random position"
    if(gap_length >= total_length):
        return np.repeat(True, total_length)
    return np.hstack([
        np.repeat(False, gap_start),
        np.repeat(True, gap_length),
        np.repeat(False, total_length - (gap_length + gap_start))
    ])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 55
@dataclass
class MeteoImpDf:
    data: pd.DataFrame
    mask: pd.DataFrame
    control: pd.DataFrame
    def __iter__(self): return iter((self.data, self.mask, self.control,))
    __repr__ = basic_repr("data, mask, control")
    def _repr_html_(self):
        return row_dfs({'data': self.data, 'mask': self.mask, 'control': self.control}, title="Meteo Imp Df", hide_idx=False)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 56
class AddGapTransform(Transform):
    """Adds a random gap to a dataframe"""
    def __init__(self,gap_start): store_attr()
    def encodes(self, dc: DataControl) -> MeteoImpDf:
        df, control, var_sel, gap_len = dc
        gap = _make_random_gap(gap_len, df.shape[0], self.gap_start)
        mask = np.ones_like(df, dtype=bool)
        col_sel = L(*df.columns).argwhere(lambda x: x in var_sel)
        mask[np.argwhere(gap), col_sel] = False
        mask = pd.DataFrame(mask, index=df.index, columns=df.columns)
        return MeteoImpDf(df, mask, control)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 62
@patch
def tidy(self: MeteoImpDf,
         control_map:Optional[dict[str, str]] = None # mapping from control var names to obs names
        ):
    data = self.data.reset_index().melt("time")
    mask = self.mask.reset_index().melt("time", value_name="is_present")
    
    if control_map is not None:
        control = (self.control[control_map.keys()].rename(columns=control_map)
                    .reset_index().melt("time", value_name="control"))
        data = pd.merge(data, control, on=["time", "variable"], how="left")
    
    return pd.merge(data, mask, on=["time", "variable"])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 63
hai_control = {'TA_ERA': 'TA', 'SW_IN_ERA': 'SW_IN', 'VPD_ERA': 'VPD'}

# %% ../../lib_nbs/kalman/10_fastai.ipynb 68
import altair as alt
from altair import datum

# %% ../../lib_nbs/kalman/10_fastai.ipynb 69
def def_selection():
    return alt.selection_interval(bind="scales")

# %% ../../lib_nbs/kalman/10_fastai.ipynb 71
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 84
def find_gap_limits(df):
    gap_starts, gap_ends = [], []
    for i in range(len(df)):
        prev = df.iloc[i-1].is_present if i>0 else True 
        _next = df.iloc[i+1].is_present if i<(len(df)-1) else True 
        curr = df.iloc[i]
        if not curr.is_present and prev: gap_starts.append(curr.time)
        if not curr.is_present and _next: gap_ends.append(curr.time)
    return pd.DataFrame({'gap_start': gap_starts, 'gap_end': gap_ends})
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 86
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 89
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 92
def plot_line(df, only_present=True, y="value", y_label = "", sel = def_selection(), props = {}):
    # df = df[df.is_present] if only_present else df
    # TODO remove onle_present
    return alt.Chart(df).mark_line().encode(
        x = "time",    
        y = alt.Y(y, title = y_label, scale=alt.Scale(zero=False)),
        color=alt.Color('variable', scale= scale_meteo)
    ).add_params(
        sel
    ).properties(
        **props
    )#.transform_filter(
    #     datum.is_present
    # )

    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 95
def plot_control(df, only_present=True, y="control", y_label = "", sel = def_selection(), props = {}):
    # df = df[df.is_present] if only_present else df
    # TODO remove onle_present
    return alt.Chart(df).mark_line(strokeDash=[4,6], color="purple").encode(
        x = "time",    
        y = alt.Y(y, title = y_label, scale=alt.Scale(zero=False)),
    ).add_params(
        sel
    ).properties(
        **props
    )    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 98
def plot_error(df, y = "value", y_label = "", sel = def_selection(), props = {}):
    df.loc[:,'err_low'] = df[y] - 2 * df['std']
    df.loc[:,'err_high'] = df[y] + 2 * df['std']
    return alt.Chart(df).mark_errorband().encode(
        x = "time",    
        y = alt.Y("err_low:Q", title = y_label, scale=alt.Scale(zero=False)),
        y2 = "err_high:Q",
        color=alt.Color("variable",
                        legend = alt.Legend(title=["Line: pred. mean", "area: +/- 2 std"]),
                        scale = scale_meteo
                       )
    ).add_params(
        sel
    ).properties(
        **props
    )
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 101
def plot_variable(df,
                  variable, ys=["value", "value", "control"],
                  title="",
                  y_label="",
                  sel = None,
                  error=False,
                  point=True,
                  gap_area = True,
                  control=False,
                  props = {}):
    df = df[df.variable == variable].copy()
    sel = ifnone(sel, def_selection())
    # rug = plot_rug(df, sel, props)
    plots = []
    if point: plots.append(plot_points(df, ys[0], y_label, sel, props))
    if gap_area and not df.is_present.all():
        plots.append(plot_missing_area(df, sel, props)) # there is a gap
    if error: plots.append(plot_error(df, y=ys[1], y_label=y_label, sel=sel, props=props))
    if control: plots.append(plot_control(df, y=ys[2], y_label=y_label, sel=sel, props=props))
    plots.append(plot_line(df, True, ys[1], y_label, sel, props))
    
    return alt.layer(*plots).properties(title=title)
    
    # return alt.VConcatChart(vconcat=[(points + line), rug], spacing=-10).properties(title=title)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 107
@delegates(plot_variable, but="y_label")
def facet_variable(df, # tidy dataframe
                   n_cols: int = 3,
                   bind_interaction: bool =True, # Whether the sub-plots for each variable should be connected for zooming/panning
                   units = None,
                    **kwargs
                   ) -> alt.Chart:
    """Plot all values of the column `variable` in different subplots"""
    kwargs['props'] = ifnone(kwargs.get('props', None), {'width': 200, 'height': 150})
    vars = df.variable.unique()
    plot_list = [alt.hconcat() for _ in range(0, len(vars), n_cols)]
    selection_scale = alt.selection_interval(bind="scales", encodings=['x']) if bind_interaction else None
    for idx, variable in enumerate(vars):
        y_label =  kwargs.get("y_label", f"{variable} [{units[variable]}]" if units is not None else variable)
        plot = plot_variable(df,
                            variable,
                            sel = selection_scale,
                            y_label = y_label, 
                            **kwargs)
        
        plot_list[idx // n_cols] |= plot
    
    plot = alt.vconcat(*plot_list)
    
    return plot

# %% ../../lib_nbs/kalman/10_fastai.ipynb 109
@patch
def show(self: MeteoImpDf, ax=None, ctx=None, 
        n_cols: int = 3,
        bind_interaction: bool =True, # Whether the sub-plots for each variable should be connected for zooming/panning
        props:dict = None # additional properties (eg. size) for altair plot
       ) -> alt.Chart:
    
    df = self.tidy()
    return facet_variable(df, n_cols, bind_interaction, props=props)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 115
class MeteoImpTensor(collections.abc.Sequence):
    def __init__(self,*args):
        if len(args)==3:
            self.data = args[0]
            self.mask = args[1]
            self.control = args[2]
        elif len(args)==1 and len(args[0])==2:
            self.data = args[0][0]
            self.mask = args[0][1]
            self.control = args[0][2]
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 116
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 126
from ..utils import *
from fastai.torch_core import to_cpu

from torch import Tensor

# %% ../../lib_nbs/kalman/10_fastai.ipynb 127
class MNormalsParams(list):
    def __init__(self,*args):
        if len(args)==2:
            self.mean = args[0]
            self.cov = args[1]
        elif isinstance(args[0], Generator):
            args = list(args[0])
            self.mean = args[0]
            self.cov = args[1]
        elif len(args)==1 and len(args[0])==2:
            self.mean = tuple(args[0])[0]
            self.cov = tuple(args[0])[1]                     
        else:
            raise ValueError(f"Incorrect number of arguments. got {len(args)} args")
    def __iter__(self): return iter((self.mean, self.cov,))
    def __next__(self): return next(self.__iter__())
    def __len__(self): return 2
    def __getitem__(self, key):
        if key == 0: return self.mean
        elif key == 1: return self.cov
        else: raise IndexError("index bigger than 2")
    __repr__ = basic_repr('mean, cov')
    def squeeze(self,i):
        self.mean.squeeze_(i)
        self.cov.squeeze_(i)
        return self

# %% ../../lib_nbs/kalman/10_fastai.ipynb 128
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 131
def get_stats(df, repeat=1, device='cpu'):
    return torch.tensor(df.mean(axis=0).to_numpy(), device=device).repeat(repeat), torch.tensor(df.std(axis=0).to_numpy(), device=device).repeat(repeat)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 132
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 146
class ToTuple(Transform):
    def encodes(self, x): return tuple(x),  tuple(x)
    def decodes(self, x): return NormalsParams(x[0], x[1])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 152
from collections.abc import Iterable, Generator

# %% ../../lib_nbs/kalman/10_fastai.ipynb 153
def as_generator(x: Generator|object,
                 iter=False, # should generator return x or iterate over the elements of x
                ):
    """Maybe convert iterable to infinite generator"""
    if isinstance(x, Generator): return x
    else: return cycle( x if iter else (x,))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 163
def gen_gap_len(mean: float, min_v = 1, max_v=50): 
    scale = mean*.6
    shape = mean/scale
    while True:
        v = int(np.random.gamma(scale=scale, shape=shape))
        yield max(min(v, max_v), min_v)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 169
def gen_var_sel(vars):
    while True:
        n_var = np.random.randint(1,1+len(vars))
        yield np.random.choice(np.array(vars), size=n_var, replace=False)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 176
from fastai.data.transforms import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 183
def imp_pipeline(df,
                 control,
                 var_sel,
                 gap_len,
                 block_len,
                 control_lags,
                 n_rep,
                 shifts = None
                ):
    offset = max(control_lags)
    block_ids = get_block_ids(n_rep, len(df), block_len, var_sel, gap_len, shifts, offset)
    return [BlockIndexTransform(df.index, block_len=block_len, offset=offset),
            BlockDfTransform(data = df, control = control,  control_lags = control_lags),
            AddGapTransform(block_len//2),
            MeteoImpDf2Tensor,
            MeteoImpNormalize(*get_stats(df), *get_stats(control, 1+len(control_lags))),
            ToTuple
           ], block_ids

# %% ../../lib_nbs/kalman/10_fastai.ipynb 200
def imp_dataloader(df,
                 control,
                 var_sel,
                 gap_len,
                 block_len,
                 control_lags,
                 n_rep,  
                 bs):
    pipeline, block_ids = imp_pipeline(df, control, var_sel, gap_len, block_len, control_lags, n_rep)
    splits = EndSplitter()(block_ids)
    ds = TfmdLists(block_ids, pipeline, splits=splits)
    
    return ds.dataloaders(bs=bs)
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 208
from .filter import *
from torch.distributions import MultivariateNormal

# %% ../../lib_nbs/kalman/10_fastai.ipynb 215
@patch
def forward(self: KalmanFilter|KalmanFilterSR, meteo_data: MeteoImpTensor):
    data, mask, control = meteo_data
    assert not data.isnan().any()
    use_smooth = self.use_smooth if hasattr(self, 'use_smooth') else True
    
    mean, cov = (self.predict(obs=data, mask=mask, control=control, smooth=True) if use_smooth
                        else self._predict_filter(data, mask, control))
    return MNormalsParams(mean, cov) # to have fastai working this needs to be a tuple subclass

# %% ../../lib_nbs/kalman/10_fastai.ipynb 243
def get_only_gap(mask, *args):
    """for each element in arg return only the portion where there is a gap at the time level"""
    gap_mask = ~mask.all(-1)
    return [x[gap_mask] for x in args]

# %% ../../lib_nbs/kalman/10_fastai.ipynb 244
class KalmanLoss():
    def __init__(self,
                 only_gap:bool=False, # loss for all predictions or only gap. Expects predictions only for gap
                 use_std:bool=False, # loss on stds otherwise with full cov matrices.
                 reduction:str='mean', # one of ['sum', 'mean', 'none'] reduction between batches
                 reduction_inbatch:str='sum', # one of ['sum', 'mean', 'none'] reduction inside a batch
                ):
        store_attr()
    
    def __call__(self, pred: NormalsParams, target: MeteoImpTensor):
        data, mask, _ = target
        means, covs = pred        
        # assert not covs.isnan().any(), "Nan in prediction"
        losses = torch.empty(len(data), device=data.device, dtype=data.dtype)
        for i, (d, m, mean, cov) in enumerate(zip(data, mask, means, covs)):
            losses[i] = self._loss_batch(d,m,mean, cov)
        return self._reduce(losses, self.reduction)
    
    def _loss_batch(self, datas, masks, means, covs):
        if self.only_gap:
            # here means and covs are already masked, while data and mask is not
            datas, masks = get_only_gap(masks, datas, masks)
        
        assert len(datas) == len(means)
        losses = torch.zeros(len(datas), device=datas.device, dtype=datas.dtype)
        for i, (data, mask, mean, cov) in enumerate(zip(datas, masks, means, covs)):
            if self.use_std: cov = torch.diag(cov.diag()) # keep only diagonal of covariance
            if self.only_gap:
                data = data[~mask]
            losses[i] = - MultivariateNormal(mean, cov).log_prob(data)
        return self._reduce(losses, self.reduction_inbatch)
    
    @staticmethod
    def _reduce(losses, reduction):
        if reduction == 'none': return losses
        elif reduction == 'mean': return losses.mean()
        elif reduction == 'sum': return losses.sum()
        else: raise ValueError(f"invalid reduction {reduction}")

        

# %% ../../lib_nbs/kalman/10_fastai.ipynb 260
from sklearn.metrics import r2_score, mean_squared_error

# %% ../../lib_nbs/kalman/10_fastai.ipynb 272
from fastai.metrics import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 282
from fastai.learner import AvgMetric
import torch.nn.functional as F

# %% ../../lib_nbs/kalman/10_fastai.ipynb 283
class ImpMetric(AvgMetric):
    def __init__(self, metric, base_name, only_gap=False, flatten=False):
        store_attr()
    @property
    def name(self): return  self.base_name + ("_gap" if self.only_gap else "")
    def _metric_batch(self, pred, targ):
        return self.metric(pred, targ)
    def _metric_batch_gap(self, pred_list, targ, mask):
        targ, mask = get_only_gap(mask, targ, mask)
        assert len(pred_list) == len(targ)
        pred = torch.vstack(pred_list) # convert to tensor
        row_sel, col_sel = ~mask.all(1), ~mask.all(0)
        assert not mask[:, col_sel][row_sel, :].any(), "More than 1 gap uniform not supported"
        return self.metric(pred[:, col_sel[col_sel]][row_sel, :], targ[:, col_sel][row_sel, :])
    def __call__(self, *args): return self.func(*args)
    def func(self, pred: NormalsParams, targ: MeteoImpTensor):
        mean, _ = pred
        data, mask, _ = targ
        metric_values = torch.empty(len(mean))
        for i in range(metric_values.shape[0]):
            metric_values[i] = (self._metric_batch_gap(mean[i], data[i], mask[i]) if self.only_gap
            else self._metric_batch(mean[i], data[i]))
        return metric_values.mean().item()
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 284
def imp_rmse(preds, targs):
    return torch.sqrt(F.mse_loss(preds, targs))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 285
rmse_mask = ImpMetric(imp_rmse, 'rmse')
rmse_gap = ImpMetric(imp_rmse, 'rmse', only_gap=True)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 292
multi_r2 = skm_to_fastai(r2_score, flatten=False)
r2_mask = ImpMetric(multi_r2, 'r2')
# r2_gap = ImpMetric(multi_r2, 'r2', only_gap=True)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 295
imp_metrics =  [rmse_mask, rmse_gap]

# %% ../../lib_nbs/kalman/10_fastai.ipynb 298
from fastai.callback.all import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 299
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 300
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 304
from fastai.learner import * 

from fastai.tabular.all import *

from fastai.tabular.learner import *

from fastai.callback.progress import ShowGraphCallback

# %% ../../lib_nbs/kalman/10_fastai.ipynb 314
class Float64Callback(Callback):
    order = Recorder.order + 10 # run after Recorder 
    def before_fit(self):
        self.recorder.smooth_loss.val = torch.tensor(0, dtype=torch.float64) # default is a float 32

# %% ../../lib_nbs/kalman/10_fastai.ipynb 327
def one_batch_with_items(dls, items):
    """ Makes custom dataloader that returns only one batch with items"""
    new_ds = dls.dataset.copy()
    items = listify(items)
    new_ds.items =items
    return dls.new(bs = len(items), dataset = new_ds, shuffle=False).one_batch()

# %% ../../lib_nbs/kalman/10_fastai.ipynb 336
class CovStdTransform(Transform):
    def encodes(self, x: MNormalsParams) -> NormalsParams:
        return NormalsParams(x.mean, self(x.cov))
    def encodes(self, x: torch.Tensor): return cov2std(x)
    def encodes(self, x: list):
        return [self(o) for o in x]

# %% ../../lib_nbs/kalman/10_fastai.ipynb 343
def buffer_pred_single(preds: list[Tensor],
                masks: Tensor) -> Tensor:
    """For predictions are for gaps only add buffer of `Nan` so they have same shape of targets"""
    all_pred = torch.empty(masks.shape, dtype=preds[0][0].dtype).fill_(torch.nan)
    i_p = 0
    for i, (mask) in enumerate(masks.cpu()):
        if not mask.all():
            all_pred[i][~mask] = preds[i_p].detach().cpu()
            i_p += 1
    assert i_p == len(preds)
    return all_pred

# %% ../../lib_nbs/kalman/10_fastai.ipynb 344
def buffer_pred(preds: list[list[Tensor]],
                masks: Tensor) -> Tensor:
    """For predictions are for gaps only add buffer of `Nan` so they have same shape of targets"""
    return torch.stack([buffer_pred_single(pred, mask) for pred, mask in zip(preds, masks)])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 345
def maybe_buffer_pred(preds, masks):
    """If predictions are for gaps only add buffer so they have same shape of targets"""
    if not isinstance(preds.mean, torch.Tensor):
        return NormalsParams(buffer_pred(preds.mean, masks), buffer_pred(preds.std, masks))
    else:
        return NormalsParams(preds.mean.detach().cpu(), preds.std.detach().cpu())

# %% ../../lib_nbs/kalman/10_fastai.ipynb 355
def orig_target(dls, items):
    pipe = Pipeline(dls.fs[:3])
    return [pipe(item) for item in items]

# %% ../../lib_nbs/kalman/10_fastai.ipynb 359
class NormalsDf:
    """DataFrames of Normal parameters (mean and std)"""
    def __init__(self, mean, std): store_attr()
    def tidy(self, prefix=""):
        """Tidy version"""
        mean = self.mean.reset_index().melt("time", value_name=prefix + "mean")
        std = self.std.reset_index().melt("time", value_name=prefix + "std")
        return pd.merge(mean, std, on=["time", "variable"])
    __repr__ = basic_repr("mean, std")
    @classmethod
    def from_preds(cls,
                   mean: Tensor,
                   std: Tensor,
                   targ: MeteoImpDf):
        """Convert prediction to dataframe using index/columns form target """
        mean = pd.DataFrame(mean.numpy(), columns = targ.data.columns, index=targ.data.index)
        std = pd.DataFrame(std.numpy(), columns = targ.data.columns, index=targ.data.index)
        return cls(mean, std)
    def _repr_html_(self):
        return row_dfs({'data': self.mean, 'std': self.std}, title="Normals Df", hide_idx=False)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 360
def preds2df(preds: NormalsParams, targs):
    return [NormalsDf.from_preds(preds.mean[i], preds.std[i], targs[i]) for i in range(len(targs))]

# %% ../../lib_nbs/kalman/10_fastai.ipynb 364
def unsqueeze_maybe_list(x):
    """add a dimension in front if Tensor and make a list of x if x is a list"""
    return x.unsqueeze(0) if isinstance(x, torch.Tensor) else [x]
def _n_tuple(x, n, unsqueeze = True):
    """get the nth element of for every element of a tuple"""
    f = unsqueeze_maybe_list if unsqueeze else noop
    return type(x)(tuple(f(o[n]) for o in x))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 369
class PredMetrics:
    def __init__(self, learn):
        self.metrics = {metric.name: metric for metric in learn.metrics} | {'loss': learn.loss_func}
    def __call__(self, preds, targs):
        out = []
        for i in range(len(preds.mean)):
            out.append({name: metric(_n_tuple(pred, i), _n_tuple(targ, i)) for name, metric in self.metrics.items()})
        return out

# %% ../../lib_nbs/kalman/10_fastai.ipynb 370
def predict_items(
    model: KalmanFilterBase,
    dls: DataLoaders,
    items: list[list],
    # metric_fn: PredMetrics
):
    input, _ = one_batch_with_items(dls, items)
    preds_0 = model(input)
    preds_1 = CovStdTransform()(preds_0)
    preds_2 = maybe_buffer_pred(preds_1, input[1])
    preds_3 = dls.fs[-2].decode(preds_2) # inverse normalize
    targs = orig_target(dls, items)
    preds_5 = preds2df(preds_3, targs)
    
    # metrics = metric_fn(preds_0, input)
    
    return preds_5, targs, #metrics

# %% ../../lib_nbs/kalman/10_fastai.ipynb 378
from fastcore.xtras import ContextManagers
from fastai.learner import replacing_yield

# %% ../../lib_nbs/kalman/10_fastai.ipynb 379
def only_gap_ctx(learn, only_gap=True):
    @contextmanager
    def _set_model(): return replacing_yield(learn.model, 'pred_only_gap', only_gap)
    @contextmanager
    def _set_loss(): return replacing_yield(learn.loss_func, 'only_gap', only_gap)
    @contextmanager
    def _set_metric(): return replacing_yield(learn, 'metrics', [rmse_gap] if only_gap else [rmse_mask])
    return ContextManagers([_set_model(), _set_loss(), _set_metric()])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 386
def format_metric(name, val):
    val = f"{val:.5}" if abs(val) <1 else f"{val:.5E}"
    return f"{name}: {val}"

# %% ../../lib_nbs/kalman/10_fastai.ipynb 387
@delegates(facet_variable)
def plot_result(pred, targ, metrics=None, control_map=None, hide_no_gap=False, **kwargs):
    df = pd.merge(targ.tidy(control_map), pred.tidy(), on=["time", "variable"])

    title =  [format_metric(name, val) for name, val in metrics.items()] if metrics else ""
    if hide_no_gap:
        show_vars = f_targs[0].data.columns[~f_targs[0].mask.all()] # only variables with a gap
        df = df[df.variable.isin(show_vars)]
    return facet_variable(df, ys=["value", "mean", "control"], error=True, control=bool(control_map), **kwargs).properties(title=title)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 393
def plot_results(preds, targs, metrics = None, n_cols=1, **kwargs):
    metrics = ifnone(metrics, [None for _ in range(len(preds))])
    plots = [plot_result(targ, pred, metric, n_cols=n_cols, **kwargs) for targ, pred, metric in zip(preds, targs, metrics)]
    return alt.hconcat(*plots)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 399
def get_results(learn, n=3, items=None, dls=None):
    dls = ifnone(dls, learn.dls)
    dls = dls.valid if len(dls.valid.items) > 0 else dls
    items = items if items is not None else random.choices(dls.items, k=n)
    return predict_items(learn.model, dls, items)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 401
@delegates(plot_results)
def show_results(learn, n=3, items=None, dls=None, **kwargs):
    return plot_results(*get_results(learn,n,items, dls), **kwargs)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 405
from ipywidgets import IntSlider, interact_manual, Text

# %% ../../lib_nbs/kalman/10_fastai.ipynb 406
def results_custom_gap(learn, df, control, items_idx, var_sel, gap_len, block_len, shift, control_lags):
    pipeline,_ = imp_pipeline(df, control, var_sel, gap_len, block_len, control_lags, n_rep=1)
    items_idx = [MeteoImpItem(i, shift, var_sel, gap_len) for i in items_idx]
    dls = TfmdLists(items_idx,pipeline).dataloaders(bs=len(items_idx)).to(learn.dls.device)
    return predict_items(learn.model, dls=dls, items=items_idx)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 408
class CustomGap:
    def __init__(self, learn, df, control): store_attr()
    def results(self, items_idx, var_sel, gap_len, block_len, shift, control_lags):
        pipeline,_ = imp_pipeline(self.df, self.control, var_sel, gap_len, block_len, control_lags, n_rep=1)
        items_idx = [MeteoImpItem(i, shift, var_sel, gap_len) for i in items_idx]
        dls = TfmdLists(items_idx,pipeline).dataloaders(bs=len(items_idx)).to(self.learn.dls.device)
        return predict_items(self.learn.model, dls=dls, items=items_idx)
    def show(self, items_idx, var_sel, gap_len, block_len, shift, control_lags):
        return plot_results(*self.results(items_idx, var_sel, gap_len, block_len, shift, control_lags))
    
    def _show_ipy(self, gap_len, items_idx, control_lags, block_len, shift, **var_names):
        var_sel = [var_name for var_name, var_use in var_names.items() if var_use]
        items_idx = list(map(int, items_idx.split(",")))
        control_lags = list(map(int, control_lags.split(",")))
        return self.show(var_sel=var_sel, gap_len=gap_len, items_idx=items_idx, block_len=block_len,
                                                     control_lags=control_lags, shift=shift)
    def interact_results(self):
        interact_args = {
            'gap_len': IntSlider(10, 1, 100),
            'items_idx': Text(value='10, 100', placeholder="comma separated indices"),
            'control_lags': Text(value='1', label="comma lag control"),
            'block_len': IntSlider(200, 10, 1000, 10),
            'shift': IntSlider(0, -100, 100, 1),
            **{var_name: True for var_name in self.df.columns}
        }
        return interact_manual(self._show_ipy, **interact_args) 
