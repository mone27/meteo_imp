# AUTOGENERATED! DO NOT EDIT! File to edit: ../lib_nbs/99_utils.ipynb.

# %% auto 0
__all__ = ['cache_dir', 'cache_disk', 'reset_seed', 'test_close', 'array2df', 'maybe_retrieve_callers_name', 'retrieve_names',
           'pretty_repr', 'row_items', 'show_as_row', 'row_dfs', 'display_as_row', 'eye_like', 'is_diagonal',
           'product_dict']

# %% ../lib_nbs/99_utils.ipynb 3
# dill is an improved version of pickle, using it to support namedtuples
import dill
from pathlib import Path
import inspect
import hashlib
from pyprojroot import here

# %% ../lib_nbs/99_utils.ipynb 10
cache_dir = here(".cache")

# %% ../lib_nbs/99_utils.ipynb 11
# inspired from https://gist.github.com/shantanuo/c6a376309d6bac6bd55bf77e3961b5fb
def cache_disk(base_file, rm_cache=False, verbose=False):
    "Decorator to cache function output to disk"
    base_file = Path(base_file)
    def decorator(original_func):
        
        f_hash = hashlib.md5(original_func.__code__.co_code).hexdigest()
        filename = base_file.parent / (base_file.stem + f_hash + ".pickle")
        
        if verbose: print(filename)
        
        if rm_cache: filename.unlink()
        
        try:
            cache = dill.load(open(filename, 'rb'))
        except (IOError, ValueError, FileNotFoundError):
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

# %% ../lib_nbs/99_utils.ipynb 24
import torch
import numpy as np
import random

# %% ../lib_nbs/99_utils.ipynb 25
def reset_seed(seed=27):
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

# %% ../lib_nbs/99_utils.ipynb 27
from typing import Generator, Iterable
from functools import partial
from fastcore.test import test
from fastcore.basics import patch

# %% ../lib_nbs/99_utils.ipynb 28
def is_close(a,b,eps=1e-5):
    "Is `a` within `eps` of `b`"
    if hasattr(a, '__array__') or hasattr(b,'__array__'):
        a = torch.as_tensor(a)
        b = torch.as_tensor(b)
        return (abs(a-b)<eps).all()
    if isinstance(a, (Iterable,Generator)) or isinstance(b, (Iterable,Generator)):
        return all(is_close(a_, b_, eps) for a_,b_ in zip(a,b))
    return abs(a-b)<eps

# %% ../lib_nbs/99_utils.ipynb 29
def test_close(a,b,eps=1e-5):
    "`test` that `a` is within `eps` of `b`"
    test(a,b,partial(is_close,eps=eps),'close')

# %% ../lib_nbs/99_utils.ipynb 32
from collections import namedtuple
from fastcore.basics import patch
from sklearn.preprocessing import StandardScaler

# %% ../lib_nbs/99_utils.ipynb 38
@patch
def inverse_transform_std(self: StandardScaler, 
                         x_std # standard deviations
                        ):
    return x_std * self.scale_

# %% ../lib_nbs/99_utils.ipynb 40
from torch import Tensor
from typing import Collection
import pandas as pd

from IPython.display import HTML
from IPython.display import display
from typing import Iterable

from fastcore.basics import *

# %% ../lib_nbs/99_utils.ipynb 41
def array2df(x: Tensor, # 2d tensor
             row_names: Collection[str]|None=None, # names for the row
             col_names: Collection[str]|None=None, # names for the columns
             row_var: str = '' # name of the first column (the one with row names). This should describe the values of `row_name`
            ):
    df = pd.DataFrame(x.detach().cpu().numpy(), columns=col_names)
    if row_names is not None: df.insert(0, row_var, row_names)
    return df

# %% ../lib_nbs/99_utils.ipynb 46
import inspect

# %% ../lib_nbs/99_utils.ipynb 47
# inspired from https://stackoverflow.com/questions/18425225/ 
def maybe_retrieve_callers_name(args):
    """Tries to retrieve the argument name in the call frame, if there are multiple matches name is ''"""
    names = []
    for i, arg in enumerate(args):
        callers_local_vars = inspect.currentframe().f_back.f_back.f_locals.items()
        var_names = [var_name for var_name, var_val in callers_local_vars if var_val is arg and not var_name.startswith("_")]
        names.append(var_names[0] if len(var_names)==1 else f'#{i}')
    return names

