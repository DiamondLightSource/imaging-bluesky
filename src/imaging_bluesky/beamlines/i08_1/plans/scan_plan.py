import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import dodal.beamlines.i08_1 as bl08j
from bluesky.utils import MsgGenerator
from dodal.common.beamlines.device_helpers import CAM_SUFFIX, HDF5_SUFFIX
from ophyd_async.core import (  # noqa: F401
    DetectorTrigger,
    TriggerInfo,
)
from ophyd_async.epics.adandor3 import Andor3Detector
from ophyd_async.epics.adcore import ADWriterFactory
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
from scanspec.specs import Fly, Line, step

BL = bl08j.BL
PREFIX = bl08j.PREFIX


def panda_scan(
    start: float,
    start_slow: float,
    stop: float,
    stop_slow: float,
    num: int,
    duration: float,
    repetitions: int = 1,
    ramp_time: float | None = None,
    turnaround_time: float | None = None,
) -> MsgGenerator[None]:
    p = bl08j.panda1(bl08j.path_provider())
    motor_x = bl08j.scanning_combined().x
    motor_y = bl08j.scanning_combined().y
    # pmac = bl08j.scanning_pmac()
    pmac = PmacIO(
        prefix=f"{PREFIX.beamline_prefix}-MO-STEP-01:",
        raw_motors=[bl08j.scanning_fine().x, bl08j.scanning_fine().y],
        coord_nums=[2],
        name="pmac",
    )

    detector = Andor3Detector(
        f"{PREFIX.beamline_prefix}-EA-DET-08:",
        ADWriterFactory.hdf(
            path_provider=bl08j.path_provider(), writer_suffix=HDF5_SUFFIX
        ),
        driver_suffix=CAM_SUFFIX,
        name="AndorMarana",
    )

    # detector = Andor3DriverIO(prefix="BL08J-EA-DET-08:CAM:")
    yield from ensure_connected(pmac, motor_x, motor_y, p, detector)
    panda_seq = ScanSpecSeqTableFlyableLogic(p.seq[1]).with_device()

    # Prepare motor info using trajectory scanning
    spec = Fly(
        float(duration)
        @ (Line(motor_y, start_slow, stop_slow, num) * ~Line(motor_x, start, stop, num))
    )
    spec = step(
        (Line(motor_y, start_slow, stop_slow, num) * Line(motor_x, start, stop, num)),
        float(duration),
    )

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

    detector_info = TriggerInfo(
        number_of_events=num * num,
        trigger=DetectorTrigger.EXTERNAL_EDGE,
        livetime=duration - 0.05,
        deadtime=0.05,
    )

    @bpp.run_decorator()
    @bpp.stage_decorator([p, panda_seq, pmac, detector])
    def inner_plan():
        # prepare detector and hdf writer
        yield from bps.prepare(detector, detector_info, wait=True)
        # Prepare pmac with the trajectory
        yield from bps.prepare(pmac_trajectory_flyer, info, wait=True)
        # prepare sequencer table
        yield from bps.prepare(panda_seq, ss_info, wait=True)
        # prepare panda and hdf writer once, at start of scan
        yield from bps.prepare(p, panda_hdf_info, wait=True)

        yield from bps.declare_stream(detector, name="primary", collect=True)

        # kickoff devices waiting for all of them
        yield from bps.kickoff(detector, wait=True)
        yield from bps.kickoff(p, wait=True)
        yield from bps.kickoff(panda_seq, wait=True)

        # Start the Trajectory
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)

        # Wait for the scan to complete whilst continuously collecting the data.
        yield from bps.collect_while_completing(
            flyers=[
                pmac_trajectory_flyer,
                p,
                panda_seq,
                detector,
            ],
            dets=[detector],
            flush_period=0.5,
            stream_name="primary",
        )

    yield from inner_plan()
