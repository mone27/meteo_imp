# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/kalman/00_Kalman_Filter.ipynb.

# %% auto 0
__all__ = ['to_posdef', 'posdef_log', 'is_pos_semidef', 'check_is_pos_semidef', 'PosDef', 'is_symmetric', 'symmetric_upto',
           'is_posdef', 'is_posdef2', 'make_symmetric', 'check_posdef', 'check_posdef4', 'KalmanFilter',
           'KalmanFilterTester']

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 3
from fastcore.test import *
from fastcore.basics import patch
from ..utils import *
from ..gaussian import *
from ..data_preparation import MeteoDataTest
import pykalman
from typing import *

import numpy as np
import pandas as pd
import torch
from torch import Tensor
from torch.distributions import MultivariateNormal

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 6
def array1d(X):
    """Returns at least 1-d array with data from X"""
    return torch.atleast_1d(torch.as_tensor(X))

def array2d(X):
    """Returns at least 2-d array with data from X"""
    return torch.atleast_2d(torch.as_tensor(X))


# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 7
def _determine_dimensionality(variables, default):
    """Derive the dimensionality of the state space

    Parameters
    ----------
    variables : list of ({None, array}, conversion function, index)
        variables, functions to convert them to arrays, and indices in those
        arrays to derive dimensionality from.
        
    Returns
    -------
    dim : int
        dimensionality of state space as derived from variables or default.
    """
    # gather possible values based on the variables
    candidates = []
    for (v, converter, idx) in variables:
        if v is not None:
            v = converter(v)
            candidates.append(v.shape[idx])
    
     # also use the manually specified default
    if default is not None:
        candidates.append(default)
    
    # ensure consistency of all derived values
    if len(candidates) == 0:
        return 1
    else:
        if not torch.all(torch.tensor(candidates) == candidates[0]):
            raise ValueError(
                "The shape of all " +
                "parameters is not consistent.  " +
                "Please re-check their values."
            )
        return candidates[0]


def _last_dims(X: Tensor, t: int, ndims: int=2):
    """Extract the final dimensions of `X`

    Extract the final `ndim` dimensions at index `t` if `X` has >= `ndim` + 1
    dimensions, otherwise return `X`.

    Parameters
    ----------
    X : Tensor with at least dimension `ndims`
    t : int
        index to use for the `ndims` + 1th dimension
    ndims : int, optional
        number of dimensions in the array desired

    Returns
    -------
    Y : array with dimension `ndims`
        the final `ndims` dimensions indexed by `t`
    """
    if len(X.shape) == ndims + 1:
        return X[t]
    elif len(X.shape) == ndims:
        return X
    else:
        raise ValueError(("X only has %d dimensions when %d" +
                " or more are required") % (len(X.shape), ndims))

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 8
def _stack_detach(l: Collection[Tensor]):
    return torch.stack(list(map(lambda x: x.detach(), l)))

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 11
def is_pos_semidef(cov):
    return torch.distributions.constraints.positive_semidefinite.check(cov).item()

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 12
def check_is_pos_semidef(cov):
    if not is_pos_semidef(cov):
        raise ValueError(f"Not positive semi definite {cov}")

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 13
class PosDef():
    """ Positive Definite Constraint for PyTorch parameters"""
    def __init__(self, a=1e-5):
        self.a = a
    def transform(self,
                  raw # square matrix that will be 
                 ):
        C = torch.tril(raw)
        return C @ C.mT
    def transform_old(self,
                  raw # square matrix that will be 
                 ):
        "transform any square matrix into a positive definite one"
        semi_pos = raw @ raw.T
        check_is_pos_semidef(semi_pos)
        return semi_pos + (self.a * torch.eye(raw.shape[0]))
    
    def inverse_transform(self,
                          value # a positive definite matrix
                         ):
        "tranform positive definite matrix into a raw matrix"
        return torch.linalg.cholesky(value)

