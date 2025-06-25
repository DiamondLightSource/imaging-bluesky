from pathlib import Path

from bluesky import RunEngine
from dodal.common.beamlines.beamline_utils import (
    set_path_provider,
)
from dodal.common.visit import (
    LocalDirectoryServiceClient,
    StaticVisitPathProvider,
)
from dodal.utils import BeamlinePrefix, get_beamline_name
from ophyd_async.plan_stubs import ensure_connected

from imaging_bluesky.p49.devices.devices import panda
from imaging_bluesky.p49.devices.stages import Stages

BL = get_beamline_name("p49")
PREFIX = BeamlinePrefix(BL)

set_path_provider(
    StaticVisitPathProvider(
        get_beamline_name("p49"),
        Path("/exports/mybeamline/data"),
        client=LocalDirectoryServiceClient(),
    )
)


stages = Stages(PREFIX.beamline_prefix)
panda_device = panda(PREFIX.beamline_prefix)

RE = RunEngine()
RE(ensure_connected(stages, panda_device))
