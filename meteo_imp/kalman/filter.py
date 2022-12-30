# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/kalman/00_filter.ipynb.

# %% auto 0
__all__ = ['KalmanFilter']

# %% ../../lib_nbs/kalman/00_filter.ipynb 3
from fastcore.test import *
from fastcore.basics import *
from ..utils import *
from ..gaussian import *
from ..data_preparation import MeteoDataTest
from typing import *

import numpy as np
import pandas as pd
import torch
from torch import Tensor
from torch.distributions import MultivariateNormal

# %% ../../lib_nbs/kalman/00_filter.ipynb 9
class KalmanFilter(torch.nn.Module):
    """Base class for Kalman Filter and Smoother using PyTorch"""
    def __init__(self,
            trans_matrix: Tensor,    # [n_dim_state,n_dim_state] $A$, state transition matrix 
            obs_matrix: Tensor,      # [n_dim_obs, n_dim_state] $H$, observation matrix
            trans_cov: Tensor,       # [n_dim_state, n_dim_state] $Q$, state trans covariance matrix
            obs_cov: Tensor,         # [n_dim_obs, n_dim_obs] $R$, observations covariance matrix
            trans_off: Tensor,       # [n_dim_state] $b$, state transition offset
            obs_off: Tensor,         # [n_dim_obs] $d$, observations offset
            init_state_mean: Tensor, # [n_dim_state] $\mu_0$
            init_state_cov: Tensor,  # [n_dim_state, n_dim_state] $\Sigma_0$
            n_dim_state: int = None, # Number of dimensions for state - defaults to 1 if cannot be infered from parameters
            n_dim_obs: int = None,   # Number of dimensions for observations - defaults to 1 if cannot be infered from parameters
            cov_checker: CheckPosDef = CheckPosDef()
                ):
        
        super().__init__()
        # check parameters are consistent
        self.n_dim_state = determine_dimensionality(
            [(trans_matrix, array2d, -2),
             (trans_off, array1d, -1),
             (trans_cov, array2d, -2),
             (init_state_mean, array1d, -1),
             (init_state_cov, array2d, -2),
             (obs_matrix, array2d, -1)],
            n_dim_state
        )
        self.n_dim_obs = determine_dimensionality(
            [(obs_matrix, array2d, -2),
             (obs_off, array1d, -1),
             (obs_cov, array2d, -2)],
            n_dim_obs
        )
        
        params = {
        #name               value             constraint
        'trans_matrix':     [trans_matrix,    None    ],
        'trans_off':        [trans_off,       None    ],
        'trans_cov':        [trans_cov,       PosDef()],
        'obs_matrix':       [obs_matrix,      None    ],
        'obs_off':          [obs_off,         None    ],
        'obs_cov':          [obs_cov,         PosDef()],
        'init_state_mean':  [init_state_mean, None    ],
        'init_state_cov':   [init_state_cov,  PosDef()],
        }
        self._init_params(params)
        
        self.cov_checker = cov_checker
        
    def _init_params(self, params):
        for name, (value, constraint) in params.items():
            if constraint is not None:
                name, value = self._init_constraint(name, value, constraint)
            self._init_param(name, value, train=True)    
    
    def _init_param(self, param_name, value, train):
        self.register_parameter(param_name, torch.nn.Parameter(value, requires_grad=train))
    
    ### === Constraints utils
    def _init_constraint(self, param_name, value, constraint):
        name = param_name + "_raw"
        value = constraint.inverse_transform(value)
        setattr(self, param_name + "_constraint", constraint)
        return name, value
    
    def _get_constraint(self, param_name):
        constraint = getattr(self, param_name + "_constraint")
        raw_value = getattr(self, param_name + "_raw")
        return constraint.transform(raw_value)
    
    def _set_constraint(self, param_name, value, train=True):
        constraint = getattr(self, param_name + "_constraint")
        raw_value = constraint.inverse_transform(value)
        self._init_param(param_name + "_raw", raw_value, train)
    
    ### === Convenience functions to get and set parameters that have a constraint
    @property
    def trans_cov(self): return self._get_constraint('trans_cov')
    @trans_cov.setter
    def trans_cov(self, value): return self._set_constraint('trans_cov', value)

    @property
    def obs_cov(self): return self._get_constraint('obs_cov')
    @obs_cov.setter
    def obs_cov(self, value): return self._set_constraint('obs_cov', value)
    
    @property
    def init_state_cov(self): return self._get_constraint('init_state_cov')
    @init_state_cov.setter
    def init_state_cov(self, value): return self._set_constraint('init_state_cov', value)
    
    
    ### === Utility Func    
    def _parse_obs(self, obs, mask=None):
        """maybe get mask from `nan`"""
        if mask is None: mask = ~torch.isnan(obs)
        # TODO incorrect support for 2d input!!!!!!
        assert obs.dim() == 3
        obs, mask = torch.atleast_3d(obs), torch.atleast_3d(mask)
        return obs, mask
    
    def __repr__(self):
        return f"""Kalman Filter
        N dim obs: {self.n_dim_obs}, N dim state: {self.n_dim_state}"""

