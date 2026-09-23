"""
A knife edge scan to determine the correct focus a certian distance from the beam.
Testing movement first.
"""

# from dodal.devices import Motor
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np
from bluesky.preprocessors import stage_decorator
from bluesky.utils import MsgGenerator
from dodal.common import inject
from ophyd_async.epics.adcore import AreaDetector
from ophyd_async.epics.motor import Motor


# it would be cool to see if you can find the plan stubs that make up a simple plan like the scan
@stage_decorator
def simple_scan(
    start_pos: float,
    stop_pos: float,
    num_points: float,
    motor: Motor = inject("sim_motor_x"),  # noqa: B008
    det: AreaDetector = inject("fds2"),  # noqa: B008
) -> MsgGenerator[None]:
    # det_signal = yield from bps.rd(det) # I think that this is the correct way to get the signal from the detector, but I am not sure.
    yield from bp.scan([det], motor, start_pos, stop_pos, num_points)


# @stage_decorator  # Ask - is it correct to have this everywhere
def knife_scan(
    start_pos: float,
    stop_pos: float,
    step_size: float,
    motor: Motor = inject("sim_motor_x"),  # noqa: B008
    det: AreaDetector = inject("fds2"),  # noqa: B008
) -> MsgGenerator[None]:
    for pos in np.arange(start_pos, stop_pos + step_size, step_size):
        yield from bps.mv(motor, pos)
        yield from bps.trigger(det)
        data = yield from bps.rd(det)
        print(
            data
        )  # I'm not about the format of the data and how to do the integration. also I don't think that you can do prints like this


# set up the detector - make sure you use the decorator which makes sure that everything is staged.
# def knife_edge_scan()

# Let's just forget about the above for now and concentrate on the logic
# I think do this in a separate place

# func 1
# Get image
# Sum image

# func 2
# plot of motor position against the sum of the image
# differentiate this to get slope
# get the width of the guassian

# ask vishal, do we want to be able to see these outputs
