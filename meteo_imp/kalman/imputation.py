# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/kalman/21_imputation.ipynb.

# %% auto 0
__all__ = ['KalmanImputation']

# %% ../../lib_nbs/kalman/21_imputation.ipynb 3
import pandas as pd
import numpy as np
from .model import KalmanModel
from ..results import ImputationResult
from ..utils import *
from fastcore.basics import store_attr, patch
from ..data_preparation import StandardScaler

import torch
from torch import Tensor

# %% ../../lib_nbs/kalman/21_imputation.ipynb 5
class KalmanImputation:
    """Imputation using a kalman model"""
    def __init__(self, data: pd.DataFrame,
                 model: KalmanModel = KalmanModel, # a subclass of KalmanModel to be used as model
                 **kwargs # for model
                ):
        self.data = data
        self.mask = ~torch.tensor(self.data.isna())
        self.train_idx = self.any(axis=1)
        
        train_data = torch.tensor(data.to_numpy())
        self.scaler = StandardScaler(train_data)
        train_data = self.scaler.transform(train_data)
        self.train_data = train_data
        
        self.T = torch.arange(self.data.shape[0])
        self.model = model(self.train_data, **kwargs)
    def fit(self, n_iter=10, lr=.1) -> 'KalmanImputation':
        """Fit model parameters"""
        times = self.T[self.train_idx]
        obs_test = self.train_data[self.train_idx]
        self.model.train(times, obs_test, n_iter, lr)
        return self

    def impute(self,
               pred_all = False, # If the dataset should be replaced by the model predictions
                                # or only the gaps imputed using the model
              ):
        """Impute data in tidy format using model"""
        # predict either no all dataset or only on part
        if pred_all:
            time_mask = self.T
            data_mask = self.mask
        else:
            time_mask = self.T[~self.train_idx]
            data_mask = self.mask[~self.train_idx]

        pred = self.model.predict(time_mask)
        
        imp_mean = self.data.copy()
        mean = self.scaler.inverse_transform(pred.mean)
        imp_mean.iloc[data_mask, :] = mean.cpu().numpy()
        imp_mean = imp_mean.assign(time=self.T).melt('time', value_name = 'mean')
        
        # for observations std is 0
        imp_std = pd.DataFrame(np.zeros_like(self.data), columns=self.data.columns)
        # get the diagonal of the covariance matrices (the variance) and transform to std
        std = cov2std(pred.cov)
        std = self.scaler.inverse_transform_std(std)
        imp_std.iloc[data_mask, :] = std.cpu().numpy()
        imp_std = imp_std.assign(time=self.T).melt('time',value_name = 'std')
        
        return pd.merge(imp_mean, imp_std, on=['time', 'variable'])       

# %% ../../lib_nbs/kalman/21_imputation.ipynb 17
@patch
def to_result(self: KalmanImputation, data_compl, var_names=None, units=None, pred_all=False):
    return ImputationResult(self.impute(pred_all), data_compl, self.model.filter.get_info(var_names), units)