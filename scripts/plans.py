from pathlib import Path

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import dodal.beamlines.i13_1 as bl13j
from dodal.common.beamlines.beamline_utils import (
    set_path_provider,
)
from dodal.common.visit import (
    LocalDirectoryServiceClient,
    StaticVisitPathProvider,
)
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from dodal.utils import BeamlinePrefix, get_beamline_name
from ophyd_async.core import (
    DetectorTrigger,
    StandardFlyer,
    StaticPathProvider,
    TriggerInfo,
    UUIDFilenameProvider,
)
from ophyd_async.epics.motor import Motor
from ophyd_async.epics.pmac import (
    PmacIO,
    PmacTrajectoryTriggerLogic,
)
from ophyd_async.fastcs.panda import (
    HDFPanda,
    ScanSpecInfo,
    ScanSpecSeqTableTriggerLogic,
    SeqTable,
    SeqTableInfo,
    SeqTrigger,
    StaticSeqTableTriggerLogic,
)
from ophyd_async.plan_stubs import (
    ensure_connected,
)
from scanspec.specs import Fly, Line

# get_beamline_name with no arguments to get the
# default BL name (from $BEAMLINE)
BL = get_beamline_name("p99")
PREFIX = BeamlinePrefix(BL)
PATH = "/dls/i13-1/data/2025/cm40629-5/tmp"


# @device_factory()
# def panda() -> HDFPanda:
#     return HDFPanda(
#         f"{PREFIX.beamline_prefix}-MO-PANDA-01:",
#         path_provider=get_path_provider(),
#         name="panda",
#     )


set_path_provider(
    StaticVisitPathProvider(
        BL,
        Path("/dls/i13-1/data/2025/cm40629-5/tmp"),
        client=LocalDirectoryServiceClient(),
    )
)


# def test_store_settings():
#     p = panda()
#     yield from ensure_connected(p)
#     provider = YamlSettingsProvider("./scripts/layouts")
#     yield from store_settings(provider, "seq_table", p)


# def test_restore_settings():
#     p = panda()
#     yield from ensure_connected(p)
#     provider = YamlSettingsProvider("./scripts/layouts")
#     settings = yield from retrieve_settings(provider, "seq_table", p)
#     yield from apply_panda_settings(settings)


def no_panda():
    # Defining the frlyers and components of the scan
    motor_x = Motor(prefix="BL13J-MO-PI-02:X", name="Motor_X")
    motor_y = Motor(prefix="BL13J-MO-PI-02:Y", name="Motor_Y")
    # motor_t = Motor(prefix="BL13J-MO-STAGE-01:THETA", name="Motor_T")

    pmac = PmacIO(
        prefix="BL13J-MO-STEP-25:",
        raw_motors=[motor_y, motor_x],
        coord_nums=[1],
        name="pmac",
    )

    yield from ensure_connected(pmac, motor_x, motor_y)

    # Prepare motor info using trajectory scanning
    spec = Fly(0.01 @ (Line(motor_y, -5, 5, 11) * Line(motor_x, -5, 5, 11)))

    trigger_logic = spec
    pmac_trajectory = PmacTrajectoryTriggerLogic(pmac)
    pmac_trajectory_flyer = StandardFlyer(pmac_trajectory)

    @bpp.run_decorator()
    def inner_plan():
        # Prepare pmac with the trajectory
        yield from bps.prepare(pmac_trajectory_flyer, trigger_logic, wait=True)

        # kickoff devices waiting for all of them
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)

        yield from bps.complete_all(pmac_trajectory_flyer, wait=True)

    yield from inner_plan()


data_dir = "/dls/i13-1/data/2025/cm40629-5/tmp"


def panda_scan(start: float, stop: float, num: int, duration: float):
    provider = StaticPathProvider(UUIDFilenameProvider(), Path(data_dir))
    p = HDFPanda(
        "BL13J-TS-PANDA-02",
        path_provider=provider,
        name="panda",
    )
    motor_x = Motor(prefix="BL13J-MO-PI-02:X", name="Motor_X")
    motor_y = Motor(prefix="BL13J-MO-PI-02:Y", name="Motor_Y")
    motor_t = Motor(prefix="BL13J-MO-STAGE-01:THETA", name="Motor_T")

    pmac = PmacIO(
        prefix="BL13J-MO-STEP-25:",
        raw_motors=[motor_y, motor_t],
        coord_nums=[1],
        name="pmac",
    )
    yield from ensure_connected(pmac, motor_x, motor_y, p)
    panda_seq = StandardFlyer(StaticSeqTableTriggerLogic(p.seq[1]))

    # Prepare motor info using trajectory scanningmerlin
    spec = Fly(
        float(duration)
        @ (Line(motor_y, start, stop, num) * Line(motor_x, start, stop, num))
    )

    trigger_logic = spec
    pmac_trajectory = PmacTrajectoryTriggerLogic(pmac)
    pmac_trajectory_flyer = StandardFlyer(pmac_trajectory)

    motor_x_mres = 1e-04

    table = SeqTable()  # type: ignore
    positions = [int(x / motor_x_mres) for x in spec.frames().lower[motor_x]]

    direction = (
        SeqTrigger.POSA_LT
        if start * motor_x_mres > stop * motor_x_mres
        else SeqTrigger.POSA_GT
    )

    table += SeqTable.row(
        repeats=1,
        trigger=SeqTrigger.BITA_0,
    )
    table += SeqTable.row(
        repeats=1,
        trigger=SeqTrigger.BITA_1,
    )

    counter = 0
    for pos in positions:
        if counter == num:
            table += SeqTable.row(
                repeats=1,
                trigger=SeqTrigger.BITA_0,
            )
            table += SeqTable.row(
                repeats=1,
                trigger=SeqTrigger.BITA_1,
            )
            counter = 0

        table += SeqTable.row(
            repeats=1,
            trigger=direction,
            position=pos,
            time1=1,
            outa1=True,
            time2=1,
            outa2=False,
        )

        counter += 1
    seq_table_info = SeqTableInfo(sequence_table=table, repeats=1, prescale_as_us=1)

    # Prepare Panda file writer trigger info
    panda_hdf_info = TriggerInfo(
        number_of_events=num * num,
        trigger=DetectorTrigger.CONSTANT_GATE,
        livetime=duration,
        deadtime=0.001,
    )

    @attach_data_session_metadata_decorator()
    @bpp.run_decorator()
    @bpp.stage_decorator([p, panda_seq])
    def inner_plan():
        # Prepare pmac with the trajectory
        yield from bps.prepare(pmac_trajectory_flyer, trigger_logic, wait=True)
        # prepare sequencer table
        yield from bps.prepare(panda_seq, seq_table_info, wait=True)
        # prepare panda and hdf writer once, at start of scan
        yield from bps.prepare(p, panda_hdf_info, wait=True)

        # kickoff devices waiting for all of them
        yield from bps.kickoff(p, wait=True)
        yield from bps.kickoff(panda_seq, wait=True)
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)

        yield from bps.complete_all(pmac_trajectory_flyer, p, panda_seq, wait=True)

    yield from inner_plan()