to_posdef = PosDef().transform

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 24
def is_symmetric(value, atol=1e-5):
    return torch.isclose(value, value.mT, atol=atol).all().item()

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 26
def symmetric_upto(value, start=-8):
    for exp in torch.arange(start, 3):
        if is_symmetric(value, atol=10**exp):
            return exp
    return exp

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 29
def is_posdef(cov):
    return torch.distributions.constraints.positive_definite.check(cov).item()

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 37
def is_posdef2(cov):
    eigv = torch.linalg.eigvalsh(cov)
    if (eigv < 0).any():
        return False, eigv
    return True, eigv

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 40
from warnings import warn

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 44
def make_symmetric(value):
    "drops upper half to make matrix symmetric"
    value = value.clone()
    mask = torch.tril(torch.ones_like(value, dtype=torch.bool))
    value[mask.T] = torch.tril(value)[mask]
    return value

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 47
import pandas as pd

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 50
def check_posdef(value, name = '', error=True, **extra_args):
    value = value.clone()
    sym_upto = symmetric_upto(value).numpy()
    
    is_pd_eigv, eigv = is_posdef2(value)
    is_pd_chol = torch.linalg.cholesky_ex(value).info.eq(0).all().item()
    is_sym = is_symmetric(value)
  
    # sym = make_symmetric(value)
    # is_pd_forced, _ = is_posdef2(sym)
    
    
    
    info = pd.DataFrame({
        'is_pd_eigv': is_pd_eigv,
        'is_pd_chol': is_pd_chol,
        'is_sym': is_sym,
        'sym_upto': sym_upto,
        # 'force_sym_posdef': is_pd_forced,
        'eigv': [eigv.detach().numpy()],
        'matrix': [value.detach().numpy()],
        'name': name,
        **extra_args
    })
    
    global posdef_log
    if posdef_log is not None:
        posdef_log = pd.concat([posdef_log, info])
    
    if not is_pd_eigv or not is_pd_chol:
        if error:
            warn("Matrix is not positive definite")
    return info

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 57
posdef_log = None # by default disable logging for exported module 

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 58
def check_posdef4(value, error=True):
    msg = ""
    is_pd_eigv, eigv = is_posdef2(value)
    is_pd_chol = is_posdef(value)
    if not is_pd_eigv or not is_pd_chol:
        is_sym = is_symmetric(value)
        if not is_sym:
            msg += f"Not symmetric, symmetric up to 1e{symmetric_upto(value)}\n"
            msg += f"Not pos definite with eigv {eigv} \n"
        # try to make it symmetric and try again to see if it's posdef
            sym = make_symmetric(value)
            is_pd, eigv = is_posdef2(sym)
            add_msg = "forced symmetric is posdef" if is_pd else "force symmetric is not posdef"
            msg += add_msg
        
    if msg != "":
        msg += str(value)
        warn(msg)

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 64
class KalmanFilter(torch.nn.Module):
    """Kalman Filter and Smoother using PyTorch"""
    def __init__(self,
            transition_matrices: Tensor=None, # [n_timesteps-1, n_dim_state, n_dim_state] or [n_dim_state,n_dim_state] 
               # Also known as $A$ 
               # state transition matrix between times t and t+1 for t in [0...n_timesteps-2]
            obs_matrices: Tensor=None, # [n_timesteps, n_dim_obs, n_dim_state] or [n_dim_obs, n_dim_state]
                # Also known as $H$
                # obs matrix for times [0...n_timesteps-1]
            transition_cov: Tensor=None, # [n_dim_state, n_dim_state] 
                 # Also known as $Q$
                 # state transition cov matrix for times [0...n_timesteps-2]
            obs_cov: Tensor=None, # [n_dim_obs, n_dim_obs]
                 # Also known as $R$
                 # obs cov matrix for times [0...n_timesteps-1]
            transition_offsets: Tensor=None, # [n_timesteps-1, n_dim_state] or [n_dim_state]
                 # Also known as $b$
                 # state offsets for times [0...n_timesteps-2]
            obs_offsets: Tensor=None, # [n_timesteps, n_dim_obs] or [n_dim_obs]
                 # Also known as $d$
            initial_state_mean: Tensor=None, # [n_dim_state]
                 # Also known as $\mu_0"$
            initial_state_cov: Tensor=None, # [n_dim_state, n_dim_state]
                 # Also known as $\Sigma_0$
            n_dim_state: int = None, # Number of dimensions for state - defaults to 1 if cannot be infered from parameters
            n_dim_obs: int = None # Number of dimensions for observations - defaults to 1 if cannot be infered from parameters
                ):
        """Initialize Kalman Filter"""
        
        super().__init__()
        
        # determine size of state space and check parameters are consistent
        n_dim_state = _determine_dimensionality(
            [(transition_matrices, array2d, -2),
             (transition_offsets, array1d, -1),
             (transition_cov, array2d, -2),
             (initial_state_mean, array1d, -1),
             (initial_state_cov, array2d, -2),
             (obs_matrices, array2d, -1)],
            n_dim_state
        )
        n_dim_obs = _determine_dimensionality(
            [(obs_matrices, array2d, -2),
             (obs_offsets, array1d, -1),
             (obs_cov, array2d, -2)],
            n_dim_obs
        )
        
        self.n_dim_obs = n_dim_obs
        self.n_dim_state = n_dim_state
        
        params = {
        # name                 value         default_value                              converter constraint train
        'transition_matrices': [transition_matrices, torch.eye(n_dim_state),            array2d, None    , True],
        'transition_offsets':  [transition_offsets,  torch.zeros(n_dim_state),          array1d, None    , True],
        'transition_cov':      [transition_cov,      torch.eye(n_dim_state),            array2d, PosDef(), True],
        'obs_matrices':        [obs_matrices,        torch.eye(n_dim_obs, n_dim_state), array2d, None    , True],
        'obs_offsets':         [obs_offsets,         torch.zeros(n_dim_obs),            array1d, None    , True],
        'obs_cov':             [obs_cov,             torch.eye(n_dim_obs),              array2d, PosDef(), True],
        'initial_state_mean':  [initial_state_mean,  torch.zeros(n_dim_state),          array1d, None    , True],
        'initial_state_cov':   [initial_state_cov,   torch.eye(n_dim_state),            array2d, PosDef(), True],
        }
        
        self._init_params(params)
        
        self.check_args = None
        
    def _init_params(self, params):
        for name, (value, default, converter, constraint, train) in params.items():
            value = value if value is not None else default
            value = converter(value) 
            if constraint is not None:
                name, value = self._init_constraint(name, value, constraint)
            self._init_param(name, value, train)    
    
    def _init_param(self, param_name, value, train):
        self.register_parameter(param_name, torch.nn.Parameter(value, requires_grad=train))
    
    ## Constraints ----
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
        

    
    ### convenience functions to get and set parameters that have a constraint
    
    @property
    def transition_cov(self):
        return self._get_constraint('transition_cov')
    
    @transition_cov.setter
    def transition_cov(self, value):
        return self._set_constraint('transition_cov', value)
    
    @property
    def obs_cov(self):
        return self._get_constraint('obs_cov')
    
    @obs_cov.setter
    def obs_cov(self, value):
        return self._set_constraint('obs_cov', value)
    
    @property
    def initial_state_cov(self):
        return self._get_constraint('initial_state_cov')
    
    @initial_state_cov.setter
    def initial_state_cov(self, value):
        return self._set_constraint('initial_state_cov', value)
    
    
    ### -----
    
    def _parse_obs(self, obs, mask=None):
        """Safely convert observations to their expected format"""
        obs = torch.atleast_2d(obs)
        if obs.shape[0] == 1 and obs.shape[1] > 1:
            obs = obs.T
        if mask is None: mask = ~torch.isnan(obs)
        return obs, torch.atleast_2d(mask)
    
    def __repr__(self):
        return f"""Kalman Filter
        N dim obs: {self.n_dim_obs}, N dim state: {self.n_dim_state}"""

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 87
from fastcore.basics import *

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 88
to_posdef = PosDef().transform

