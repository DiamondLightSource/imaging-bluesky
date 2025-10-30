from bluesky import RunEngine
from scripts.plans import grid_scan, just_traj_scan, traj_panda_scan  # noqa: F401

RE = RunEngine()
# RE(just_traj_scan())
RE(traj_panda_scan())
# RE(grid_scan())
