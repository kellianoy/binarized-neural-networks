from trainer.gpuTrainer import GPUTrainer
import torch


class BayesTrainer(GPUTrainer):
    """Extended Trainer class to cover the special case of BayesBiNN

    Necessity to have a different training function to implement mu and lambda properly 

    Args:
        Trainer (Trainer): Trainer class to extend
        *args: Variable length argument list (for the Trainer class)
        **kwargs: Arbitrary keyword arguments (most likely optimizer or scheduler parameters)
    """

    def __init__(self, *args, **kwargs):
        if "test_mcmc_samples" in kwargs["training_parameters"]:
            self.test_mcmc_samples = kwargs["training_parameters"]["test_mcmc_samples"]
        else:
            raise ValueError(
                "BayesTrainer needs test_mcmc_samples to be defined in training_parameters (number of samples to use for the monte carlo prediction)")

        super().__init__(*args, **kwargs)

    def batch_step(self, inputs, targets, dataset_size):
        """Perform the training of a single sample of the batch
        """
        def closure():
            # Closure for the optimizer sending the loss to the optimizer
            self.optimizer.zero_grad()
            output = self.model.forward(inputs).to(self.device)
            loss = self.criterion(output.to(self.device),
                                  targets.to(self.device),
                                  reduction=self.reduction)
            return loss
        ### LOSS ###
        self.model.train()
        self.loss = self.optimizer.step(
            input_size=dataset_size, closure=closure)

    def predict(self, inputs, n_samples=1):
        """Predict the output of the model on the given inputs

        Args:
            inputs (torch.Tensor): Input data

        Returns:
            torch.Tensor: Mean of the predictions
            torch.Tensor: Standard deviation of the predictions
        """
        self.model.eval()
        with torch.no_grad():
            noise = []
            for _ in range(n_samples):
                noise.append(torch.bernoulli(
                    torch.sigmoid(2*self.optimizer.state["lambda"])))
            if len(noise) == 0:
                noise.append(torch.where(self.optimizer.state['mu'] <= 0,
                                         torch.zeros_like(
                                             self.optimizer.state['mu']),
                                         torch.ones_like(self.optimizer.state['mu'])))
            predictions = self.monte_carlo_prediction(inputs, noise)
        return predictions

    def test(self, inputs, labels):
        """Test the model on the given inputs and labels

        Args:
            inputs (torch.Tensor): Input data
            labels (torch.Tensor): Labels

        Returns:
            torch.Tensor: Predictions
        """
        predictions = self.predict(inputs, n_samples=self.test_mcmc_samples)
        predictions = torch.stack(predictions, dim=0)
        predictions = torch.mean(predictions, dim=0)
        if "binary_cross_entropy" in self.criterion.__name__:
            # apply exponential to get the probability
            predictions = torch.functional.F.sigmoid(predictions)
            predictions = torch.where(predictions >= 0.5, torch.ones_like(
                predictions), torch.zeros_like(predictions))
        else:
            predictions = torch.argmax(predictions, dim=1)
        return torch.mean((predictions == labels).float())

    def monte_carlo_prediction(self, inputs, noise):
        """Perform a monte carlo prediction on the given inputs

        Args:
            inputs (torch.Tensor): Input data
            noise (torch.Tensor, optional): Noise to use for the prediction. Defaults to None.

        Returns:
            torch.Tensor: Predictions
        """
        # Retrieve the parameters
        parameters = self.optimizer.param_groups[0]['params']
        predictions = []
        # We iterate over the parameters
        for n in noise:
            # 2p - 1
            torch.nn.utils.vector_to_parameters(2*n-1, parameters)
            prediction = self.model.forward(inputs).to(self.device)
            predictions.append(prediction)
        return predictions

    def epoch_step(self, train_dataset, test_loader=None):
        """Perform the training of a single epoch

        Args: 
            train_dataset (torch.Tensor): Training data
            test_loader (torch.Tensor, optional): Testing data. Defaults to None.
        """
        ### SEND BATCH ###

        dataset_size = len(train_dataset) * train_dataset.batch_size
        for inputs, targets in train_dataset:
            if len(inputs.shape) == 4:
                # remove all dimensions of size 1
                inputs = inputs.squeeze()
            self.batch_step(inputs.to(self.device),
                            targets.to(self.device), dataset_size)

        ### SCHEDULER ###
        if "scheduler" in dir(self):
            self.scheduler.step()

        ### EVALUATE ###
        if test_loader is not None:
            test = []
            for testset in test_loader:
                batch = []
                for inputs, targets in testset:
                    if len(inputs.shape) == 4:
                        # remove all dimensions of size 1
                        inputs = inputs.squeeze()
                    if "test_permutations" in dir(self):
                        self.testing_accuracy.append(
                            self.test_continual(inputs.to(self.device), targets.to(self.device)))
                    else:
                        batch.append(
                            self.test(inputs.to(self.device), targets.to(self.device)))
                test.append(torch.mean(torch.tensor(batch)))
            if "test_permutations" not in dir(self):
                self.testing_accuracy.append(test)