# %% ../../lib_nbs/kalman/00_filter.ipynb 13
@patch(cls_method=True)
def init_random(cls: KalmanFilter, n_dim_obs, n_dim_state, dtype=torch.float32):
    """kalman filter with random parameters"""
    params = {
        'trans_matrix':    torch.rand(n_dim_state, n_dim_state, dtype=dtype),
        'trans_off':       torch.rand(n_dim_state, dtype=dtype),        
        'trans_cov':       to_posdef(torch.rand(n_dim_state, n_dim_state, dtype=dtype)),        
        'obs_matrix':      torch.rand(n_dim_obs, n_dim_state, dtype=dtype),
        'obs_off':         torch.rand(n_dim_obs, dtype=dtype),          
        'obs_cov':         to_posdef(torch.rand(n_dim_obs, n_dim_obs, dtype=dtype)),            
        'init_state_mean': torch.rand(n_dim_state, dtype=dtype),        
        'init_state_cov':  to_posdef(torch.rand(n_dim_state, n_dim_state, dtype=dtype)),
    } 
    return cls(**params) 
        

# %% ../../lib_nbs/kalman/00_filter.ipynb 21
def get_test_data(n_obs = 10, n_dim_obs=3, p_missing=.3, bs=2, dtype=torch.float32, device='cpu'):
    data = torch.rand(bs, n_obs, n_dim_obs, dtype=dtype, device=device)
    mask = torch.rand(bs, n_obs, n_dim_obs, device=device) > p_missing
    # data[~mask] = torch.nan # ensure that the missing data cannot be used
    return data, mask

# %% ../../lib_nbs/kalman/00_filter.ipynb 26
from datetime import datetime
def _filter_predict(trans_matrix,
                    trans_cov,
                    trans_off,
                    curr_state_mean,
                    curr_state_cov,
                    control_matrix=0,
                    control=0,
                    cov_checker=CheckPosDef()):
    r"""Calculate the state at time `t+1` given the state at time `t`"""
    pred_state_mean = trans_matrix.unsqueeze(0) @ curr_state_mean + trans_off.unsqueeze(-1)
    pred_state_cov =  trans_matrix.unsqueeze(0) @ curr_state_cov @ trans_matrix.unsqueeze(0).mT + trans_cov.unsqueeze(0)

    cov_checker.check(pred_state_cov, caller='filter_predict')
    return (pred_state_mean, pred_state_cov)

