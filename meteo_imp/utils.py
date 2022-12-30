# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/99_utils.ipynb.

# %% auto 0
__all__ = ['cache_dir', 'cache_disk', 'reset_seed', 'test_close', 'array2df', 'maybe_retrieve_callers_name', 'retrieve_names',
           'show_as_row', 'row_dfs', 'display_as_row', 'array1d', 'array2d', 'determine_dimensionality', 'last_dims']

# %% ../lib_nbs/99_utils.ipynb 3
# dill is an improved version of pickle, using it to support namedtuples
import dill
from pathlib import Path
import inspect
import hashlib
from pyprojroot import here

# %% ../lib_nbs/99_utils.ipynb 5
cache_dir = here(".cache")

# %% ../lib_nbs/99_utils.ipynb 6
# inspired from https://gist.github.com/shantanuo/c6a376309d6bac6bd55bf77e3961b5fb
def cache_disk(base_file, rm_cache=False):
    "Decorator to cache function output to disk"
    base_file = Path(base_file)
    def decorator(original_func):
        
        f_hash = hashlib.md5(inspect.getsource(original_func).encode()).hexdigest()
        filename = base_file.parent / (base_file.stem + f_hash + ".pickle")
        
        if rm_cache: filename.unlink()
        
        try:
            cache = dill.load(open(filename, 'rb'))
        except (IOError, ValueError):
            cache = {}

        def save_data():
            dill.dump(cache, open(filename, "wb"))  

        def new_func(*args):
            if tuple(args) not in cache:
                cache[tuple(args)] = original_func(*args)
                save_data()
            return cache[args]

        return new_func

    return decorator

# %% ../lib_nbs/99_utils.ipynb 18
import torch
import numpy as np

# %% ../lib_nbs/99_utils.ipynb 19
def reset_seed(seed=27):
    torch.manual_seed(seed)
    np.random.seed(seed)

# %% ../lib_nbs/99_utils.ipynb 20
def reset_seed(seed=27):
    torch.manual_seed(seed)
    np.random.seed(seed)

# %% ../lib_nbs/99_utils.ipynb 22
from typing import Generator, Iterable
from functools import partial
from fastcore.test import test
from fastcore.basics import patch

# %% ../lib_nbs/99_utils.ipynb 23
def is_close(a,b,eps=1e-5):
    "Is `a` within `eps` of `b`"
    if hasattr(a, '__array__') or hasattr(b,'__array__'):
        a = torch.as_tensor(a)
        b = torch.as_tensor(b)
        return (abs(a-b)<eps).all()
    if isinstance(a, (Iterable,Generator)) or isinstance(b, (Iterable,Generator)):
        return all(is_close(a_, b_, eps) for a_,b_ in zip(a,b))
    return abs(a-b)<eps

# %% ../lib_nbs/99_utils.ipynb 24
def test_close(a,b,eps=1e-5):
    "`test` that `a` is within `eps` of `b`"
    test(a,b,partial(is_close,eps=eps),'close')

# %% ../lib_nbs/99_utils.ipynb 27
from collections import namedtuple
from fastcore.basics import patch
from sklearn.preprocessing import StandardScaler

# %% ../lib_nbs/99_utils.ipynb 33
@patch
def inverse_transform_std(self: StandardScaler, 
                         x_std # standard deviations
                        ):
    return x_std * self.scale_

# %% ../lib_nbs/99_utils.ipynb 35
from torch import Tensor
from typing import Collection
import pandas as pd

from IPython.display import HTML
from IPython.display import display
from typing import Iterable

from fastcore.basics import *

# %% ../lib_nbs/99_utils.ipynb 36
def array2df(x: Tensor, # 2d tensor
             row_names: Collection[str]|None=None, # names for the row
             col_names: Collection[str]|None=None, # names for the columns
             row_var: str = '' # name of the first column (the one with row names). This should describe the values of `row_name`
            ):
    df = pd.DataFrame(x.detach().cpu().numpy(), columns=col_names)
    if row_names is not None: df.insert(0, row_var, row_names)
    return df

# %% ../lib_nbs/99_utils.ipynb 41
import inspect

# %% ../lib_nbs/99_utils.ipynb 42
# inspired from https://stackoverflow.com/questions/18425225/ 
def maybe_retrieve_callers_name(args):
    """Tries to retrieve the argument name in the call frame, if there are multiple matches name is ''"""
    names = []
    for arg in args:
        callers_local_vars = inspect.currentframe().f_back.f_back.f_locals.items()
        var_names = [var_name for var_name, var_val in callers_local_vars if var_val is arg and not var_name.startswith("_")]
        names.append(var_names[0] if len(var_names)==1 else '')
    return names

def retrieve_names(*args):
    """Tries to retrieve the argument name in the call frame, if there are multiple matches name is ''"""
    names = []
    for arg in args:
        callers_local_vars = inspect.currentframe().f_back.f_locals.items()
        var_names = [var_name for var_name, var_val in callers_local_vars if var_val is arg]
        names.append(var_names)
    return names

# %% ../lib_nbs/99_utils.ipynb 45
def show_as_row(*os: Iterable, names: Iterable[str]=None, **kwargs):
    """Shows a interable of tensors on a row"""
    if names is None: names = maybe_retrieve_callers_name(os)
    kwargs.update(dict(zip(names, os)))
    columns = [f"<div><p style='font-size: 1.2rem;'>{title}</p> <pre>{repr(o)}</pre> </div>" for title, o in kwargs.items()]
    out = f"<div style=\"display: flex; column-gap: 20px; flex-wrap: wrap;\" class='table table-striped table-sm'> {''.join(columns)}</div>"
    display(HTML(out))

# %% ../lib_nbs/99_utils.ipynb 50
def _style_df(df):
    """style dataframe for better printing """
    return df.style.hide(axis="index").format(precision = 4)

def row_dfs(dfs: dict[str, pd.DataFrame], title="", styler=_style_df):
    out = []
    for df_title, df in dfs.items():
        df_html = _style_df(df).to_html()
        out.append(f"<div> <p style='font-size: 1.3rem;'>{df_title}</p> {df_html} </div>")
    out = f"<div style=\"display: flex; column-gap: 20px; flex-wrap: wrap;\" class='table table-striped table-sm'> {''.join(out)}</div>"
    return f"<p style='font-size: 1.5rem; font-decoration: bold'>{title}<p>" + "".join(out)
def display_as_row(dfs: dict[str, pd.DataFrame], title="", styler=_style_df):
    """display multiple dataframes in the same row"""
    display(HTML(row_dfs(dfs, title, styler)))

# %% ../lib_nbs/99_utils.ipynb 55
def array1d(X):
    """Returns at least 1-d array with data from X"""
    return torch.atleast_1d(torch.as_tensor(X))

def array2d(X):
    """Returns at least 2-d array with data from X"""
    return torch.atleast_2d(torch.as_tensor(X))


# %% ../lib_nbs/99_utils.ipynb 56
def determine_dimensionality(variables, default):
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


def last_dims(X: Tensor, t: int, ndims: int=2):
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
