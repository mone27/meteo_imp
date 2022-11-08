# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/01_Learner.ipynb.

# %% auto 0
__all__ = ['NormParam', 'GPFALearner']

# %% ../lib_nbs/01_Learner.ipynb 4
import torch
from torch import Tensor
from torch.distributions import MultivariateNormal 

import gpytorch
from .gpfa import *
from .data_preparation import Normalizer

from collections import namedtuple
import math

from fastcore.foundation import *
from tqdm.auto import tqdm
from fastcore.foundation import patch

import matplotlib.pyplot as plt
from pathlib import Path

import pandas as pd
import numpy as np
import altair as alt

# %% ../lib_nbs/01_Learner.ipynb 8
class GPFALearner():
    def __init__(self,
                 X: Tensor, # (n_features * n_obs) Multivariate time series
                 T: Tensor = None, # (n_obs) Vector of time of observations.
                 # If none each observation are considered to be at the same distance
                 latent_dims: int = 1, # Number of latent variables in GPFA
                 model = GPFA, # sub-class of `GPFA`
                 var_names = None # for model info
                ):
        self.prepare_X(X)
        if T is None: self.default_time(X)
        else: self.T = T
        self.T = self.T.to(X.device) # to support GPUs
        self.latent_dims = latent_dims
        self.var_names = var_names
        
        self.likelihood = gpytorch.likelihoods.GaussianLikelihood()
        self.model = model(self.T, self.X, self.likelihood, self.n_features, latent_dims=latent_dims)
        
    @torch.no_grad()
    def prepare_X(self, X):
        self.norm = Normalizer(X)
        X = self.norm.normalize(X)
        # flatten Matrix to vector
        self.X = X.reshape(-1) 
        self.n_features = X.shape[1]
        
    def default_time(self, X):
        self.T = torch.arange(X.shape[0])
        
    
    def train(self, n_iter=100, lr=0.1):
        # need to enable training mode
        self.model.train()
        self.likelihood.train()
        
        # Use the adam optimizer
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr) 
        
        if not hasattr(self, 'losses'):
            self.losses = torch.zeros(n_iter)
            self.model_infos = [None for _ in range(n_iter)] # put one element so it can be indexed from 0
            offset = 0
        else:
            offset = self.losses.shape[0]
            self.losses = torch.concat([self.losses, torch.zeros(n_iter)])
            self.model_infos.extend([None for _ in range(n_iter)])
            
        
        # "Loss" for GPs - the marginal log likelihood
        mll = gpytorch.mlls.ExactMarginalLogLikelihood(self.likelihood, self.model)
        for i in tqdm(range(n_iter)):
            # Zero gradients from previous iteration
            optimizer.zero_grad()
            # Output from model
            output = self.model(self.T)
            # Calc loss and backprop gradients
            loss = -mll(output, self.X)
            self.losses[i + offset] = loss.detach()
            loss.backward()
            self.model_infos[i + offset] = self.model.get_info(self.var_names)

            optimizer.step()
        

# %% ../lib_nbs/01_Learner.ipynb 21
@torch.no_grad() # don't calc gradients on predictions
@patch()
def predict_raw(self: GPFALearner, T):
    self.model.eval()
    self.likelihood.eval()
    return self.likelihood(self.model(T))

# %% ../lib_nbs/01_Learner.ipynb 28
NormParam = namedtuple("NormalParameters", ["mean", "std"])

# %% ../lib_nbs/01_Learner.ipynb 30
@torch.no_grad() # needed because raw output still has gradients attached
@patch
def prediction_from_raw(self: GPFALearner, raw_mean, raw_std):
    """ Takes a raw prediction and produces and final prediction, by reshaping and reversing normalization"""
    raw_std = raw_std.reshape(-1, self.n_features)
    raw_mean = raw_mean.reshape(-1, self.n_features)
    
    pred_mean = self.norm.reverse_normalize(raw_mean)
    pred_std = self.norm.reverse_normalize_std(raw_std)
    
    #remove pytorch gradients
    return NormParam(pred_mean.detach(), pred_std.detach())

# %% ../lib_nbs/01_Learner.ipynb 52
def conditional_guassian(gauss: MultivariateNormal,
                         obs,
                         idx # Boolean tensor specifying for each variable is observed (True) or not (False)
                        ):
    μ = gauss.mean
    Σ = gauss.covariance_matrix
    # check idx same size of mu
    μ_x = μ[~idx]
    μ_o = μ[idx]
    
    Σ_xx = Σ[~idx,:][:, ~idx]
    Σ_xo = Σ[~idx,:][:, idx]
    Σ_ox = Σ[idx,:][:, ~idx]
    Σ_oo = Σ[idx,:][:, idx]
    
    Σ_oo_inv = torch.linalg.inv(Σ_oo)
    
    mean = μ_x + Σ_xo@Σ_oo_inv@(obs - μ_o)
    cov = Σ_xx - Σ_xo@Σ_oo_inv@Σ_ox
    
    return MultivariateNormal(mean, cov)
    

