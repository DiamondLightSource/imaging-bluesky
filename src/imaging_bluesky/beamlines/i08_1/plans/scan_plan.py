import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.motors import XYStage
from dodal.devices.pgm import PlaneGratingMonochromator
from dodal.devices.synchrotron import Synchrotron
from dodal.log import LOGGER
from ophyd_async.core import (  # noqa: F401
    DetectorTrigger,
    TriggerInfo,
)
from ophyd_async.epics.adandor3 import Andor3Detector
from ophyd_async.epics.adcore import setup_ndstats_sum
from ophyd_async.epics.pmac import (
    PmacIO,
    PmacScanInfo,
    PmacTrajectoryFlyableLogic,
)
from ophyd_async.fastcs.panda import (
    HDFPanda,
    ScanSpecInfo,
    ScanSpecSeqTableFlyableLogic,
)
from scanspec.specs import Fly, Line, step

scanning_combined = inject("scanning_combined")
scanning_coarse = inject("scanning_coarse")
pmac = inject("scanning_pmac")
detector = inject("andor_detector")
panda = inject("panda1")
synchrotron = inject("synchrotron")
pgm = inject("pgm")


def panda_scan(
    start: float,
    start_slow: float,
    stop: float,
    stop_slow: float,
    num_fast: int,
    num_slow: int,
    exposure: float,
    repetitions: int = 1,
    ramp_time: float | None = None,
    turnaround_time: float | None = None,
    scanning_combined: XYStage = scanning_combined,
    scanning_coarse: XYStage = scanning_coarse,
    pmac: PmacIO = pmac,
    detector: Andor3Detector = detector,
    panda: HDFPanda = panda,
    synchrotron: Synchrotron = synchrotron,
    pgm: PlaneGratingMonochromator = pgm,
) -> MsgGenerator[None]:

    panda_seq = ScanSpecSeqTableFlyableLogic(panda.seq[1]).with_device()
    deadtime = 0.04202

    fast_centre = stop - (stop - start) / 2
    slow_centre = stop_slow - (stop_slow - start_slow) / 2

    # Prepare motor info using trajectory scanning
    duration = exposure + deadtime
    spec = Fly(
        float(duration)
        @ (
            Line(scanning_combined.y, start_slow, stop_slow, num_slow)
            * ~Line(scanning_combined.x, start, stop, num_fast)
        )
    )
    spec = step(
        (
            Line(scanning_combined.y, start_slow, stop_slow, num_slow)
            * Line(scanning_combined.x, start, stop, num_fast)
        ),
        float(duration),
    )

    info = PmacScanInfo(spec=spec, ramp_time=ramp_time, turnaround_time=turnaround_time)

    pmac_trajectory = PmacTrajectoryFlyableLogic(pmac)
    pmac_trajectory_flyer = pmac_trajectory.with_device()

    ss_info = ScanSpecInfo(spec=spec, deadtime=0.1)
    _md = {
        "plan_args": {
            "detectors": {det.name for det in [panda, detector]},
            "spec": spec.serialize(),
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
        number_of_events=num_fast * num_slow,
        trigger=DetectorTrigger.EXTERNAL_EDGE,
        livetime=exposure,
        deadtime=deadtime,
    )
    yield from setup_ndstats_sum(detector)

    @bpp.stage_decorator([panda, panda_seq, pmac, detector])
    @bpp.baseline_decorator([scanning_combined, pgm, synchrotron])
    @bpp.run_decorator(md=_md)
    def inner_plan():
        LOGGER.info("Move coarse motors into position")
        scanning_coarse.x.set(fast_centre)
        scanning_coarse.y.set(slow_centre)

        LOGGER.info("Prepare detector and hdf writer")
        yield from bps.prepare(detector, detector_info, wait=True)

        LOGGER.info("Prepare pmac with the trajectory")
        yield from bps.prepare(pmac_trajectory_flyer, info, wait=True)

        LOGGER.info("Prepare sequencer table")
        yield from bps.prepare(panda_seq, ss_info, wait=True)

        LOGGER.info("Prepare panda and hdf writer once, at start of scan")
        yield from bps.prepare(panda, panda_hdf_info, wait=True)

        # Note: PandA datasets PVs need to be set on inenc vals
        yield from bps.declare_stream(detector, panda, name="primary", collect=True)

        LOGGER.info("kickoff devices waiting for all of them")
        yield from bps.kickoff(detector, wait=True)
        yield from bps.kickoff(panda, wait=True)
        yield from bps.kickoff(panda_seq, wait=True)

        LOGGER.info("Start the Trajectory")
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)

        LOGGER.info(
            "Waiting for the scan to complete whilst continuously collecting the data."
        )
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
