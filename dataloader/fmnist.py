from torchvision import datasets, transforms
from torch.utils.data import DataLoader
import torch


def fashion_mnist(path, batch_size, num_workers=0):
    """ Load Fashion-MNIST dataset

    Args:
        path (str): Path to save/load dataset
        batch_size (int): Batch size for training
        num_workers (int): Number of workers for data loading

    Returns:
        torch.utils.data.DataLoader: Fashion-MNIST training dataset
        torch.utils.data.DataLoader: Fashion-MNIST testing dataset
    """
    ### NORMALIZATION ###
    mean, std = 0.1307, 0.3081  # As in EWC paper
    normalisation = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ])

    ### DOWNLOAD DATASETS ###
    fashion_mnist_train = datasets.FashionMNIST(
        root=path, download=True, transform=normalisation, target_transform=None, train=True)
    fashion_mnist_test = datasets.FashionMNIST(
        root=path, download=True, transform=normalisation, target_transform=None, train=False)

    ### DATA LOADER ###
    fashion_mnist_train = DataLoader(
        fashion_mnist_train, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    fashion_mnist_test = DataLoader(
        fashion_mnist_test, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    return fashion_mnist_train, fashion_mnist_test
