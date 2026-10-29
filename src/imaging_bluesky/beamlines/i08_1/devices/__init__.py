from dodal.utils import BeamlinePrefix, get_beamline_name

BL = get_beamline_name("i08-1")
PREFIX = BeamlinePrefix(BL)


# @device_factory()
# def detector() -> AravisDetector:
#     return AravisDetector(
#         f"{PREFIX.beamline_prefix}-EA-DET-01:",
#         path_provider=get_path_provider(),
#         drv_suffix="DET:",
#         fileio_suffix="HDF5:",
#     )
