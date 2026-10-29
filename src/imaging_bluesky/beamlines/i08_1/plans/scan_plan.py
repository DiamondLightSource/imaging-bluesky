import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import dodal.beamlines.i08_1 as bl08j
from ophyd_async.core import (  # noqa: F401
    DetectorTrigger,
    TriggerInfo,
)
from ophyd_async.epics.pmac import (
    PmacIO,
    PmacScanInfo,
    PmacTrajectoryFlyableLogic,
)
from ophyd_async.fastcs.panda import (
    ScanSpecInfo,
    ScanSpecSeqTableFlyableLogic,
)
from ophyd_async.plan_stubs import (
    ensure_connected,
)
from scanspec.specs import Fly, Line

BL = bl08j.BL
PREFIX = bl08j.PREFIX


def panda_scan(
    start: float,
    stop: float,
    num: int,
    duration: float,
    repetitions: int = 1,
    ramp_time: float | None = None,
    turnaround_time: float | None = None,
):
    # p = bl08j.panda1(get_path_provider())
    p = bl08j.panda1(bl08j.path_provider())
    # motor_x = Motor(prefix="BL08J-EA-TABLE-01:XF", name="Motor_X")
    motor_x = bl08j.scanning_fine_x()
    # pmac = bl08j.scanning_pmac()
    pmac = PmacIO(
        prefix=f"{PREFIX.beamline_prefix}-MO-STEP-01:",
        raw_motors=[motor_x],
        coord_nums=[2],
        name="pmac",
    )
    yield from ensure_connected(pmac, motor_x, p)
    panda_seq = ScanSpecSeqTableFlyableLogic(p.seq[1]).with_device()

    # Prepare motor info using trajectory scanning
    spec = Fly(float(duration) @ (repetitions * ~Line(motor_x, start, stop, num)))

    info = PmacScanInfo(spec=spec, ramp_time=ramp_time, turnaround_time=turnaround_time)

    pmac_trajectory = PmacTrajectoryFlyableLogic(pmac)
    pmac_trajectory_flyer = pmac_trajectory.with_device()

    acq_duration = (num * duration) / (num + 1)
    print(f"acq_duration = {acq_duration}")

    ss_info = ScanSpecInfo(spec=spec, deadtime=0.1)

    # Prepare Panda file writer trigger info
    panda_hdf_info = TriggerInfo(
        number_of_events=0,
        trigger=DetectorTrigger.EXTERNAL_LEVEL,
        livetime=duration - 1e-5,
        deadtime=1e-5,
    )

    @bpp.run_decorator()
    @bpp.stage_decorator([p, panda_seq])
    def inner_plan():
        # Prepare pmac with the trajectory
        yield from bps.prepare(pmac_trajectory_flyer, info, wait=True)
        # prepare sequencer table
        yield from bps.prepare(panda_seq, ss_info, wait=True)
        # prepare panda and hdf writer once, at start of scan
        yield from bps.prepare(p, panda_hdf_info, wait=True)

        # kickoff devices waiting for all of them
        yield from bps.kickoff(p, wait=True)
        yield from bps.kickoff(panda_seq, wait=True)
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)

        yield from bps.complete_all(pmac_trajectory_flyer, p, panda_seq, wait=True)

    yield from inner_plan()
