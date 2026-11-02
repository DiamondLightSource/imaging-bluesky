from bluesky import RunEngine

from imaging_bluesky.beamlines.i08_1.plans import panda_scan

RE = RunEngine()
# RE(panda_scan_time_based())
# RE(no_panda())
RE(
    panda_scan(
        start=0, start_slow=-1.9, stop=0.005, stop_slow=-1.905, duration=1, num=10
    )
)
