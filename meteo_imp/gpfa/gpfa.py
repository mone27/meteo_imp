# AUTOGENERATED! DO NOT EDIT! File to edit: ../../lib_nbs/GPFA/0_GPFA.ipynb.

# %% auto 0
__all__ = ['GPFAKernel', 'compute_gpfa_covariance', 'GPFAZeroMean', 'GPFA']

# %% ../../lib_nbs/GPFA/0_GPFA.ipynb 16
import torch
import gpytorch

from fastcore.foundation import patch
import pandas as pd

# %% ../../lib_nbs/GPFA/0_GPFA.ipynb 18
class GPFAKernel(gpytorch.kernels.Kernel):
    """
    Kernel to implement Gaussian Processes Factor Analysis
    """
    def __init__(self,
                 n_features: int, # number of variables at each time step
                 latent_kernel: gpytorch.kernels.Kernel, # func that returns any valid GPyTorch Kernel used to model the relationship over time of the latent
                 latent_dims:int = 1,  # Number of latent dims
                 Lambda: torch.tensor = None, #(n_features * latent_dims) initial value for factor loading matrix. If None init to one
                 psi: torch.tensor = None, #(n_features) initial value for random noise covariance. Note this is only the diagonal matrix
                 **kwargs):
        super(GPFAKernel, self).__init__(**kwargs)
        
        # Number of features in the X for each time step
        self.n_features = n_features

        self.latent_dims = latent_dims
        
        # see GPyTorch Kernels
        self.register_parameter(
            name = "Lambda",
            parameter = torch.nn.Parameter(torch.rand(self.n_features, self.latent_dims)))
        
        # each dim has it's own latent kernel
        self.latent_kernels = torch.nn.ModuleList([latent_kernel() for _ in range(self.latent_dims)])
        
        self.register_parameter(
            name = "raw_psi_diag",
            parameter = torch.nn.Parameter(torch.zeros(self.n_features))) 
        self.register_constraint("raw_psi_diag", gpytorch.constraints.Positive())
        if psi is not None: self.psi = psi
    
    # Convenient getter and setter for psi, since there is the Positive() constraint
    @property
    def psi(self):
        # when accessing the parameter, apply the constraint transform
        return self.raw_psi_diag_constraint.transform(self.raw_psi_diag)

    @psi.setter
    def psi(self, value):
        return self._set_psi(value)

    def _set_psi(self, value):
        if not torch.is_tensor(value):
            value = torch.as_tensor(value).to(self.raw_psi_diag)
        # when setting the paramater, transform the actual value to a raw one by applying the inverse transform
        self.initialize(raw_psi_diag=self.raw_psi_diag_constraint.inverse_transform(value))
    

        
    def forward(self, t1, t2, diag = False, last_dim_is_batch=False, **params):

        # not implemented yet
        assert diag is False
        assert last_dim_is_batch is False

        # take the number of observations from the input
        n_obs = t1.shape[0]

        # compute the latent kernel
        kT = torch.stack([ kernel(t1, t2, diag, last_dim_is_batch, **params).evaluate() # this may make the whole thing slow as it breaks lazy evaluations
                         for kernel in self.latent_kernels], dim=2)
        return compute_gpfa_covariance(self.Lambda, kT, self.psi, self.n_features, n_obs)
    
    def num_outputs_per_input(self, x1,x2):
        return self.n_features

# this is a separate function, because torch script cannot take self as a parameter
@torch.jit.script
def compute_gpfa_covariance(Lambda, kT, psi, n_features, n_obs):
    # pre allocate covariance matrix
    X_cov = torch.empty(n_features * n_obs, n_features * n_obs, device=Lambda.device)
    for i in torch.arange(n_obs):
        for j in torch.arange(n_obs):
            # i:i+1 is required to keep the number of dimensions
            cov =  Lambda @ torch.diag(kT[i,j,:]) @ Lambda.T
            # only diagonals add the noise
            if i == j: cov += torch.diag(psi)
            # add a block of size n_features*n_features to the covariance matrix
            X_cov[i*n_features:(i*n_features + n_features),j*n_features:(j*n_features+n_features)] = cov
    return X_cov

# %% ../../lib_nbs/GPFA/0_GPFA.ipynb 25
class GPFAZeroMean(gpytorch.means.Mean):
    """
    Zero Mean function to be used in GPFA, as it takes into account the number of features
    """
    def __init__(self, n_features, device):
        super().__init__()
        self.n_features = n_features
        self.device = device
    def forward(self, input):
        shape = input.shape[0] * self.n_features
        return torch.zeros(shape, device=self.device)

