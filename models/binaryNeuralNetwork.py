
import torch
from .layers import *
from .deepNeuralNetwork import *


class BNN(DNN):
    """ Binarized Neural Network (BNN)

    Neural Network with binary weights and activations, using hidden weights called "degrees of certainty" (DOCs) to approximate real-valued weights.

    Axel Laborieux et al., Synaptic metaplasticity in binarized neural
networks

    Args:
        layers (list): List of layer sizes (including input and output layers)
        init (str): Initialization method for weights
        std (float): Standard deviation for initialization
        device (str): Device to use for computation (e.g. 'cuda' or 'cpu')
        dropout (bool): Whether to use dropout
        latent_weights (bool): Whether to use latent weights or not
    """

    def __init__(self, *args, **kwargs):
        self.latent_weights = kwargs['latent_weights'] if 'latent_weights' in kwargs else True
        super().__init__(*args, **kwargs)

    def _layer_init(self, layers, dropout=False, bias=False):
        for i in range(self.n_layers+1):
            # Linear layers with BatchNorm
            if dropout and i != 0:
                layers.append(torch.nn.Dropout(p=0.2))
            self.layers.append(BinarizedLinear(
                layers[i], layers[i+1], bias=bias, device=self.device, latent_weights=self.latent_weights))
            self.layers.append(torch.nn.BatchNorm1d(
                layers[i+1], affine=not bias, track_running_stats=True, device=self.device))

    def forward(self, x):
        """Forward propagation of the binarized neural network
        Uses Sign activation function for binarization
        """
        for layer in self.layers:
            x = layer(x)
            if layer is not self.layers[-1] and isinstance(layer, torch.nn.BatchNorm1d):
                x = Sign.apply(x)
        return torch.nn.functional.log_softmax(x, dim=1)
