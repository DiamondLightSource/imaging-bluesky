from pathlib import Path

from bluesky import RunEngine
from dodal.common.beamlines.beamline_utils import (
    set_path_provider,
)
from dodal.common.visit import (
    LocalDirectoryServiceClient,
    StaticVisitPathProvider,
)
from ophyd_async.plan_stubs import ensure_connected

from imaging_bluesky.p49.devices import BL, alignment_stages, detector, panda

# The following line is necessary so that the iPython terminal can access the plan
from imaging_bluesky.p49.plans.panda_plan import fly_scan  # noqa: F401

set_path_provider(
    StaticVisitPathProvider(
        BL,
        Path("/exports/mybeamline/data"),
        client=LocalDirectoryServiceClient(),
    )
)


stages = alignment_stages()
panda_device = panda()
aravis = detector()


RE = RunEngine()
RE(ensure_connected(stages, panda_device, aravis))