# %% ../../lib_nbs/GPFA/0_GPFA.ipynb 27
class GPFA(gpytorch.models.ExactGP):
    latent_kernel = gpytorch.kernels.RBFKernel
    def __init__(self, train_x, train_y, likelihood, n_features,latent_dims=1):
        super(GPFA, self).__init__(train_x, train_y, likelihood)
        self.likelihood = likelihood
        self.mean_module = GPFAZeroMean(n_features, train_x.device) # gets device from train_x
        self.covar_module = GPFAKernel(n_features, self.latent_kernel, latent_dims = latent_dims)

    def forward(self, x, **params):
        mean_x = self.mean_module(x)
        covar_x = self.covar_module(x, **params)
        return gpytorch.distributions.MultivariateNormal(mean_x, covar_x)

# %% ../../lib_nbs/GPFA/0_GPFA.ipynb 56
@patch
def get_info(self: GPFA,
             var_names = None # Optional variable names for better printing
            ) -> dict[str, pd.DataFrame]:
    "Model info for a GPFA with a RBFKernel"
    out = {}
    
    latent_names = [f"z{i}" for i in range(self.covar_module.latent_dims)]
    
    out["Lambda"] = pd.concat([
        None if var_names is None else pd.Series(var_names, name='variable'),
        pd.DataFrame(
            self.covar_module.Lambda.detach().cpu().numpy(),
            columns=latent_names)],
        axis=1)
    
    ls = [self.covar_module.latent_kernels[i].lengthscale.detach().item() for i in range(self.covar_module.latent_dims)]
    out["lengthscale"] = pd.DataFrame({
        'latent': latent_names,
        'lengthscale': ls
    })
    
    psi = self.covar_module.psi.detach().cpu().numpy()
    out["psi"] = pd.DataFrame({
        'variable': var_names,
        'psi': psi 
    })
    
    out["likelihood"] = pd.DataFrame({'noise': [self.likelihood.noise_covar.noise.detach().item()]})
    
    return out

# %% ../../lib_nbs/GPFA/0_GPFA.ipynb 64
@patch
def get_info(self: GPFA,
             var_names = None # Optional variable names for better printing
            ) -> dict[str, pd.DataFrame]:
    "Model info for a GPFA with a RBFKernel"
    out = {}
    
    latent_names = [f"z{i}" for i in range(self.covar_module.latent_dims)]
    
    out["Lambda"] = pd.concat([
        None if var_names is None else pd.Series(var_names, name='variable'),
        pd.DataFrame(
            self.covar_module.Lambda.detach().cpu().numpy(),
            columns=latent_names)],
        axis=1)
    
    ls = [self.covar_module.latent_kernels[i].lengthscale.detach().item() for i in range(self.covar_module.latent_dims)]
    out["lengthscale"] = pd.DataFrame({
        'latent': latent_names,
        'lengthscale': ls
    })
    
    psi = self.covar_module.psi.detach().cpu().numpy()
    out["psi"] = pd.DataFrame({
        'variable': var_names,
        'psi': psi 
    })
    
    out["likelihood"] = pd.DataFrame({'noise': [self.likelihood.noise_covar.noise.detach().item()]})
    
    return out

# %% ../../lib_nbs/GPFA/0_GPFA.ipynb 70
@patch
def get_info(self: GPFA,
             var_names = None # Optional variable names for better printing
            ) -> dict[str, pd.DataFrame]:
    "Model info for a GPFA with a RBFKernel"
    out = {}
    
    latent_names = [f"z{i}" for i in range(self.covar_module.latent_dims)]
    
    out["Lambda"] = pd.concat([
        None if var_names is None else pd.Series(var_names, name='variable'),
        pd.DataFrame(
            self.covar_module.Lambda.detach().cpu().numpy(),
            columns=latent_names)],
        axis=1)
    
    ls = [self.covar_module.latent_kernels[i].lengthscale.detach().item() for i in range(self.covar_module.latent_dims)]
    out["lengthscale"] = pd.DataFrame({
        'latent': latent_names,
        'lengthscale': ls
    })
    
    psi = self.covar_module.psi.detach().cpu().numpy()
    out["psi"] = pd.DataFrame({
        'variable': var_names,
        'psi': psi 
    })
    
    out["likelihood"] = pd.DataFrame({'noise': [self.likelihood.noise_covar.noise.detach().item()]})
    
    return out
