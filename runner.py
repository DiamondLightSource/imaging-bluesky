from bluesky import RunEngine
from scripts.plans import (
    panda_scan_time_based,
)

RE = RunEngine()
RE(panda_scan_time_based())
# RE(no_panda())
