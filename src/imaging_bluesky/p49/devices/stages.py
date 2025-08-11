from ophyd_async.core import (
    StandardReadable,
)
from ophyd_async.epics.motor import Motor


class Stages(StandardReadable):
    """Collection of motors to control the alignment stage"""

    def __init__(self, beamline_prefix: str, name: str = "") -> None:
        with self.add_children_as_readables():
            self.x = Motor(beamline_prefix + "-MO-MAP-01:STAGE:X")
            self.theta = Motor(beamline_prefix + "-MO-MAP-01:STAGE:A")
        super().__init__(name=name)