# %% ../../lib_nbs/kalman/00_filter.ipynb 35
def _filter_correct(obs_matrix,
                    obs_cov,
                    obs_off,
                    pred_state_mean,
                    pred_state_cov,
                    obs,
                    mask,
                    cov_checker=CheckPosDef()):
    """Update state at time `t` given observations at time `t`"""
    
    pred_obs_mean = obs_matrix.unsqueeze(0) @ pred_state_mean + obs_off.unsqueeze(-1) # extra dim needed to hae batched matmul working
    pred_obs_cov = obs_matrix.unsqueeze(0) @ pred_state_cov @ obs_matrix.unsqueeze(0).mT + obs_cov

    kalman_gain = pred_state_cov @ obs_matrix.T @ torch.inverse(pred_obs_cov) # torch.cholesky_inverse(torch.linalg.cholesky(pred_obs_cov))

    corr_state_mean = pred_state_mean + kalman_gain @ (obs.unsqueeze(-1) - pred_obs_mean)
    corr_state_cov = pred_state_cov - kalman_gain @ obs_matrix @ pred_state_cov
    
    mask = mask.all(-1) # if any observation is missing need to discard the whole vector
    corr_state_mean[~mask] = pred_state_mean[~mask]
    corr_state_cov[~mask] = pred_state_cov[~mask]

    cov_checker.check(pred_state_cov, caller='filter_correct')
    return (kalman_gain, corr_state_mean, corr_state_cov)

# %% ../../lib_nbs/kalman/00_filter.ipynb 44
def _times2batch(x):
    """Permutes `x` so that the first dimension is the number of batches and not the times"""
    return x.permute(1,0,-2,-1)

# %% ../../lib_nbs/kalman/00_filter.ipynb 45
def _filter(trans_matrix, obs_matrix,
            trans_cov, obs_cov,
            trans_off, obs_off,
            init_state_mean, init_state_cov,
            obs, mask,
            cov_checker=CheckPosDef()
           ) ->Tuple[List, List, List, List]: # pred_state_means, pred_state_covs, filt_state_means, filt_state_covs
    """Filter observations using kalman filter """
    n_timesteps = obs.shape[-2]
    bs = obs.shape[0]
    # lists are mutable so need to copy them
    pred_state_means, pred_state_covs, filt_state_means, filt_state_covs = [[None for _ in range(n_timesteps)].copy() for _ in range(4)] 

    for t in range(n_timesteps):
        if t == 0:
            pred_state_means[t], pred_state_covs[t] = torch.stack([init_state_mean]*bs).unsqueeze(-1), torch.stack([init_state_cov]*bs)
        else:
            pred_state_means[t], pred_state_covs[t] = _filter_predict(trans_matrix, trans_cov, trans_off,
                                                                      filt_state_means[t - 1], filt_state_covs[t - 1],
                                                                      cov_checker.add_args(t=t))

        _, filt_state_means[t], filt_state_covs[t] = _filter_correct(obs_matrix, obs_cov, obs_off,
                                                                     pred_state_means[t], pred_state_covs[t],
                                                                     obs[:,t,:], mask[:,t,:],
                                                                     cov_checker.add_args(t=t))
    
    ret = list(maps(torch.stack, _times2batch, (pred_state_means, pred_state_covs, filt_state_means, filt_state_covs,)))
    return ret

# %% ../../lib_nbs/kalman/00_filter.ipynb 52
@patch
def _filter_all(self: KalmanFilter, obs, mask=None
               ) ->Tuple[List, List, List, List]: # pred_state_means, pred_state_covs, filt_state_means, filt_state_covs
    """ wrapper around `_filter`"""
    obs, mask = self._parse_obs(obs, mask)
    return _filter(
            self.trans_matrix, self.obs_matrix,
            self.trans_cov, self.obs_cov,
            self.trans_off, self.obs_off,
            self.init_state_mean, self.init_state_cov,
            obs, mask,
            self.cov_checker
        )

# %% ../../lib_nbs/kalman/00_filter.ipynb 57
@patch
def filter(self: KalmanFilter,
          obs: Tensor, # [n_timesteps, n_dim_obs] obs for times [0...n_timesteps-1]
          mask = None,
          ) -> ListMNormal: # Filtered state
    """Filter observation"""
    _, _, filt_state_means, filt_state_covs = self._filter_all(obs, mask)
    return ListMNormal(filt_state_means.squeeze(-1), filt_state_covs)

