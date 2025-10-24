from bluesky import RunEngine
from scripts.plans import no_panda

RE = RunEngine()
# RE(panda_scan_time_based())
RE(no_panda())
