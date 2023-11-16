
import torch
from .layers import *


class BNN(torch.nn.Module):
    """ Binarized Neural Network (BNN) 

    Neural Network with binary weights and activations, using hidden weights called "degrees of certainty" (DOCs) to approximate real-valued weights.

    Axel Laborieux et al., Synaptic metaplasticity in binarized neural
networks
    """

    def __init__(self, layers=[512], init='gauss', std=0.01, device='cuda', latent_weights=True, dropout=False):
        """ Initialize BNN

        Args: 
            layers (list): List of layer sizes (including input and output layers)
            init (str): Initialization method for weights
            std (float): Standard deviation for initialization
            device (str): Device to use for computation (e.g. 'cuda' or 'cpu')
            latent_weights (bool): Whether to use latent weights or not

        """
        super(BNN, self).__init__()
        self.n_layers = len(layers)-2
        self.layers = torch.nn.ModuleList()
        self.device = device
        self.latent_weights = latent_weights
        self.dropout = dropout

        ### LAYER INITIALIZATION ###
        for i in range(self.n_layers+1):
            # Linear layers with BatchNorm
            self.layers.append(BinarizedLinear(
                layers[i], layers[i+1], bias=False, device=device, latent_weights=latent_weights))
            self.layers.append(torch.nn.BatchNorm1d(
                layers[i+1], affine=True, track_running_stats=True, device=device))
            if dropout:
                self.layers.append(torch.nn.Dropout(p=0.2))
        # Compute the number of different layers (binarized_linear or batchnorm or dropout)
        self.n_diff_layers = len(self.layers) // len(layers) + 1
        print(self.n_diff_layers)

        ### WEIGHT INITIALIZATION ###
        for layer in self.layers[::self.n_diff_layers]:
            if init == 'gauss':
                torch.nn.init.normal_(
                    layer.weight, mean=0.0, std=std)
            elif init == 'uniform':
                torch.nn.init.uniform_(
                    layer.weight, a=-std/2, b=std/2)
            elif init == 'xavier':
                torch.nn.init.xavier_normal_(layer.weight)

    def forward(self, x):
        """Forward propagation of the binarized neural network"""
        for layer in self.layers:
            x = layer(x)
            if layer != self.layers[-1]:
                x = Sign.apply(x)
        return x
