import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import dodal.beamlines.i08_1 as bl08j
from dodal.common import inject
from dodal.devices.motors import XYStage
from ophyd_async.epics.adandor3 import Andor3Detector
from ophyd_async.fastcs.panda import HDFPanda
from ophyd_async.core import PathProvider

from bluesky.utils import MsgGenerator
from dodal.common.beamlines.device_helpers import CAM_SUFFIX, HDF5_SUFFIX
from ophyd_async.core import (  # noqa: F401
    DetectorTrigger,
    TriggerInfo,
)
#from ophyd_async.epics.adandor3 import Andor3Detector
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

scanning_combined = inject("scanning_combined")
pmac = inject("scanning_pmac")
detector = inject("andor_detector")
panda = inject("panda1")




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
    scanning_combined: XYStage = scanning_combined,
    pmac: PmacIO = pmac,
    detector: Andor3Detector = detector,
    panda1: HDFPanda = panda,

) -> MsgGenerator[None]:

    panda_seq = ScanSpecSeqTableFlyableLogic(panda.seq[1]).with_device()

    # Prepare motor info using trajectory scanning
    spec = Fly(
        float(duration)
        @ (Line(scanning_combined.y, start_slow, stop_slow, num) * ~Line(scanning_combined.x, start, stop, num))
    )
    spec = step(
        (Line(scanning_combined.y, start_slow, stop_slow, num) * Line(scanning_combined.x, start, stop, num)),
        float(duration),
    )

    info = PmacScanInfo(spec=spec, ramp_time=ramp_time, turnaround_time=turnaround_time)

    pmac_trajectory = PmacTrajectoryFlyableLogic(pmac)
    pmac_trajectory_flyer = pmac_trajectory.with_device()

    acq_duration = (num * duration) / (num + 1)
    print(f"acq_duration = {acq_duration}")

    ss_info = ScanSpecInfo(spec=spec, deadtime=0.1)
    _md = {
        "plan_args": {
            "detectors": {det.name for det in [panda, detector]},
            "spec": repr(spec),
        },
        "plan_name": "mapping_scan",
        "shape": spec.shape(),
    }

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

    @bpp.run_decorator(md=_md)
    @bpp.baseline_decorator([scanning_combined])
    @bpp.stage_decorator([panda, panda_seq, pmac, detector])
    def inner_plan():
        # prepare detector and hdf writer
        yield from bps.prepare(detector, detector_info, wait=True)
        # Prepare pmac with the trajectory
        yield from bps.prepare(pmac_trajectory_flyer, info, wait=True)
        # prepare sequencer table
        yield from bps.prepare(panda_seq, ss_info, wait=True)
        # prepare panda and hdf writer once, at start of scan
        yield from bps.prepare(panda, panda_hdf_info, wait=True)

        # Note: PandA datasets PVs need to be set on inenc vals
        yield from bps.declare_stream(detector, panda, name="primary", collect=True)

        # kickoff devices waiting for all of them
        yield from bps.kickoff(detector, wait=True)
        yield from bps.kickoff(panda, wait=True)
        yield from bps.kickoff(panda_seq, wait=True)

        # Start the Trajectory
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)

        # Wait for the scan to complete whilst continuously collecting the data.
        yield from bps.collect_while_completing(
            flyers=[
                pmac_trajectory_flyer,
                panda,
                panda_seq,
                detector,
            ],
            dets=[detector, panda],
            flush_period=0.5,
            stream_name="primary",
        )

    yield from inner_plan()
