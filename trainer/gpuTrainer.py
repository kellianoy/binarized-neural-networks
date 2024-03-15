import torch
import tqdm


class GPUTrainer:
    """Trainer that does not require the usage of DataLoaders

    Args: 
        model (torch.nn.Module): Model to train
        optimizer (torch.optim): Optimizer to use
        optimizer_parameters (dict): Parameters of the optimizer
        criterion (torch.nn): Loss function
        device (torch.device): Device to use for the training
        kwargs: Additional arguments
            scheduler (torch.optim.lr_scheduler, optional): Scheduler to use. Defaults to None.
            scheduler_parameters (dict, optional): Parameters of the scheduler. Defaults to None.
    """

    def __init__(self, model, optimizer, optimizer_parameters, criterion, device, *args, **kwargs):
        self.model = model
        self.optimizer = optimizer(
            self.model.parameters(),
            **optimizer_parameters
        )
        self.criterion = criterion
        self.device = device
        self.training_accuracy = []
        self.testing_accuracy = []
        self.mean_testing_accuracy = []
        # Scheduler addition
        if "scheduler" in kwargs:
            scheduler = kwargs["scheduler"]
            scheduler_parameters = kwargs["scheduler_parameters"]
            self.scheduler = scheduler(
                self.optimizer, **scheduler_parameters)

    def reset_optimizer(self, optimizer_parameters):
        """Reset the optimizer parameters such as momentum and learning rate

        Args:
            optimizer_parameters (dict): Parameters of the optimizer
        """
        self.optimizer = self.optimizer.__class__(
            self.model.parameters(), **optimizer_parameters)

    def batch_step(self, inputs, targets):
        """Perform the training of a single batch

        Args: 
            inputs (torch.Tensor): Input data
            targets (torch.Tensor): Labels
        """
        ### LOSS ###
        self.loss = self.criterion(
            self.model.forward(inputs).to(self.device),
            targets.to(self.device)
        )

        ### BACKWARD PASS ###
        self.optimizer.zero_grad()
        self.loss.backward()
        self.optimizer.step()

    def epoch_step(self, train_dataset):
        """Perform the training of a single epoch

        Args: 
            train_dataset (torch.Tensor): Training data
            test_loader (torch.Tensor, optional): Testing data. Defaults to None.
        """
        ### SEND BATCH ###
        self.model.train()
        for inputs, targets in train_dataset:
            self.batch_step(inputs.to(self.device), targets.to(self.device))

    @torch.no_grad()
    def evaluate(self, test_loader, train_loader=None):
        """ Evaluate the model on the test sets

        Args:
            test_loader (torch.utils.data.DataLoader): Testing data
            train_loader (torch.utils.data.DataLoader, optional): Training data. Defaults to None.

        Returns:
            float: mean accuracy on the test sets
        """
        self.model.eval()
        with torch.no_grad():
            if test_loader is not None:
                test = []
                # Iterate over the Dataloaders
                for dataloader in test_loader:
                    batch = []
                    for inputs, targets in dataloader:
                        batch.append(self.test(inputs, targets))
                    test.append(torch.mean(torch.tensor(batch)))
                self.testing_accuracy.append(test)
                self.mean_testing_accuracy.append(
                    torch.mean(torch.tensor(test)))
            if train_loader is not None:
                train = []
                for dataloader in train_loader:
                    batch = []
                    for inputs, targets in dataloader:
                        batch.append(self.test(inputs, targets))
                    train.append(torch.mean(torch.tensor(batch)))
                self.training_accuracy.append(train)

    @torch.no_grad()
    def predict(self, inputs):
        """Predict the labels of the given inputs

        Args:
            inputs (torch.Tensor): Input data

        Returns:
            torch.Tensor: Predictions
        """
        self.model.eval()
        predictions = self.model.forward(
            inputs.to(self.device))
        return predictions

    @torch.no_grad()
    def test(self, inputs, labels):
        """ Predict labels for a full dataset and retrieve accuracy

        Args:
            inputs (torch.Tensor): Input data
            labels (torch.Tensor): Labels of the data

        Returns:
            float: Accuracy of the model on the dataset

        """
        ### ACCURACY COMPUTATION ###
        self.model.eval()
        predictions = self.predict(inputs)
        if self.model.output_function == "sigmoid":
            # apply exponential to get the probability
            predictions = torch.where(predictions >= 0.5, torch.ones_like(
                predictions), torch.zeros_like(predictions))
        else:
            predictions = torch.argmax(predictions, dim=1)
        return torch.mean((predictions == labels.to(self.device)).float())

    def pbar_update(self, pbar, epoch, n_epochs, name_loader=None, task=None):
        """Update the progress bar with the current loss and accuracy"""
        pbar.set_description(f"Epoch {epoch+1}/{n_epochs}")
        # creation of a dictionnary with the name of the test set and the accuracy
        kwargs = {}
        if len(self.testing_accuracy) > 0:
            if name_loader is not None and len(self.testing_accuracy[-1]) != len(name_loader):
                raise ValueError(
                    "Not enough names for the test sets provided"
                )
            if name_loader is None:
                if "training_accuracy" in dir(self) and len(self.training_accuracy) > 0:
                    kwargs = {
                        f"task {i+1}": f"Test: {test_acc:.2%} - Train: {train_acc:.2%}" for i, test_acc, train_acc in zip(range(len(self.testing_accuracy[-1])), self.testing_accuracy[-1], self.training_accuracy[-1])
                    }
                else:
                    kwargs = {
                        f"task {i+1}": f"Test: {accuracy:.2%}" for i, accuracy in enumerate(self.testing_accuracy[-1])
                    }
            else:
                if "training_accuracy" in dir(self) and len(self.training_accuracy) > 0:
                    kwargs = {
                        name: f"Test: {test_acc:.2%} - Train: {train_acc:.2%}" for name, test_acc, train_acc in zip(name_loader, self.testing_accuracy[-1], self.training_accuracy[-1])
                    }
                else:
                    kwargs = {
                        name: f"Test: {accuracy:.2%}" for name, accuracy in zip(name_loader, self.testing_accuracy[-1])
                    }
            pbar.set_postfix(loss=self.loss.item())
            # Do a pretty print of our results
            pbar.write("==================================")
            pbar.write("Accuracies: ")
            for key, value in kwargs.items():
                pbar.write(f"\t{key}: {value}")

    def save(self, path):
        """Save the model
        """
        torch.save(self.model.state_dict(), path)

    def load(self, path):
        """Load the model
        """
        self.model.load_state_dict(torch.load(path))
