# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/kalman/10_fastai.ipynb.

# %% auto 0
__all__ = ['BlockDfTransform', 'AddGapTransform', 'MaskedDf2Tensor', 'get_stats', 'NormalizeMasked', 'imp_pipeline',
           'make_dataloader', 'KalmanLoss', 'to_msk_metric', 'SaveParams', 'Float64Callback']

# %% ../../lib_nbs/kalman/10_fastai.ipynb 5
from ..utils import *
from ..gaussian import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 9
from fastcore.transform import *
from fastcore.basics import *
from fastcore.foundation import *
from fastcore.all import *
from fastai.tabular import *
from fastai.torch_core import default_device

from ..data import read_fluxnet_csv, hai_path

import collections

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# %% ../../lib_nbs/kalman/10_fastai.ipynb 13
class BlockDfTransform(Transform):
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 25
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 26
from fastcore.basics import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 27
class AddGapTransform(Transform):
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 34
@patch
def tidy(self: MaskedDf):
    data = self.data.reset_index().melt("time")
    mask = self.mask.reset_index().melt("time", value_name="is_present")
    
    return pd.merge(data, mask, on=["time", "variable"])

# %% ../../lib_nbs/kalman/10_fastai.ipynb 37
import altair as alt
from altair import datum

# %% ../../lib_nbs/kalman/10_fastai.ipynb 38
def def_selection():
    return alt.selection_interval(bind="scales")

# %% ../../lib_nbs/kalman/10_fastai.ipynb 39
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 43
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

    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 45
def plot_variable(df, variable, title="", y_label="", sel = None, props = {}):
    df = df[df.variable == variable]
    sel = ifnone(sel, def_selection())
    # rug = plot_rug(df, sel, props)
    points = plot_points(df, y_label, sel, props)
    line = plot_line(df, True, y_label, sel, props)
    
    return (points + line).properties(title=title)
    
    # return alt.VConcatChart(vconcat=[(points + line), rug], spacing=-10).properties(title=title)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 47
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

# %% ../../lib_nbs/kalman/10_fastai.ipynb 62
class MaskedDf2Tensor(Transform):
    def setups(self, items):
        self.columns = list(items[0].data.columns)
    def encodes(self, df: MaskedDf) -> MaskedTensor:
        data = torch.tensor(df.data.to_numpy())
        mask = torch.tensor(df.mask.to_numpy())
        return MaskedTensor(data, mask)
        
    def decodes(self, x: MaskedTensor) -> MaskedDf:
        data = pd.DataFrame(x.data.detach().cpu().numpy(), columns = self.columns)
        mask = pd.DataFrame(x.mask.cpu().numpy(), columns = self.columns)
        return MaskedDf(data, mask)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 74
from ..utils import *
from fastai.torch_core import to_cpu

from torch import Tensor

# %% ../../lib_nbs/kalman/10_fastai.ipynb 80
def get_stats(df, device='cpu'):
    return torch.tensor(df.mean(axis=0).to_numpy(), device=device), torch.tensor(df.std(axis=0).to_numpy(), device=device)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 81
class NormalizeMasked(Transform):
    "Normalize/denorm MaskedTensor column-wise "
    @property
    def name(self): return f"{super().name} -- {getattr(self,'__stored_args__',{})}"

    def __init__(self, mean=None, std=None): store_attr()

    def encodes(self, x:MaskedTensor)-> MaskedTensor:
        return MaskedTensor((x.data -self.mean) / self.std, x.mask)

    def decodes(self, x:MaskedTensor)->MaskedTensor:
        f = to_cpu if x[0].device.type=='cpu' else noop
        return MaskedTensor(x[0] * f(self.std) + f(self.mean), x[1])
    
    def decodes(self, x:NormalsParams):
        print("decoding")
        f = to_cpu if x[0].device.type=='cpu' else noop
        mean = x.mean * f(self.std) + f(self.mean)
        std = x.std * (self.std)
        
        return NormalsParams(mean, std)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 93