data_dir = "/dls/i13-1/data/2025/cm40629-5/tmp"


def panda_scan_time_based():
    provider = StaticPathProvider(UUIDFilenameProvider(), Path(data_dir))
    panda02 = HDFPanda(
        "BL13J-TS-PANDA-02:",
        path_provider=provider,
        name="panda02",
    )
    # motor_x = Motor(prefix="BL13J-MO-PI-02:X", name="Motor_X")
    motor_y = Motor(prefix="BL13J-MO-PI-02:Y", name="Motor_Y")
    motor_t = Motor(prefix="BL13J-MO-STAGE-01:THETA", name="Motor_T")

    pmac = PmacIO(
        prefix="BL13J-MO-STEP-25:",
        raw_motors=[motor_y, motor_t],
        coord_nums=[1],
        name="pmac",
    )
    # detector = AravisDetector(
    #     "BL01C-DI-DCAM-02:",
    #     path_provider=provider,
    #     drv_suffix="CAM:",
    #     fileio_suffix="HDF5:",
    # )
    detector = bl13j.merlin()

    yield from ensure_connected(pmac, motor_y, motor_t, panda02, detector)

    # Prepare motor info using trajectory scanning
    scan_frame_duration = 0.01
    num_x = 500
    num_y = 4
    spec = Fly(
        scan_frame_duration
        @ (Line(motor_y, -20, 20, num_y) * ~Line(motor_t, -5, 5, num_x))
    )

    detector_deadtime = 2e-3 * 1.01
    total = num_x * num_y
    print(total)

    trigger_logic = spec
    pmac_trajectory = PmacTrajectoryTriggerLogic(pmac)
    pmac_trajectory_flyer = StandardFlyer(pmac_trajectory)
    table = panda02.seq[1]

    info = ScanSpecInfo(spec=spec, deadtime=detector_deadtime)

    panda_trigger_logic = StandardFlyer(
        ScanSpecSeqTableTriggerLogic(
            table,
            {
                # motor_t: PosOutScaleOffset.from_inenc(panda=panda02, number=4)
            },
        )
    )

    scan_frame_livetime = scan_frame_duration - detector_deadtime

    # Prepare Panda file writer trigger info
    panda_hdf_info = TriggerInfo(
        number_of_events=total,
        trigger=DetectorTrigger.CONSTANT_GATE,
        livetime=scan_frame_livetime,
        deadtime=detector_deadtime,
    )

    # Prepare Panda file writer trigger info
    detector_info = TriggerInfo(
        number_of_events=total,
        trigger=DetectorTrigger.CONSTANT_GATE,
        livetime=scan_frame_livetime,
        deadtime=detector_deadtime,
    )

    detector.drv.acquire_time.set(scan_frame_livetime)
    detector.drv.acquire_period.set(scan_frame_duration)

    @attach_data_session_metadata_decorator()
    @bpp.run_decorator()
    @bpp.stage_decorator(
        [panda02, panda_trigger_logic, detector, pmac_trajectory_flyer]
    )
    def inner_plan():
        # Prepare pmac with the trajectory
        yield from bps.prepare(pmac_trajectory_flyer, trigger_logic)
        # prepare sequencer table
        yield from bps.prepare(panda_trigger_logic, info)
        # prepare panda and hdf writer once, at start of scan
        yield from bps.prepare(panda02, panda_hdf_info)
        # prepare detector and info
        # waiting for this last prepare means all prepare functions will be complete
        yield from bps.prepare(detector, detector_info, wait=True)

        # Need to run this after detectors are prepared
        yield from bps.declare_stream(panda02, detector, name="primary", collect=True)

        # kickoff devices waiting for all of them??
        # start the detectors and hdf writers acquiring and set start moving the motors
        yield from bps.kickoff(panda02, wait=True)
        yield from bps.kickoff(panda_trigger_logic, wait=True)
        yield from bps.kickoff(pmac_trajectory_flyer, wait=True)
        yield from bps.kickoff(detector, wait=True)

        yield from bps.collect_while_completing(
            flyers=[pmac_trajectory_flyer, panda_trigger_logic, panda02, detector],
            dets=[panda02, detector],
            flush_period=0.5,
            stream_name="primary",
        )

    yield from inner_plan()