# %% ../../lib_nbs/kalman/00_filter.ipynb 62
def _smooth_update(trans_matrix,                # [n_dim_state, n_dim_state]
                   filt_state: MNormal,         # [n_dim_state] filtered state at time `t`
                   pred_state: MNormal,         # [n_dim_state] state before filtering at time `t + 1` (= using the observation until time t)
                   next_smoothed_state: Normal, # [n_dim_state] smoothed state at time  `t+1`
                   cov_checker = CheckPosDef()
                   ) -> MNormal:                # mean and cov of smoothed state at time `t`
    """Correct a pred state with a Kalman Smoother update"""
    kalman_smoothing_gain = filt_state.cov @ trans_matrix.unsqueeze(0).mT @ torch.inverse(pred_state.cov) # torch.cholesky_inverse(torch.linalg.cholesky(pred_state.cov))

    smoothed_state_mean = filt_state.mean + kalman_smoothing_gain @ (next_smoothed_state.mean - pred_state.mean)
    smoothed_state_cov = filt_state.cov + kalman_smoothing_gain @ (next_smoothed_state.cov - pred_state.cov) @ kalman_smoothing_gain.mT

    cov_checker.check(smoothed_state_cov, caller='smooth_update')
    
    return MNormal(smoothed_state_mean, smoothed_state_cov)

# %% ../../lib_nbs/kalman/00_filter.ipynb 67
def _smooth(trans_matrix, # `[n_dim_state, n_dim_state]`
            filt_state: ListMNormal, # `[n_timesteps, n_dim_state]`
                # `filt_state_means[t]` is the state estimate for time t given obs from times `[0...t]`
            pred_state: ListMNormal, # `[n_timesteps, n_dim_state]`
                # `pred_state_means[t]` is the state estimate for time t given obs from times `[0...t-1]`
            cov_checker = CheckPosDef()
           ) -> ListMNormal: # `[n_timesteps, n_dim_state]` Smoothed state 
    """Apply the Kalman Smoother"""
    x = pred_state.mean # sample for getting tensor properties
    bs, n_timesteps, n_dim_state = x.shape[0], x.shape[1], x.shape[2]

    smoothed_state = ListMNormal(torch.zeros((bs, n_timesteps,n_dim_state,1),             dtype=x.dtype, device=x.device), 
                                 torch.zeros((bs, n_timesteps, n_dim_state,n_dim_state), dtype=x.dtype, device=x.device))
    # For the last timestep cannot use the smoother
    smoothed_state.mean[:,-1,] = filt_state.mean[:,-1]
    smoothed_state.cov[:,-1] = filt_state.cov[:,-1]

    for t in reversed(range(n_timesteps - 1)):
        (smoothed_state.mean[:,t], smoothed_state.cov[:,t]) = (
            _smooth_update(
                trans_matrix,
                filt_state[:,t],
                pred_state[:,t + 1],
                smoothed_state[:,t+1],
            )
        )
    return smoothed_state

# %% ../../lib_nbs/kalman/00_filter.ipynb 73
@patch
def smooth(self: KalmanFilter,
           obs: Tensor,
           mask: Tensor = None,
          ) -> ListMNormal: # `[n_timesteps, n_dim_state]` smoothed state
        
    """Kalman Filter Smoothing"""

    (pred_state_means, pred_state_covs, filt_state_means, filt_state_covs) = self._filter_all(obs, mask)

    smoothed_state = _smooth(self.trans_matrix,
                   ListMNormal(filt_state_means, filt_state_covs), ListMNormal(pred_state_means, pred_state_covs),
                   self.cov_checker)
    smoothed_state.mean.squeeze_(-1)
    return smoothed_state

# %% ../../lib_nbs/kalman/00_filter.ipynb 84
@patch
def _obs_from_state(self: KalmanFilter, state: ListMNormal):

    mean = self.obs_matrix @ state.mean.unsqueeze(-1) + self.obs_off.unsqueeze(-1)
    cov = self.obs_matrix @ state.cov @ self.obs_matrix.mT + self.obs_cov
    
    self.cov_checker.check(cov, caller='predict')
    
    return ListMNormal(mean.squeeze(-1), cov)

