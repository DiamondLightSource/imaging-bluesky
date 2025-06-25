from pathlib import Path

from bluesky import RunEngine
from dodal.common.beamlines.beamline_utils import (
    set_path_provider,
)
from dodal.common.visit import (
    LocalDirectoryServiceClient,
    StaticVisitPathProvider,
)
from dodal.utils import get_beamline_name
from ophyd_async.plan_stubs import ensure_connected
from spectroscopy_bluesky.p49.devices import panda
from spectroscopy_bluesky.p49.stages import Stages

BL = get_beamline_name("p49")
set_path_provider(
    StaticVisitPathProvider(
        BL,
        Path("/exports/p49/data/2025"),
        client=LocalDirectoryServiceClient(),
    )
)
p49_stages = Stages("BL49P")
p = panda()

RE = RunEngine()
RE(ensure_connected(p49_stages, p))
