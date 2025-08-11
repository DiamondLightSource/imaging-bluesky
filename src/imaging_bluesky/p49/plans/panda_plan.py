from math import ceil

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.core import (
    DetectorTrigger,
    StandardFlyer,
    TriggerInfo,
)
from ophyd_async.epics.motor import FlyMotorInfo, Motor
from ophyd_async.fastcs.panda import (
    HDFPanda,
    PandaPcompDirection,
    PcompInfo,
    StaticPcompTriggerLogic,
)

# for calculations
# MRES = -0.000125
MRES = 0.018


def fly_scan(
    start: int,
    stop: int,
    num: int,
    duration: float,
    motor: Motor,
    panda: HDFPanda,
) -> MsgGenerator:
    panda_pcomp = StandardFlyer(StaticPcompTriggerLogic(panda.pcomp[1]))

    @attach_data_session_metadata_decorator()
    @bpp.run_decorator()
    @bpp.stage_decorator([panda, panda_pcomp])
    def inner_plan():
        width = (stop - start) / (num - 1)
        start_pos = start - (width / 2)
        stop_pos = stop + (width / 2)
        motor_info = FlyMotorInfo(
            start_position=start_pos,
            end_position=stop_pos,
            time_for_move=num * duration,
        )
        panda_pcomp_info = PcompInfo(
            start_postion=ceil(start_pos / abs(MRES)),
            pulse_width=1,
            rising_edge_step=ceil(abs(width / MRES)),
            number_of_pulses=num,
            direction=PandaPcompDirection.NEGATIVE
            if width / MRES > 0
            else PandaPcompDirection.POSITIVE,
        )

        panda_hdf_info = TriggerInfo(
            number_of_events=num,
            trigger=DetectorTrigger.CONSTANT_GATE,
            livetime=duration,
            deadtime=1e-5,
        )

        # The order of these prepare calls does not matter, as we are setting the PVs.
        yield from bps.prepare(motor, motor_info)
        yield from bps.prepare(panda, panda_hdf_info)
        yield from bps.prepare(panda_pcomp, panda_pcomp_info, wait=True)

        # Kickoff the motor last to ensure other components are initialized first.
        # Otherwise, the motor might move before other parts are ready.
        yield from bps.kickoff(panda)
        yield from bps.kickoff(panda_pcomp, wait=True)
        yield from bps.kickoff(motor, wait=True)

        yield from bps.complete_all(motor, panda_pcomp, panda, wait=True)

    yield from inner_plan()
