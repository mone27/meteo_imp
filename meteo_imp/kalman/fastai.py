# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/kalman/03_Kalman_fastai.ipynb.

# %% auto 0
__all__ = ['MaskedDf', 'BlockDfTransform', 'AddGapTransform', 'MaskedTensor', 'MaskedDf2Tensor', 'get_stats', 'NormalizeMasked',
           'imp_pipeline', 'make_dataloader', 'ListNormal', 'KalmanLoss', 'to_meteo_imp_metric', 'SaveParams',
           'Float64Callback']

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 9
from fastcore.transform import *
from fastcore.basics import *
from fastcore.foundation import *
from fastcore.all import *

from fastai.tabular import *

from ..data import read_fluxnet_csv, hai_path

from collections import namedtuple

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 11
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 14
class BlockDfTransform(ItemTransform):
    """divide timeseries DataFrame into blocks"""
    def __init__(self, df, block_len=200): 
        self.df = df 
        self.block_len = block_len
        self.n = len(df)
        
    def encodes(self, i:int) -> pd.DataFrame:       
        start = i * self.block_len
        end = (i+1) * self.block_len
        assert end <= self.n 
        
        block = self.df[start:end]
        
        return block

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 21
def _make_random_gap(
    gap_length: int, # The length of the gap
    total_length: int, # The total number of observations
    gap_start: int = None # Optional start of gap
): # (total_length) array of bools to indicicate if the data is missing or not
    "Add a continous gap of ginve length at random position"
    if(gap_length >= total_length):
        return np.repeat(True, total_length)
    gap_start = np.random.randint(total_length - gap_length) if gap_start is None else gap_start
    return np.hstack([
        np.repeat(False, gap_start),
        np.repeat(True, gap_length),
        np.repeat(False, total_length - (gap_length + gap_start))
    ])

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 22
from fastcore.basics import *

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 23
MaskedDf = namedtuple('MaskedDf', 'data mask')

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 24
class AddGapTransform(ItemTransform):
    """Adds a random gap to a `TimeSTensor`"""
    def __init__(self,
                variables,
                gap_length,
                ):
        store_attr()
    def encodes(self, df: pd.DataFrame):
        gap = _make_random_gap(self.gap_length, df.shape[0])
        mask = np.ones_like(df, dtype=bool)
        col_sel = L(*df.columns).argwhere(lambda x: x in self.variables)
        mask[np.argwhere(gap), col_sel] = False
        return MaskedDf(df, pd.DataFrame(mask, index=df.index, columns=df.columns))

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 30
@patch
def tidy(self: MaskedDf):
    data = self.data.reset_index().melt("time")
    mask = self.mask.reset_index().melt("time", value_name="is_present")
    
    return pd.merge(data, mask, on=["time", "variable"])

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 32
import altair as alt
from altair import datum

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 33
def def_selection():
    return alt.selection_interval(bind="scales")

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 34
def plot_rug(df, sel = def_selection(), props = {}):
    if 'height' in props:
        props = props.copy() 
        props.pop('height') # rug should have default heigth
    return alt.Chart(df).mark_tick(
            color='black',
        ).encode(
            x = "time",
            color = alt.condition(datum.is_present, alt.value('white'), alt.value('black'))
        ).add_selection(
            sel
        ).properties(**props) 

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 38
def plot_line(df, only_present=True, y_label = "", sel = def_selection(), props = {}):
    # df = df[df.is_present] if only_present else df
    # TODO remove onle_present
    return alt.Chart(df).mark_line().encode(
        x = "time",    
        y = alt.Y("value", title = y_label, scale=alt.Scale(zero=False)),
        color='variable'
    ).add_selection(
        sel
    ).properties(
        **props
    )#.transform_filter(
    #     datum.is_present
    # )

    

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 40
def plot_variable(df, variable, title="", y_label="", sel = None, props = {}):
    df = df[df.variable == variable]
    sel = ifnone(sel, def_selection())
    # rug = plot_rug(df, sel, props)
    points = plot_points(df, y_label, sel, props)
    line = plot_line(df, True, y_label, sel, props)
    
    return (points + line).properties(title=title)
    
    # return alt.VConcatChart(vconcat=[(points + line), rug], spacing=-10).properties(title=title)

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 42
@patch
def show(self: MaskedDf, ax=None, ctx=None, 
        n_cols: int = 3,
        bind_interaction: bool =True, # Whether the sub-plots for each variable should be connected for zooming/panning
        props:dict = None # additional properties (eg. size) for altair plot
       ) -> alt.Chart:
    
    df = self.tidy()
    
    props = ifnone(props, {'width': 180, 'height': 100})
   
    plot_list = [alt.hconcat() for _ in range(0, self.data.shape[0], n_cols)]
    selection_scale = alt.selection_interval(bind="scales", encodings=['x']) if bind_interaction else None
    for idx, variable in enumerate(self.data.columns):
        plot = plot_variable(df,
                            variable,
                            title = variable,
                            y_label = variable,
                            sel = selection_scale,
                            props=props)
        
        plot_list[idx // n_cols] |= plot
    
    plot = alt.vconcat(*plot_list)
    
    return plot

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 56
class MaskedTensor(fastuple):
    pass

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 57
class MaskedDf2Tensor(ItemTransform):
    def setups(self, items):
        self.columns = list(items[0].data.columns)
    def encodes(self, df: MaskedDf) -> MaskedTensor:
        data = torch.tensor(df[0].to_numpy())
        mask = torch.tensor(df[1].to_numpy())
        return MaskedTensor(data, mask)
        
    def decodes(self, x: MaskedTensor) -> MaskedDf:
        data = pd.DataFrame(x[0].detach().cpu().numpy(), columns = self.columns)
        mask = x[1].numpy()
        return MaskedDf(mask, data)

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 62
from ..utils import *

from torch import Tensor

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 63
def get_stats(df):
    return torch.tensor(df.mean(axis=0).to_numpy()), torch.tensor(df.std(axis=0).to_numpy())

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 64
class NormalizeMasked(ItemTransform):
    "Normalize/denorm MaskedTensor column-wise "
    parameters,order = L('mean', 'std'),99
    def __init__(self, mean=None, std=None, axes=(0,)): store_attr()

    def encodes(self, x:MaskedTensor):
        return MaskedTensor((x[0]-self.mean) / self.std, x[1])

    def encodes(self, x):
        return MaskedTensor((x[0]-self.mean) / self.std, x[1])
    
    def decodes(self, x:ListNormal):
        mean = (x.std-self.mean) / self.std
        std = x.cov * self.std
        
        return ListNormal(mean, std)

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 70
from fastai.data.transforms import *

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 72
def imp_pipeline(df,
                 block_len,
                 gap_len
                ):
    block_ids = list(range(0, (len(df) // block_len) - 1))
    return [BlockDfTransform(df, block_len),
            AddGapTransform(['TA','SW_IN'], gap_len),
            MaskedDf2Tensor,
            NormalizeMasked(*get_stats(df))], block_ids

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 89
def make_dataloader(df, block_len, gap_len, bs=10):
    pipeline, block_ids = imp_pipeline(df, block_len, gap_len)
    
    splits = RandomSplitter()(block_ids)
    ds = Datasets(block_ids, [pipeline, pipeline], splits=splits)
    
    return ds.dataloaders(bs=bs)
    

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 96
from .filter import *
from torch.distributions import MultivariateNormal

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 97
class ListNormal(fastuple):
    pass

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 98
@patch
def _predict_filter(self: KalmanFilter, data, mask, check_args=None):
    """Predict every obsevation using only the filter step"""
    # use the predicted state not the filtered state!
    pred_state_mean, pred_state_cov, _, _ = self._filter_all(data, mask, check_args)
    
    means = torch.empty_like(data)
    covs = torch.empty((data.shape[0], data.shape[1], data.shape[1]), dtype=data.dtype, device=data.device) 
    for t in range(data.shape[0]):
        means[t], covs[t] = self._obs_from_state(pred_state_mean[t], pred_state_cov[t], check_args)
    return ListNormal(means, torch.diagonal(covs, dim1=-2, dim2=-1))

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 99
@patch
def forward(self: KalmanFilter, masked_data: MaskedTensor):
    data, mask = masked_data
    use_smooth = self.use_smooth if hasattr(self, 'use_smooth') else True
    means = torch.empty_like(data)
    covs = torch.empty(data.shape[0], data.shape[1], data.shape[2], dtype=data.dtype, device=data.device)
    for i in range(data.shape[0]):
        times = torch.arange(data[i].shape[0])
        mean, cov = (self.predict(obs=data[i], mask=mask[i], smooth=True, check_args=self.check_args) if use_smooth
                        else self._predict_filter(data[i], mask[i], self.check_args))
        
        means[i], covs[i] = mean, cov
    return ListNormal(means, covs)

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 135
class KalmanLoss():
    def __init__(self,
                 only_gap:bool=True, # loss for all predictions or only gap?
                ):
        store_attr()
    
    def __call__(self, pred: ListNormal, target: MaskedTensor):
        data, mask = target
        means, stds = pred
        
        # make a big vector with all variables and observations and compute ll
        mask = mask.flatten() if self.only_gap else torch.fill(mask, True).flatten()
        obs = data.flatten()[mask]
        means = data.flatten()[mask]
        stds = stds.flatten()[mask] 
        
        return MultivariateNormal(means, torch.diag(stds)).log_prob(obs)
        

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 140
def to_meteo_imp_metric(metric):
    def meteo_imp_metric(inp, targ):
        return metric(imp[0], targ[0]) # first element are the means, first element 

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 143
from fastai.callback.all import *

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 144
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 147
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 149
from fastai.learner import * 

from fastai.tabular.all import *

from fastai.tabular.learner import *

from fastai.callback.progress import ShowGraphCallback

# %% ../../lib_nbs/kalman/03_Kalman_fastai.ipynb 188
class Float64Callback(Callback):
    order = Recorder.order + 10 # run 
    def before_fit(self):
        self.recorder.smooth_loss.val = torch.tensor(0, dtype=torch.float64) # default is a float 32