# %% ../lib_nbs/01_Learner.ipynb 57
def _merge_raw_cond_pred(pred_raw,
                         pred_cond,
                         obs,
                         idx
                        ) -> NormParam:
    """This functions merges a complete predition with a conditional prediction and the observations.
    For the observations the std is considered to be 0 """
    mean = torch.zeros_like(pred_raw.mean) # get shape from complete prediction
    mean[~idx] = pred_cond.mean # add predictions
    mean[idx] = obs # add observations
    
    std = torch.zeros_like(pred_raw.stddev)
    std[~idx] = pred_cond.stddev
    std[idx] = 0 # uncertainty of an oberservation doesn't make sense
    
    return NormParam(mean, std)

# %% ../lib_nbs/01_Learner.ipynb 62
@patch
def _normalize_obs(self: GPFALearner,
                   obs, # (n_obs)
                   idx
                  ) -> Tensor: # (n_obs)
    """ reshape the observations so they can normalized"""
    obs_compl = torch.zeros_like(idx, dtype=obs.dtype)
    obs_compl[idx] = obs
    obs_compl = obs_compl.reshape(-1, self.n_features)
    obs_norm = self.norm.normalize(obs_compl)
    return obs_norm.reshape(-1)[idx]

# %% ../lib_nbs/01_Learner.ipynb 67
@patch
def predict(self: GPFALearner,
            T: Tensor, # (n_pred) time where prediction is needed
            # (n_obs_pred) Optional - if at the times of the prediction there are some observations
            # array with the values of observations to condition distribution
            obs: Tensor = None,
            # ((n_pred*n_features)) Optional - necessary if obs are present
            # Boolean array that is True where an observation is present and False where a prediction is needed
            # This is a 1D array with the length equal to n_pred (number time steps to predict) times n_features
            idx: Tensor = None
           ):
    pred_raw = self.predict_raw(T)
    
    # Conditional observations
    if obs is not None and idx is not None:
        # observations needs to be normalized before can be used with the raw prediction!
        obs_norm = self._normalize_obs(obs, idx)
        pred_cond = conditional_guassian(pred_raw, obs_norm, idx)

        pred_merge = _merge_raw_cond_pred(pred_raw, pred_cond, obs_norm, idx)
    else:
        pred_merge = NormParam(pred_raw.mean, pred_raw.stddev)
    
    return self.prediction_from_raw(pred_merge.mean, pred_merge.std)

# %% ../lib_nbs/01_Learner.ipynb 80
@patch
def cuda(self: GPFALearner):
    """Moves all learner to gpu"""
    for par in ['T', 'X', 'model', 'likelihood']:
        self.__getattribute__(par).cuda()
    self.norm.x_mean.cuda()
    self.norm.x_std.cuda()

# %% ../lib_nbs/01_Learner.ipynb 93
@patch
def save(self: GPFALearner, path: Path|str):
    model_state = self.model.state_dict()
    ll_state = self.likelihood.state_dict()
    torch.save((model_state, ll_state), path)
@patch
def load(self: GPFALearner, path: Path|str):
    model_state, ll_state = torch.load(path)
    self.model.load_state_dict(model_state)
    self.likelihood.load_state_dict(ll_state)

# %% ../lib_nbs/01_Learner.ipynb 100
@patch
def plot_progress(self: GPFALearner, size={'width': 250, 'height': 120}):
    
    sel = alt.selection_interval(bind="scales", encodings=['x'])
    
    plt_losses = alt.Chart(
        pd.DataFrame({'loss': self.losses, 'n_iter': range(self.losses.shape[0])})
    ).mark_line().encode(
        x = 'n_iter',
        y = 'loss'
    ).properties(title="loss", **size).add_selection(sel)
    
    out_plot = [plt_losses]
    for info_name in self.model_infos[0].keys():
        
        values = pd.concat([info[info_name].assign(n_iter=i) for i, info in enumerate(self.model_infos)])
        
        if values.shape[1] == 2:
            # only one column so add fake facet
            values.insert(0, 'info', info_name)
        
        facet = values.columns[0] # first column is either latent or variable
        
        values = values.melt([facet, 'n_iter'], var_name='prop')
        
        plt = alt.Chart(values).mark_line().encode(
            x = 'n_iter',
            y = 'value',
            color = 'prop',
            facet = facet
        ).properties(title=info_name, **size).add_selection(sel)
        
        out_plot.append(plt)
    
    return alt.VConcatChart(vconcat=out_plot).resolve_scale(
        color='independent'
    )
    
