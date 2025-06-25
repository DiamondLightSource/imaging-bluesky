from dodal.common.beamlines.beamline_utils import (
    device_factory,
    get_path_provider,
)
from dodal.utils import BeamlinePrefix, get_beamline_name
from ophyd_async.fastcs.panda import HDFPanda

BL = get_beamline_name("p49")
PREFIX = BeamlinePrefix(BL)


@device_factory()
def panda() -> HDFPanda:
    return HDFPanda(
        f"{PREFIX.beamline_prefix}-MO-PANDA-01:",
        path_provider=get_path_provider(),
        name="panda",
    )
