import numpy as np
from sklearn.decomposition import PCA
import torch


class GaussianSimulator:
    """
    Generate samples with known correlation
    """
    def __init__(self, p, k, c, seed=None):
        self.seed = seed if seed is not None else np.random.randint(1e9)
        np.random.seed(self.seed)
        # Distribution generation parameters
        self.p = p
        self.k = k
        self.c = c
        # Distribution parameters
        self.sigmas = None
        self.mus = None
        self.contexts = None
        self._build()

    def _build(self):
        """
        Generate parameters for k p-variate gaussians with context
        """
        self.mus = np.zeros((self.k, self.p))
        self.sigmas = np.zeros((self.k, self.p, self.p))
        self.contexts = np.zeros((self.k, self.c))
        for i in range(self.k):
            self.mus[i] = np.zeros(self.p)
            self.contexts[i] = np.random.random((self.c,))
            # TODO: generate sigma using eigen decomposition
            sigma = np.random.random((self.p, self.p)) * 2 - 1
            sigma = sigma @ sigma.T
            self.sigmas[i] = sigma

    def gen_samples(self, k_n):
        """
        Generate full datasets of samples
        """
        # Sample each distribution
        n = self.k * k_n
        C = np.zeros((n, self.c))
        X = np.zeros((n, self.p))
        for i in range(self.k):
            mu, sigma, context = self.mus[i], self.sigmas[i], self.contexts[i]
            sample = np.random.multivariate_normal(mu, sigma, k_n)
            C[i * k_n:(i + 1) * k_n] = context
            X[i * k_n:(i + 1) * k_n] = sample
        return C, X


class Dataset:
    """
    Dataset
    """
    def __init__(self, C, X, Y, to_task=None, testsplit=0.2, seed=1, dtype=torch.float):
        self.seed = seed
        np.random.seed(self.seed)
        self.dtype = dtype
        self.C, self.X, self.Y = C, X, Y
        self.N, self.p_x = X.shape
        _, self.p_y = Y.shape
        self.c = C.shape[-1] 
        # Train/test split
        split = int(self.N * testsplit)
        idx = torch.randperm(self.N)
        self.train_idx = idx[:-split]
        self.test_idx = idx[-split:]
        self.batch_i = 0
        self.epoch = 0
#         # Transform into task pair dataset
#         self._build(C, X, Y)

#     def _build(self, C, X, Y):
#         """
#         Build the task pairs
#         """
# #         # TODO: Normalize C and X
# #         X_train = X[self.train_idx]
# #         C_train = C[self.train_idx]
# #         X = (X - torch.mean(X_train, 0)) / torch.std(X_train, 0)
# #         C = (C - torch.mean(C_train, 0)) / torch.std(C_train, 0)
#         self.C = np.repeat(C, self.x_p * self.y_p, axis=0)
#         self.T = np.zeros((self.N, self.x_p + self.y_p))
#         self.X = np.zeros(self.N)
#         self.Y = np.zeros(self.N)
#         for n in range(self.N):
#             t_i = (n // self.y_p) % self.x_p
#             t_j = n % self.y_p
#             m = n // (self.x_p * self.y_p)
#             # k = n // (k_n * self.p ** 2)
#             x_i = X[m, t_i]
#             y_j = Y[m, t_j]
#             self.X[n] = x_i
#             self.Y[n] = y_j
#             taskpair = np.zeros(self.x_p + self.y_p)
#             taskpair[t_i] = 1
#             taskpair[self.x_p + t_j] = 1
#             self.T[n] = taskpair
#         self.C = torch.tensor(self.C, dtype=self.dtype)
#         self.T = torch.tensor(self.T, dtype=self.dtype)
#         self.X = torch.tensor(self.X, dtype=self.dtype)
#         self.Y = torch.tensor(self.Y, dtype=self.dtype)

    def pairwise(self, C, X, Y, to_task=None):
        """
        Load a pairwise dataset of C, T, X, Y from full dataset C, X, Y, to_task()
        """
        n, p_x = X.shape
        _, p_y = Y.shape
        N = n * p_x * p_y
        C_pairwise = np.repeat(C, p_x * p_y, axis=0)
        T_pairwise = np.zeros((N, p_x + p_y))
        X_pairwise = np.zeros(N)
        Y_pairwise = np.zeros(N)
        for n in range(N):
            t_i = (n // p_y) % p_x
            t_j = n % p_y
            m = n // (p_x * p_y)
            # k = n // (k_n * self.p ** 2)
            x_i = X[m, t_i]
            y_j = Y[m, t_j]
            X_pairwise[n] = x_i
            Y_pairwise[n] = y_j
            taskpair = np.zeros(p_x + p_y)
            taskpair[t_i] = 1
            taskpair[p_x + t_j] = 1
            T_pairwise[n] = taskpair
        C_pairwise = torch.tensor(C_pairwise, dtype=self.dtype)
        T_pairwise = torch.tensor(T_pairwise, dtype=self.dtype)
        X_pairwise = torch.tensor(X_pairwise, dtype=self.dtype)
        Y_pairwise = torch.tensor(Y_pairwise, dtype=self.dtype)
        return C_pairwise, T_pairwise, X_pairwise, Y_pairwise

    def get_test(self):
        """
        Return the test set from train_test_split
        """
        return self.pairwise(self.C[self.test_idx], self.X[self.test_idx], self.Y[self.test_idx])
    
    def load_data(self, batch_size=32, device=None):
        """
        Load batch_size samples from the training set
        A single epoch should see training samples exactly once
        """
        batch_end = min(self.N, self.batch_i + batch_size)
        batch_idx = self.train_idx[self.batch_i:batch_end]
        if batch_end >= self.N:
            self.batch_i = 0
            self.epoch += 1
        else:
            self.batch_i += batch_size
        C_batch, T_batch, X_batch, Y_batch = self.pairwise(self.C[batch_idx], self.X[batch_idx], self.Y[batch_idx])
        if device is None:
            return C_batch.detach(), T_batch.detach(), X_batch.detach(), Y_batch.detach()
        return C_batch.to(device), T_batch.to(device), X_batch.to(device), Y_batch.to(device)

