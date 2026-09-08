"""
A knife edge scan to determine the correct focus a certian distance from the beam.
Testing movement first.
"""

# from dodal.devices import Motor
import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from ophyd_async.epics.motor import Motor


def move_motor(pos: float, motor: Motor = inject("sim_motor_x")) -> MsgGenerator[None]:
    yield from bps.mv(motor, pos)
