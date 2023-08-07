import torch
from phase_space_reconstruction.modeling import ImageDataset, ImageDataset3D


def run_quad_scan(
        beam,
        lattice,
        screen,
        ks,
        scan_quad_id = 0,
        save_as = None
        ):
    
    """
    Runs virtual quad scan and returns image data from the
    screen downstream.

    Parameters
    ----------
    beam : bmadx.Beam
        ground truth beam
    lattice: bmadx TorchLattice
        diagnostics lattice
    screen: ImageDiagnostic
        diagnostic screen
    ks: Tensor
        quadrupole strengths. 
        shape: n_quad_strengths x n_images_per_quad_strength x 1
    save_as : str
        filename to store output dataset. Default: None.

    Returns
    -------
        dset: ImageDataset
            output image dataset
    """

    # tracking though diagnostics lattice
    diagnostics_lattice = lattice.copy()
    diagnostics_lattice.elements[scan_quad_id].K1.data = ks
    output_beam = diagnostics_lattice(beam)

    # histograms at screen
    images = screen(output_beam)

    # create image dataset
    dset = ImageDataset(ks, images)
    
    # save scan data if wanted
    if save_as is not None:
        torch.save(dset, save_as)
        print(f"dataset saved as '{save_as}'")

    return dset

def run_3d_scan(
        beam,
        lattice,
        screen,
        ks,
        vs,
        gs,
        ids = [0, 2, 4],
        save_as = None
        ):
    
    """
    Runs virtual quad + transverse deflecting cavity 2d scan and returns
    image data from the screen downstream.

    Parameters
    ----------
    beam : bmadx.Beam
        ground truth beam
    lattice: bmadx TorchLattice
        diagnostics lattice
    screen: ImageDiagnostic
        diagnostic screen
    quad_ks: Tensor
        quadrupole strengths. 
        shape: n_quad_strengths
    quad_id: int
        id of quad lattice element used for scan.
    tdc_vs: Tensor
        Transverse deflecting cavity voltages. 
        shape: n_tdc_voltages
    tdc_id: int
        id of tdc lattice element.
    save_as : str
        filename to store output dataset. Default: None.

    Returns
    -------
    dset: ImageDataset
        output image dataset
    """

    # base lattice
    diagnostics_lattice = lattice.copy()
    # params:
    params = torch.meshgrid(ks, vs, gs, indexing='ij')
    params = torch.stack(params, dim=-1).reshape((-1,3)).unsqueeze(-1)
    diagnostics_lattice.elements[ids[0]].K1.data = params[:,0].unsqueeze(-1)
    diagnostics_lattice.elements[ids[1]].VOLTAGE.data = params[:,1].unsqueeze(-1)
    diagnostics_lattice.elements[ids[2]].G.data = params[:,2].unsqueeze(-1)

    # track through lattice
    output_beam = diagnostics_lattice(beam)

    # histograms at screen
    images = screen(output_beam)

    # create image dataset
    dset = ImageDataset3D(params, images)
    
    # save scan data if wanted
    if save_as is not None:
        torch.save(dset, save_as)
        print(f"dataset saved as '{save_as}'")

    return dset