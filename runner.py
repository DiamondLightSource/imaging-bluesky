from bluesky import RunEngine
from scripts.plans import no_panda, panda_scan_time_based  # noqa: F401

RE = RunEngine()
RE(panda_scan_time_based())
# RE(no_panda())