def retrieve_names(*args):
    """Tries to retrieve the argument name in the call frame, if there are multiple matches name is ''"""
    names = []
    for arg in args:
        callers_local_vars = inspect.currentframe().f_back.f_locals.items()
        var_names = [var_name for var_name, var_val in callers_local_vars if var_val is arg]
        names.append(var_names)
    return names

# %% ../lib_nbs/99_utils.ipynb 50
from contextlib import redirect_stdout
import io
from pprint import pp

# %% ../lib_nbs/99_utils.ipynb 52
def pretty_repr(o):
    trap = io.StringIO()
    with redirect_stdout(trap):
        pp(o)
    return trap.getvalue()
def row_items(**kwargs):
    columns = [f"<div><p style='font-size: 1.2rem;'>{title}</p> <pre>{pretty_repr(o)}</pre> </div>" for title, o in kwargs.items()]
    out = f"<div style=\"display: flex; column-gap: 20px; flex-wrap: wrap;\" class='table table-striped table-sm'> {''.join(columns)}</div>"
    return out
def show_as_row(*os, names: Iterable[str]=None, **kwargs):
    """Shows a interable of tensors on a row"""
    if names is None: names = maybe_retrieve_callers_name(os)
    kwargs.update(dict(zip(names, os)))
    out = row_items(**kwargs)
    display(HTML(out))

# %% ../lib_nbs/99_utils.ipynb 63
def _style_df(df_style):
    """style dataframe for better printing """
    return df_style.format(precision = 4)

def row_dfs(dfs: dict[str, pd.DataFrame], title="", hide_idx = True, styler=_style_df):
    out = []
    for df_title, df in dfs.items():
        df_styled =  df.style.hide(axis="index") if hide_idx else df.style 
        df_html = styler(df_styled).to_html()
        out.append(f"<div> <p style='font-size: 1.3rem;'>{df_title}</p> {df_html} </div>")
    out = f"<div style=\"display: flex; column-gap: 20px; flex-wrap: wrap;\" class='table table-striped table-sm'> {''.join(out)}</div>"
    return f"<p style='font-size: 1.5rem; font-decoration: bold'>{title}<p>" + "".join(out)
def display_as_row(dfs: dict[str, pd.DataFrame], title="", hide_idx=True, styler=_style_df):
    """display multiple dataframes in the same row"""
    display(HTML(row_dfs(dfs, title, hide_idx, styler)))

# %% ../lib_nbs/99_utils.ipynb 71
def eye_like(x: torch.Tensor) -> torch.Tensor:
    """
    Return a tensor with same batch size as x, that has a nxn eye matrix in each sample in batch.

    Args:
        x: tensor of shape (B, n, m) or (n,m)

    Returns:
        tensor of shape (B, n, m) or (n,m) that has the same dtype and device as x.
    """
    eye = torch.eye(x.shape[-2], x.shape[-1], dtype=x.dtype, device=x.device)
    if x.dim() > 2:
        for i in range(x.dim()-2):
            eye.unsqueeze_(0) # add as many dim in front
        size_repeat = [x.shape[i] for i in range(x.dim()-2)] + [-1,-1]
        eye = eye.expand(*size_repeat)
    return eye

# %% ../lib_nbs/99_utils.ipynb 79
def is_diagonal(x: torch.Tensor):
    """ Check that tensor is diagonal respect to the last 2 dimensions"""
    d = torch.diagonal(x, dim1=-2, dim2=-1)
    return (x == torch.diag_embed(d, dim1=-2, dim2=-1)).all()

# %% ../lib_nbs/99_utils.ipynb 84
import itertools

# %% ../lib_nbs/99_utils.ipynb 85
# from https://stackoverflow.com/a/5228294
def product_dict(**kwargs):
    keys = kwargs.keys()
    vals = kwargs.values()
    for instance in itertools.product(*vals):
        yield dict(zip(keys, instance))