class KalmanFilterTester():
    
    torch2pyk = {
        'transition_matrices': 'transition_matrices',
        'transition_offsets':  'transition_offsets',        
        'transition_cov':      'transition_covariance',        
        'obs_matrices':        'observation_matrices',
        'obs_offsets':         'observation_offsets',          
        'obs_cov':             'observation_covariance',            
        'initial_state_mean':  'initial_state_mean',        
        'initial_state_cov':   'initial_state_covariance',
    }
    
    def __init__(self,
                 n_dim_state = 3,
                n_dim_obs = 3,
                n_obs = 10,
                p_missing = .3,
                seed=None,
                dtype=torch.float32,
                nan_mask = True
                ):
        store_attr(but='seed')
        if seed: reset_seed(seed)
        
        self.random_init()
    
    def random_init(self):
        self.params = {
            'transition_matrices': torch.rand(self.n_dim_state, self.n_dim_state, dtype=self.dtype),
            'transition_offsets':  torch.rand(self.n_dim_state, dtype=self.dtype),        
            'transition_cov':      to_posdef(torch.rand(self.n_dim_state, self.n_dim_state, dtype=self.dtype)),        
            'obs_matrices':        torch.rand(self.n_dim_obs, self.n_dim_state, dtype=self.dtype),
            'obs_offsets':         torch.rand(self.n_dim_obs, dtype=self.dtype),          
            'obs_cov':             to_posdef(torch.rand(self.n_dim_obs, self.n_dim_obs, dtype=self.dtype)),            
            'initial_state_mean':  torch.rand(self.n_dim_state, dtype=self.dtype),        
            'initial_state_cov':   to_posdef(torch.rand(self.n_dim_state, self.n_dim_state, dtype=self.dtype)),
        }
        self.params_pyk = {self.torch2pyk[name]: param.numpy() for name, param in self.params.items()}
        
        self.filter = KalmanFilter(**self.params)
        self.filter_pyk = pykalman.standard.KalmanFilter(**self.params_pyk)
        
        
        self.data = torch.rand(self.n_obs, self.n_dim_obs, dtype=self.dtype)
        self.mask = torch.rand(self.n_obs, self.n_dim_obs) > self.p_missing
        if self.nan_mask: self.data[~self.mask] = torch.nan # ensure that the data cannot be used
        self.data_pyk = np.ma.masked_array(self.data.numpy(), mask = ~self.mask.numpy()) 
    
    

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 94
from datetime import datetime
def _filter_predict(transition_matrix, transition_cov,
                    transition_offset, current_state_mean,
                    current_state_cov, check_args=None):
    r"""Calculate the mean and cov of $P(x_{t+1} | z_{0:t})$"""
    pred_state_mean = transition_matrix @ current_state_mean + transition_offset
    pred_state_cov =  transition_matrix @ current_state_cov @ transition_matrix.T + transition_cov

    if check_args is not None: check_posdef(pred_state_cov, 'filter_predict', **check_args)
    
    return (pred_state_mean, pred_state_cov)

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 146
def _filter_correct(obs_matrix,
                    obs_cov,
                    obs_offset,
                    pred_state_mean,
                    pred_state_cov,
                    obs,
                    mask,
                    check_args=None):
    if mask.all():
        pred_obs_mean = obs_matrix @ pred_state_mean + obs_offset
        pred_obs_cov = obs_matrix @ pred_state_cov @ obs_matrix.T + obs_cov
        
        kalman_gain = pred_state_cov @ obs_matrix.T @ torch.cholesky_inverse(torch.linalg.cholesky(pred_obs_cov))

        corrected_state_mean = pred_state_mean + kalman_gain @ (obs - pred_obs_mean)
        corrected_state_cov = pred_state_cov - kalman_gain @ obs_matrix @ pred_state_cov
    else:
        n_dim_state = pred_state_cov.shape[0]
        n_dim_obs = obs_matrix.shape[0]
        kalman_gain = torch.zeros((n_dim_state, n_dim_obs))

        corrected_state_mean = pred_state_mean
        corrected_state_cov = pred_state_cov
        
    if check_args is not None: check_posdef(pred_state_cov, 'filter_correct', **check_args)
    return (kalman_gain, corrected_state_mean,
            corrected_state_cov)

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 166
def _filter(transition_matrices, obs_matrices, transition_cov,
            obs_cov, transition_offsets, obs_offsets,
            initial_state_mean, initial_state_cov, obs, obs_mask, check_args={}):
    """Apply the Kalman Filter

    Calculate posterior distribution over hidden states given obss up
    to and including the current time step.

    Parameters
    ----------
    transition_matrices : [n_timesteps-1,n_dim_state,n_dim_state] or
    [n_dim_state,n_dim_state] array-like
        state transition matrices
    obs_matrices : [n_timesteps, n_dim_obs, n_dim_state] or [n_dim_obs, \
    n_dim_state] array-like
        obs matrix
    transition_cov : [n_timesteps-1,n_dim_state,n_dim_state] or
    [n_dim_state,n_dim_state] array-like
        state transition cov matrix
    obs_cov : [n_timesteps, n_dim_obs, n_dim_obs] or [n_dim_obs,
    n_dim_obs] array-like
        obs cov matrix
    transition_offsets : [n_timesteps-1, n_dim_state] or [n_dim_state] \
    array-like
        state offset
    obs_offsets : [n_timesteps, n_dim_obs] or [n_dim_obs] array-like
        obss for times [0...n_timesteps-1]
    initial_state_mean : [n_dim_state] array-like
        mean of initial state distribution
    initial_state_cov : [n_dim_state, n_dim_state] array-like
        cov of initial state distribution
    obss : [n_timesteps, n_dim_obs] array
        obss from times [0...n_timesteps-1].  If `obss` is a
        masked array and any of `obss[t]` is masked, then
        `obss[t]` will be treated as a missing obs.

    Returns
    -------
    pred_state_means : [n_timesteps, n_dim_state] array
        `pred_state_means[t]` = mean of hidden state at time t given
        obss from times [0...t-1]
    pred_state_covs : [n_timesteps, n_dim_state, n_dim_state] array
        `pred_state_covs[t]` = cov of hidden state at time t
        given obss from times [0...t-1]
    kalman_gains : [n_timesteps, n_dim_state] array
        `kalman_gains[t]` = Kalman gain matrix for time t
    filt_state_means : [n_timesteps, n_dim_state] array
        `filt_state_means[t]` = mean of hidden state at time t given
        obss from times [0...t]
    filt_state_covs : [n_timesteps, n_dim_state] array
        `filt_state_covs[t]` = cov of hidden state at time t
        given obss from times [0...t]
    """
    n_timesteps = obs.shape[0]
    n_dim_state = len(initial_state_mean)
    n_dim_obs = obs.shape[1]
    
    # those variables need to be lists and not Tensors,
    # otherwise pytorch tryies to compute the gradient for the whole tensor and it breaks due to the in place operations
    
    pred_state_means = [None for _ in range(n_timesteps)] # torch.zeros((n_timesteps, n_dim_state))
    pred_state_covs = [None for _ in range(n_timesteps)] # torch.zeros(
        #(n_timesteps, n_dim_state, n_dim_state)
    #)
    kalman_gains = [None for _ in range(n_timesteps)]
    filt_state_means = [None for _ in range(n_timesteps)]
    filt_state_covs = [None for _ in range(n_timesteps)]

    for t in range(n_timesteps):
        if t == 0:
            pred_state_means[t] = initial_state_mean
            pred_state_covs[t] = initial_state_cov
        else:
            transition_matrix = _last_dims(transition_matrices, t - 1)
            transition_cov = _last_dims(transition_cov, t - 1)
            transition_offset = _last_dims(transition_offsets, t - 1, ndims=1)
            pred_state_means[t], pred_state_covs[t] = (
                _filter_predict(
                    transition_matrix,
                    transition_cov,
                    transition_offset,
                    filt_state_means[t - 1],
                    filt_state_covs[t - 1],
                    check_args = {'t': t, **check_args} if check_args is not None else None
                )
            )

        obs_matrix = _last_dims(obs_matrices, t)
        obs_cov = _last_dims(obs_cov, t)
        obs_offset = _last_dims(obs_offsets, t, ndims=1)
        (kalman_gains[t], filt_state_means[t],
         filt_state_covs[t]) = (
            _filter_correct(obs_matrix,
                obs_cov,
                obs_offset,
                pred_state_means[t],
                pred_state_covs[t],
                obs[t],
                obs_mask[t],
                check_args = {'t': t, **check_args} if check_args is not None else None
            )
        )

    return (pred_state_means, pred_state_covs, filt_state_means,
            filt_state_covs)

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 178
@patch
def _filter_all(self: KalmanFilter, obs, mask=None, check_args=None) -> Tuple:
    obs, obs_mask = self._parse_obs(obs, mask)

    return _filter(
            self.transition_matrices,
            self.obs_matrices,
            self.transition_cov,
            self.obs_cov,
            self.transition_offsets,
            self.obs_offsets,
            self.initial_state_mean,
            self.initial_state_cov,
            obs,
            obs_mask,
            check_args
        )

