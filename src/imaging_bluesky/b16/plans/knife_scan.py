"""
A knife scan to determine the correct focus a certian distance from the beam.
Testing movement first.
"""

# from dodal.devices import Motor
import bluesky.plan_stubs as bps
from dodal.common import inject
from ophyd_async.epics.motor import Motor


def move_motor(pos: float, attol1: Motor = inject("attol1")):
    yield from bps.mv(attol1, pos)
