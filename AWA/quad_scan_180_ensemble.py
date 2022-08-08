import logging
from copy import deepcopy

import torch
from torchensemble import VotingRegressor
from torch.nn.functional import mse_loss

from modeling import Imager, InitialBeam, QuadScanTransport
from torch.utils.data import DataLoader, Dataset, random_split

logging.basicConfig(level=logging.INFO)
from image_processing import import_images

location = (
    "D:\\AWA\\phase_space_tomography_07_07_22" "\\Quadscan_data_matching_solenoid_180A"
)
base_fname = location + "\\DQ7_scan1_"

all_k, all_images, all_charges, xx = import_images()
all_charges = torch.tensor(all_charges)
all_images = torch.tensor(all_images)[:,:3]
all_k = torch.tensor(all_k)[:,:3]
print(all_images.shape)


# create data loader
class ImageDataset(Dataset):
    def __init__(self, k, images):
        self.images = images
        self.k = k

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        return self.k[idx], self.images[idx]


def init_weights(m):
    if isinstance(m, torch.nn.Linear):
        torch.nn.init.xavier_uniform_(m.weight, gain=1.0)
        # torch.nn.init.xavier_uniform_(m.bias, gain=1.0)


class QuadScanModel(torch.nn.Module):
    def __init__(self, initial_beam, transport, imager):
        super(QuadScanModel, self).__init__()
        self.beam_generator = deepcopy(initial_beam)
        self.lattice = transport
        self.imager = imager

        self.beam_generator.apply(init_weights)

    def forward(self, K):
        initial_beam = self.beam_generator()
        output_beam = self.lattice(initial_beam, K)
        output_coords = torch.cat(
            [output_beam.x.unsqueeze(0), output_beam.y.unsqueeze(0)]
        )
        output_images = self.imager(output_coords)
        # return output_images

        cov = torch.cov(initial_beam.data.T)
        scalar_metric = cov.trace()
        return output_images, scalar_metric


class CustomLoss(torch.nn.MSELoss):
    def forward(self, input, target):
        #image_loss = mse_loss(input[0], target, reduction="sum")
        # return image_loss + 1.0 * input[1]
        eps = 1e-8
        image_loss = torch.sum(target * ((target + eps).log() - (input[0] + eps).log()))
        return image_loss + 1.0e2 * input[1]



defaults = {
    "s": torch.tensor(0.0).float(),
    "p0c": torch.tensor(65.0e6).float(),
    "mc2": torch.tensor(0.511e6).float(),
}

train_dset, test_dset = random_split(
    ImageDataset(
        all_k, all_images
    ), [17, 4]
)

torch.save(train_dset, "train.dset")
torch.save(test_dset, "test.dset")

train_dataloader = DataLoader(train_dset, batch_size=4, shuffle=True)
test_dataloader = DataLoader(test_dset)

# define model components and model
bins = xx[0].T[0]
bandwidth = torch.tensor(2.0e-4)

module_kwargs = {
    "initial_beam": InitialBeam(100000, n_hidden=2, width=50, **defaults),
    "transport": QuadScanTransport(torch.tensor(0.12),torch.tensor(2.84 + 0.54)),
    "imager": Imager(bins, bandwidth)
}

ensemble = VotingRegressor(
    estimator=QuadScanModel,
    estimator_args=module_kwargs,
    n_estimators=2,
    n_jobs=1
)

#from torchensemble.utils import io
#io.load(ensemble, ".")

#criterion = torch.nn.MSELoss(reduction="sum")
criterion = CustomLoss()
ensemble.set_criterion(criterion)

n_epochs = 400
ensemble.set_scheduler("CosineAnnealingLR", T_max=n_epochs)
ensemble.set_optimizer("Adam", lr=0.001)#, weight_decay=0.1)


ensemble.fit(train_dataloader, epochs=n_epochs)