@patch
def filter(self: KalmanFilter,
          obs: Tensor, # [n_timesteps, n_dim_obs] obs for times [0...n_timesteps-1]
          mask = None,
          check_args=None
          ) -> ListMNormal: # Filtered state
    """Filter observation"""
    _, _, filt_state_means, filt_state_covs = self._filter_all(obs, mask, check_args)
    # need to convert a list of tensors with gradients to a big tensors without gradients
    return ListMNormal(_stack_detach(filt_state_means), _stack_detach(filt_state_covs))


# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 196
def _smooth_update(transition_matrix,      # [n_dim_state, n_dim_state]
                   filt_state: Normal, # [n_dim_state] filtered state at time `t`
                   pred_state: Normal,        # [n_dim_state] state before filtering at time `t + 1` (= using the observation until time t)
                   next_smoothed_state: Normal, # [n_dim_state] smoothed state at time  `t+1`
                   check_args: dict|None = None # if not None checks that the result is positive definite
                   ) -> Normal: # mean and cov of smoothed state at time `t`
    r"""Correct a pred state with a Kalman Smoother update

    Calculates posterior distribution of the hidden state at time `t` given the the observations via Kalman Smoothing.
    """
    kalman_smoothing_gain = filt_state.cov @ transition_matrix.T @ torch.cholesky_inverse(torch.linalg.cholesky(pred_state.cov))

    smoothed_state_mean = filt_state.mean + kalman_smoothing_gain @ (next_smoothed_state.mean - pred_state.mean)
    smoothed_state_cov = (filt_state.cov
                      + kalman_smoothing_gain @ (next_smoothed_state.cov - pred_state.cov) @ kalman_smoothing_gain.T)

    if check_args is not None: check_posdef(pred_state_cov, 'filter_correct', **check_args)
    
    return ListMNormal(smoothed_state_mean, smoothed_state_cov,)

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 201
def _smooth(transition_matrices, # `[n_timesteps-1, n_dim_state, n_dim_state]` or `[n_dim_state, n_dim_state]`
            filt_state: ListMNormal, # `[n_timesteps, n_dim_state]`
                # `filt_state_means[t]` = mean state estimate for time t given obs from times `[0...t]`
            pred_state: ListMNormal, # `[n_timesteps, n_dim_state]`
                # `pred_state_means[t]` = mean state estimate for time t given obs from times `[0...t-1]`
           check_args: dict|None = None # if not None checks that the result is positive definite
           ) -> ListMNormal: # `[n_timesteps, n_dim_state]` Smoothed state 
    """Apply the Kalman Smoother """
    n_timesteps, n_dim_state = len(pred_state.mean), pred_state.mean[0].shape[0]

    smoothed_state = ListMNormal(torch.zeros((n_timesteps,n_dim_state), dtype=pred_state.mean[0].dtype, device=pred_state.mean[0].device), 
                                torch.zeros((n_timesteps, n_dim_state,
                                           n_dim_state), dtype=pred_state.mean[0].dtype, device=pred_state.mean[0].device))

    smoothed_state.mean[-1] = filt_state.mean[-1]
    smoothed_state.cov[-1] = filt_state.cov[-1]

    for t in reversed(range(n_timesteps - 1)):
        transition_matrix = _last_dims(transition_matrices, t)
        (smoothed_state.mean[t], smoothed_state.cov[t]) = (
            _smooth_update(
                transition_matrix,
                filt_state.get_nth(t),
                pred_state.get_nth(t + 1),
                smoothed_state.get_nth(t+1),
                check_args = {'t': t, **check_args} if check_args is not None else None
            )
        )
    return smoothed_state

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 208
@patch
def smooth(self: KalmanFilter,
           obs: Tensor, # dataset
           mask = None,
           check_args=None
          ) -> ListMNormal: # `[n_timesteps, n_dim_state]` smoothed hidden state distributions for times `[0...n_timesteps-1]`
        
    """Kalman Filter Smoothing"""

    (pred_state_means, pred_state_covs, filt_state_means, filt_state_covs) = self._filter_all(obs, mask, check_args)

    return _smooth(
            self.transition_matrices,
            ListMNormal(filt_state_means, filt_state_covs),
            ListMNormal(pred_state_means, pred_state_covs),
            check_args
        )

  

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 219
def _get_cond_pred(pred: ListMNormal,
                  obs,
                  mask
                  ) -> ListNormal:
    """Conditional prediction given observations and transforms covariances into std deviations"""
    
    obs = obs[mask] # select only actually observed values
    pred_cond = conditional_guassian(pred.mean, pred.cov, obs, mask)
    
    mean = pred.mean.clone()
    mean[~mask] = pred_cond.mean
    
    std = torch.diagonal(pred.cov.clone(), dim1=-2, dim2=-1)
    std[~mask] = torch.diagonal(pred_cond.cov, dim1=-2, dim2=-1)
    
    return ListMNormal(mean, std)

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 228
@patch
def _obs_from_state(self: KalmanFilter, state_mean, state_cov, check_args=None):

    mean = self.obs_matrices @ state_mean
    cov = self.obs_matrices @ state_cov @ self.obs_matrices.mT + self.obs_cov
    
    if check_args is not None: check_posdef(cov, 'predict',  **check_args)
    
    return ListMNormal(mean, cov)

