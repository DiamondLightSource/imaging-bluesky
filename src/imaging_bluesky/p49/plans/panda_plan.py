from math import ceil

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from ophyd_async.core import DetectorTrigger, FlyMotorInfo, StandardFlyer, TriggerInfo
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.panda import (
    HDFPanda,
    PandaPcompDirection,
    PcompInfo,
    StaticPcompTriggerLogic,
)

# for calculations
MRES_X = -0.000125
MRES_THETA = 0.018


def fly_scan(
    start: int,
    stop: int,
    num: int,
    duration: float,
    motor: Motor,
    panda: HDFPanda,
) -> MsgGenerator:
    """
    Perform a fly scan.

    Args:
        start (float): Starting position.
        stop (float): Ending position.
        num (int): Number of steps.
        duration (float): Duration to acquire each frame, in seconds.
        motor (Motor): Motor instance.
        panda (HDFPanda): Data acquisition device.

    Yields:
    - Messages for the scan process (MsgGenerator).
    """

    # Describes the Panda PCOMP block.
    # It is responsible for generating the triggers based on a position and step size.
    panda_pcomp = StandardFlyer(StaticPcompTriggerLogic(panda.pcomp[1]))

    # MRES changes depending on the motor.
    # Getting this value from the motor will be soon available through an async function
    if motor.name == "x":
        MRES = MRES_X
    elif motor.name == "theta":
        MRES = MRES_THETA
    else:
        raise ValueError("Motor name not supported")

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
        # Info used to generate the triggers.
        panda_pcomp_info = PcompInfo(
            start_postion=ceil(start_pos / abs(MRES)),
            pulse_width=1,
            rising_edge_step=ceil(abs(width / MRES)),
            number_of_pulses=num,
            direction=PandaPcompDirection.NEGATIVE
            if width / MRES > 0
            else PandaPcompDirection.POSITIVE,
        )

        # Info on configuring the data writer block for the Panda device.
        # This sets the number of frames that are expected.
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
        # Otherwise, the motor might move before other devices are ready.
        yield from bps.kickoff(panda)
        yield from bps.kickoff(panda_pcomp, wait=True)
        yield from bps.kickoff(motor, wait=True)

        # Needs to wait for each flyable object to complete.
        yield from bps.complete_all(motor, panda_pcomp, panda, wait=True)

    yield from inner_plan()