# %% ../../lib_nbs/kalman/00_filter.ipynb 89
@patch
def predict(self: KalmanFilter, obs, mask=None, smooth=True):
    """Predicted observations at all times """
    state = self.smooth(obs, mask) if smooth else self.filter(obs, mask)
    obs, mask = self._parse_obs(obs, mask)
    
    pred_obs = self._obs_from_state(state)
    # conditional predictions are slow, do only if some obs are missing 
    cond_mask = torch.logical_xor(mask.all(-1), mask.any(-1))
    
    # this cannot be batched so returns a list
    cond_preds = cond_gaussian_batched(
        pred_obs[cond_mask], obs[cond_mask], mask[cond_mask])
    
    pred_mean, pred_std = pred_obs.mean, cov2std(pred_obs.cov) # multiple [] still not properly implemented in ListMNormal
    
    for i, c_pred in enumerate(cond_preds):
        m = ~mask[cond_mask][i]
        pred_mean[cond_mask][i][m] = c_pred.mean
        pred_std [cond_mask][i][m] = cov2std(c_pred.cov)
    
    return ListNormal(pred_mean, pred_std)

# %% ../../lib_nbs/kalman/00_filter.ipynb 116
@patch
def get_info(self: KalmanFilter, var_names=None):
    out = {}
    var_names = ifnone(var_names, [f"x_{i}" for i in range(self.obs_matrix.shape[0])])
    latent_names = [f"z_{i}" for i in range(self.trans_matrix.shape[0])]
    out['trans_matrix (A)'] = array2df(self.trans_matrix,    latent_names, latent_names, 'latent')
    out['trans_cov (Q)']     = array2df(self.trans_cov,       latent_names, latent_names, 'latent')
    out['trans_off']        = array2df(self.trans_off,       latent_names, ['offset'],     'latent')
    out['obs_matrix (H)']    = array2df(self.obs_matrix,      var_names,    latent_names, 'variable')
    out['obs_cov (R)']       = array2df(self.obs_cov,         var_names,    var_names,    'variable')
    out['obs_off']          = array2df(self.obs_off,         var_names,    ['offset'],     'variable')
    out['init_state_mean']  = array2df(self.init_state_mean, latent_names, ['mean'],       'latent')
    out['init_state_cov']   = array2df(self.init_state_cov,  latent_names, latent_names, 'latent')
    
    return out

# %% ../../lib_nbs/kalman/00_filter.ipynb 120
@patch(cls_method=True)
def init_simple(cls: KalmanFilter,
                n_dim, # n_dim_obs and n_dim_state
                dtype=torch.float32):
    """Simplest version of kalman filter parameters"""
    return cls(
        trans_matrix =     torch.eye(n_dim, dtype=dtype),
        trans_off =        torch.zeros(n_dim, dtype=dtype),        
        trans_cov =        torch.eye(n_dim, dtype=dtype),        
        obs_matrix =       torch.eye(n_dim, dtype=dtype),
        obs_off =          torch.zeros(n_dim, dtype=dtype),          
        obs_cov =          torch.eye(n_dim, dtype=dtype),            
        init_state_mean =  torch.zeros(n_dim, dtype=dtype),        
        init_state_cov =   torch.eye(n_dim, dtype=dtype),
    )

# %% ../../lib_nbs/kalman/00_filter.ipynb 123
@patch(cls_method=True)
def init_local_slope(cls: KalmanFilter,
                n_dim, # n_dim_obs and n_dim_state
                dtype=torch.float32):
    """Simplest version of kalman filter parameters"""
    return cls(
        trans_matrix =     torch.eye(n_dim, dtype=dtype),
        trans_off =        torch.zeros(n_dim, dtype=dtype),        
        trans_cov =        torch.eye(n_dim, dtype=dtype),        
        obs_matrix =       torch.eye(n_dim, dtype=dtype),
        obs_off =          torch.zeros(n_dim, dtype=dtype),          
        obs_cov =          torch.eye(n_dim, dtype=dtype),            
        init_state_mean =  torch.zeros(n_dim, dtype=dtype),        
        init_state_cov =   torch.eye(n_dim, dtype=dtype),
    )