@patch
def predict(self: KalmanFilter, obs, mask=None, smooth=True, check_args=None):
    """Predicted observations at all times """
    state = self.smooth(obs, mask, check_args) if smooth else self.filter(obs, mask, check_args)
    obs, mask = self._parse_obs(obs, mask)
    
    means = torch.empty_like(obs)
    stds = torch.empty_like(obs)
                             
    for t in range(obs.shape[0]):
        mean, std = self._obs_from_state(
            state.mean[t],
            state.cov[t],
            {'t': t, **check_args} if check_args is not None else None
        )
        
        means[t], stds[t] = _get_cond_pred(ListNormal(mean, std), obs[t], mask[t])
    
    return ListNormal(means, stds)

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 242
@patch
def filter_loglikelihood(self: KalmanFilter, obs, mask=None):
    "Compute log likelihood using only filter step"
    # Those are the means and covs before the updating step,
    # otherwise the model would have already seen the observation that we are predicting 
    pred_state_mean, pred_state_cov, _, _ = self._filter_all(obs, mask)
    obs, obs_mask = self._parse_obs(obs, mask)

    max_t = obs.shape[0]
    lls = torch.zeros(max_t)
    for t in range(max_t):
        if obs_mask[t].all():
            pred_obs_mean, pred_obs_cov = self._obs_from_state(pred_state_mean[t], pred_state_cov[t])
            ll = MultivariateNormal(pred_obs_mean, pred_obs_cov, validate_args=False).log_prob(obs[t])
            lls[t] = ll

    return lls.sum()

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 254
@patch
def loglikelihood(self: KalmanFilter,
                  obs_train: Tensor, # [n_timesteps, n_dim_obs] Observations use for the filter (can containt missing data)
                  times: Tensor, # [n_pred_timesteps] time at which to calculate the log likelihood
                  obs_test: Tensor, # [n_pred_timesteps, n_dim_obs] observed data to compute log likelihood
                  mask: Tensor=None, # [n_timesteps, n_dim_obs]
                 ) -> Tensor: # scalar that is sum of log likelihoods for all `times`
    "Log likelihood only for the `obs_test` at giben times"
    means, stds = self.predict(obs_train, mask=mask)
    lls = torch.zeros(len(times))
    for t in range(len(times)):
        lls[t] = MultivariateNormal(means[t], torch.diag(stds[t]), validate_args=False).log_prob(obs_test[t:t+1])
    return lls.sum() 
        

# %% ../../lib_nbs/kalman/00_Kalman_Filter.ipynb 262
@patch
def get_info(self: KalmanFilter, var_names=None):
    out = {}
    if var_names is not None: self.var_names = var_names 
    latent_names = [f"z_{i}" for i in range(self.transition_matrices.shape[0])]
    out['A'] = array2df(self.transition_matrices, latent_names, latent_names, 'latent')
    out['H'] = array2df(self.obs_matrices,        var_names,    latent_names, 'variable')
    out['R'] = array2df(self.obs_cov,             var_names,    var_names,     'variable')
    out['Q'] = array2df(self.transition_cov,      latent_names, latent_names, 'latent')
    return out
