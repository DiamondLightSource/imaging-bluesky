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
from imaging_bluesky.p49.plans.panda_plan import fly_scan  # noqa: F401

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

# Remember to add the line:
# from imaging_bluesky.p49.plans.panda_plans import fly_scan
# so that the ipython terminal is able to access the plan

# To run ipython terminal:
# 1 - Open VSCode with the container
# 2 - Open a terminal on the VSCode container
# 3 - run ipython -i startup_p49.py

# RE(fly_scan(0,10,11,1,stages.x,panda_device)) # To run on the IPython terminal

# To retrieve data:
# 1 - ssh to the server (bl49p-ea-serv-01)
# 2 - cd to /exports/mybeamline/data
# 3 - cp p49-X-panda.h5 to your home directory
# 4 - Open it in dawn
# 5 - Full path to htss rigs directory /dls_sw/htss/p49/scratch
