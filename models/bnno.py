
import torch
from .optimizer import BinaryOptimizer
from .layers import *
from tqdm import trange


class BNNO(torch.nn.Module):
    """ Binarized Neural Network (BNN) with BOP (Binary Optimizer)

    Neural Network with binary weights and activations, not using latent weights.

    """

    def __init__(self, layers=[512], init='normal', std=0.01, device='cuda'):
        """ Initialize BNNO

        Args: 
            layers (list): List of layer sizes (including input and output layers)
            init (str): Initialization method for weights
            std (float): Standard deviation for initialization
            device (str): Device to use for computation (e.g. 'cuda' or 'cpu')

        """
        super(BNNO, self).__init__()
        self.n_layers = len(layers)-2
        self.layers = torch.nn.ModuleList()
        self.device = device

        ### LAYER INITIALIZATION ###
        for i in range(self.n_layers+1):
            # Linear layers with BatchNorm
            self.layers.append(BinarizedLinear(
                layers[i], layers[i+1], bias=False, device=device, latent_weights=False))
            self.layers.append(torch.nn.BatchNorm1d(
                layers[i+1], affine=True, track_running_stats=True, device=device))

        ### WEIGHT INITIALIZATION ###
        # Init weights
        for layer in self.layers[::2]:
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
        # For each pair of layers (binarized_linear + batchnorm)
        for binarized_linear, batchnorm in zip(self.layers[::2], self.layers[1::2]):
            x = binarized_linear(x)
            x = batchnorm(x)
            if batchnorm != self.layers[-1]:
                # Apply the sign function to the output of the batchnorm layer
                x = Sign.apply(x)
        return x

    def train_network(self, train_data, n_epochs, learning_rate=0.01, metaplasticity=0, weight_decay=0.01, gamma=1e-3, threshold=1e-7, **kwargs):
        """Train the binarized neural network

        Args:
            train_data (torch.utils.data.DataLoader): Training dataset
            n_epochs (int): Number of epochs to train the network
            learning_rate (float): Learning rate for the optimizer

        Returns:
            list: List of accuracies for each epoch
        """
        ### OPTIMIZER ###
        optimizer = BinaryOptimizer(self.parameters(), lr=learning_rate, gamma=gamma, threshold=threshold,
                                    metaplasticity=metaplasticity, weight_decay=weight_decay)
        loss_function = torch.nn.CrossEntropyLoss()
        accuracy_array = []
        ### TRAINING ###
        pbar = trange(n_epochs, desc='Initialization')
        for epoch in pbar:
            # Set the network to training mode
            for i, (x, y) in enumerate(train_data):
                ### FORWARD PASS ###
                # Flatten input
                x = x.view(x.shape[0], -1).to(self.device)
                y = y.to(self.device)
                y_hat = self.forward(x)
                ### LOSS ###
                loss = loss_function(y_hat, y)
                ### BACKWARD PASS ###
                optimizer.zero_grad()
                loss.backward()
                # Do a step of the optimizer
                optimizer.step()
            ### EVALUATE ###
            accuracy = []
            if 'mnist_test' in kwargs:
                accuracy.append(self.test(kwargs['mnist_test']))
            if 'fashion_mnist_test' in kwargs:
                accuracy.append(self.test(kwargs['fashion_mnist_test']))
            accuracy_array.append(accuracy)
            # Set postfix w/ all accuracies
            pbar.set_description(f"Epoch {epoch+1}/{n_epochs}")
            pbar.set_postfix(
                loss=loss.item(), mnist_test=accuracy[0], fashion_mnist_test=accuracy[1])
        return accuracy_array

    def test(self, data):
        """ Test DNN

        Args: 
            data (torch.utils.data.DataLoader): Testing data containing (data, labels) pairs 

        Returns: 
            float: Accuracy of DNN on data

        """
        ### ACCURACY ###
        self.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for x, y in data:
                # Flatten input
                x = x.view(x.shape[0], -1).to(self.device)
                y_pred = self.forward(x).to(self.device)
                # Retrieve the most likely class
                _, predicted = torch.max(y_pred.data, 1)
                total += y.size(0)
                correct += (predicted == y.to(self.device)).sum().item()
        return correct/total

    def predict(self, x):
        """ Predict labels for data

        Args: 
            data (torch.Tensor): Data to predict labels for

        Returns: 
            torch.Tensor: Predicted labels

        """
        self.eval()
        ### PREDICT ###
        with torch.no_grad():
            x = x.view(1, -1).to(self.device)
            y_pred = self.forward(x).to(self.device)
            # Retrieve the most likely class
            _, predicted = torch.max(y_pred.data, 1)
        return predicted

    def save_state(self, path):
        """ Save the state of the network

        Args:
            path (str): Path to save the state of the network
        """
        torch.save(self.state_dict(), path)

    def load_state(self, path):
        """ Load the state of the network

        Args:
            path (str): Path to load the state of the network
        """
        self.load_state_dict(torch.load(path))