from fastai.data.transforms import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 95
def imp_pipeline(df,
                 block_len,
                 gap_len
                ):
    block_ids = list(range(0, (len(df) // block_len) - 1))
    return [BlockDfTransform(df, block_len),
            AddGapTransform(['TA','SW_IN'], gap_len),
            MaskedDf2Tensor,
            NormalizeMasked(*get_stats(df))], block_ids

# %% ../../lib_nbs/kalman/10_fastai.ipynb 116
def make_dataloader(df, block_len, gap_len, bs=10):
    pipeline, block_ids = imp_pipeline(df, block_len, gap_len)
    
    splits = RandomSplitter()(block_ids)
    ds = Datasets(block_ids, [pipeline, pipeline], splits=splits)
    
    return ds.dataloaders(bs=bs)
    

# %% ../../lib_nbs/kalman/10_fastai.ipynb 123
from .filter import *
from torch.distributions import MultivariateNormal

# %% ../../lib_nbs/kalman/10_fastai.ipynb 124
@patch
def _predict_filter(self: KalmanFilter, data, mask):
    """Predict every obsevation using only the filter step"""
    # use the predicted state not the filtered state!
    obs, mask = self._parse_obs(data, mask)
    pred_state_mean, pred_state_cov, _, _ = self._filter_all(obs, mask)
    mean, cov = self._obs_from_state(ListMNormal(pred_state_mean.squeeze(-1), pred_state_cov))
    
    return ListNormal(mean, cov2std(cov))

# %% ../../lib_nbs/kalman/10_fastai.ipynb 125
@patch
def forward(self: KalmanFilter, masked_data: MaskedTensor):
    data, mask = masked_data
    assert not data.isnan().any()
    use_smooth = self.use_smooth if hasattr(self, 'use_smooth') else True
    
    mean, std = (self.predict(obs=data, mask=mask, smooth=True) if use_smooth
                        else self._predict_filter(data, mask))
    return NormalsParams(mean, std) # to have fastai working this needs to be a tuple subclass

# %% ../../lib_nbs/kalman/10_fastai.ipynb 156
class KalmanLoss():
    def __init__(self,
                 only_gap:bool=True, # loss for all predictions or only gap
                 reduction:str='sum' # one of ['sum', 'mean', 'none']
                ):
        store_attr()
    
    def __call__(self, pred: NormalsParams, target: MaskedTensor):
        data, mask = target
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
        mask = mask.flatten() if self.only_gap else torch.fill(mask, True).flatten()
        obs = data.flatten()[mask]
        mean = data.flatten()[mask]
        std = std.flatten()[mask] 
        
        return MultivariateNormal(mean, torch.diag(std)).log_prob(obs)
        

# %% ../../lib_nbs/kalman/10_fastai.ipynb 170
def to_msk_metric(metric, name):
    def msk_metric(imp, targ):
        return metric(imp[0], targ[0]) # first element are the means
    msk_metric.__name__ = name
    return msk_metric

# %% ../../lib_nbs/kalman/10_fastai.ipynb 179
from fastai.callback.all import *

# %% ../../lib_nbs/kalman/10_fastai.ipynb 180
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 181
class SaveParams(Callback):
    def __init__(self, param_name):
        super().__init__()
        self.params = []
        self.param_name = param_name
    def after_batch(self):
        param = getattr(self.model, self.param_name).detach()
        self.params.append(param)

# %% ../../lib_nbs/kalman/10_fastai.ipynb 185
from fastai.learner import * 

from fastai.tabular.all import *

from fastai.tabular.learner import *

from fastai.callback.progress import ShowGraphCallback

# %% ../../lib_nbs/kalman/10_fastai.ipynb 311
class Float64Callback(Callback):
    order = Recorder.order + 10 # run after Recorder 
    def before_fit(self):
        self.recorder.smooth_loss.val = torch.tensor(0, dtype=torch.float64) # default is a float 32