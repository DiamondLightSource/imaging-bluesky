from bluesky import RunEngine
from scripts.plans import no_panda, panda_scan_time_based  # noqa: F401

RE = RunEngine()
# RE(no_panda())
RE(panda_scan_time_based())
