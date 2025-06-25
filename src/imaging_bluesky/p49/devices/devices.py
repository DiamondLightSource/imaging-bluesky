from dodal.common.beamlines.beamline_utils import (
    device_factory,
    get_path_provider,
)
from ophyd_async.fastcs.panda import HDFPanda


@device_factory()
def panda(beamline_prefix: str) -> HDFPanda:
    return HDFPanda(
        f"{beamline_prefix}-MO-PANDA-01:",
        path_provider=get_path_provider(),
        name="panda",
    )
