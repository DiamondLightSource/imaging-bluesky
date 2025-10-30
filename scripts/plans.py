# from collections.abc import Hashable
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

# from dodal.utils import BeamlinePrefix, get_beamline_name
from ophyd_async.core import (  # noqa: F401
    DetectorTrigger,
    StandardFlyer,
    # StaticPathProvider,
    TriggerInfo,
    # UUIDFilenameProvider,
)
from ophyd_async.epics.pmac import (
    PmacTrajectoryTriggerLogic,
    # PmacIO,
)
from ophyd_async.fastcs.panda import (
    # HDFPanda,
    ScanSpecInfo,
    ScanSpecSeqTableTriggerLogic,
)
from ophyd_async.plan_stubs import (
    ensure_connected,
)
from scanspec.specs import Fly, Line

BL = bl13j.BL
PREFIX = bl13j.PREFIX
PATH = "/dls/i13-1/data/2025/cm40629-5/tmp"


set_path_provider(
    StaticVisitPathProvider(
        BL,
        Path(PATH),
        client=LocalDirectoryServiceClient(),
    )
)

# ----------------------------------
# Below could be useful for testing.
# ----------------------------------
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


# ----------------------------------
# Populate panda sequence table for 1D pcomp scan.
# Use with StaticSeqTableTriggerLogic (instead of ScanSpecSeqTableTriggerLogic):
# panda_trigger_logic = StandardFlyer(StaticSeqTableTriggerLogic(plan.panda02.seq[1]))
# ----------------------------------
# motor_t_mres = 1e-04
# table = SeqTable()  # type: ignore
# positions = [int(n / motor_t_mres) for n in plan.spec.frames().lower[plan.theta]]
# direction = (
#     SeqTrigger.POSA_LT
#     if start * motor_t_mres > stop * motor_t_mres
#     else SeqTrigger.POSA_GT
# )
# table += SeqTable.row(
#     repeats=1,
#     trigger=SeqTrigger.BITA_0,
# )
# table += SeqTable.row(
#     repeats=1,
#     trigger=SeqTrigger.BITA_1,
# )
# counter = 0
# for pos in positions:
#     if counter == num:
#         table += SeqTable.row(
#             repeats=1,
#             trigger=SeqTrigger.BITA_0,
#         )
#         table += SeqTable.row(
#             repeats=1,
#             trigger=SeqTrigger.BITA_1,
#         )
#         counter = 0

#     table += SeqTable.row(
#         repeats=1,
#         trigger=direction,
#         position=pos,
#         time1=1,
#         outa1=True,
#         time2=1,
#         outa2=False,
#     )
#     counter += 1
# seq_table_info = SeqTableInfo(sequence_table=table, repeats=1, prescale_as_us=1)
# ----------------------------------


class common_plan_components:
    """"""

    def __init__(self):
        self.pmac = bl13j.step_25()
        self.pi = bl13j.sample_xyz()
        self.theta = bl13j.theta()
        self.panda02 = bl13j.panda_02()
        self.detector = bl13j.merlin()

        self.pmac_trajectory = PmacTrajectoryTriggerLogic(self.pmac)
        self.pmac_trajectory_flyer = StandardFlyer(self.pmac_trajectory)

        # ToDo: Scan spec currently defined here but will be parametrised.
        self.scan_frame_duration = 0.01
        num_fast_axis_pts = 100
        num_slow_axis_pts = 5
        x_start = -5
        x_stop = 5
        self.spec = Fly(
            self.scan_frame_duration
            @ (
                Line(self.pi.y, -20, 20, num_slow_axis_pts)
                * ~Line(self.pi.x, x_start, x_stop, num_fast_axis_pts)
            )
        )
        self.spec_trigger_logic = self.spec

        self.tot_frames = num_fast_axis_pts * num_slow_axis_pts
        print(
            f"Total frames = {self.tot_frames}\n"
            f"Exposure time = {self.tot_frames * self.scan_frame_duration}s\n"
            f"Scan demanded fast axis velocity = "
            f"{(x_stop - x_start) / num_fast_axis_pts / self.scan_frame_duration}"
        )

    def trig_info(self, deadtime: float):
        """Create file writer info based on scan definition (using TriggerInfo)."""
        # ToDo: Should get tot_frames from spec.
        return TriggerInfo(
            number_of_events=self.tot_frames,
            trigger=DetectorTrigger.CONSTANT_GATE,
            livetime=self.scan_frame_duration - deadtime,
            deadtime=deadtime,
        )


def just_traj_scan():
    """"""

    plan = common_plan_components()
    yield from ensure_connected(plan.pmac, plan.pi)

    @attach_data_session_metadata_decorator()
    @bpp.stage_decorator(
        [
            plan.pmac_trajectory_flyer,
        ]
    )
    @bpp.run_decorator()
    def inner_plan():
        # Prepare pmac with the trajectory
        yield from bps.prepare(
            plan.pmac_trajectory_flyer, plan.spec_trigger_logic, wait=True
        )

        # Start the trajectory.
        yield from bps.kickoff(plan.pmac_trajectory_flyer, wait=True)

        yield from bps.complete_all(plan.pmac_trajectory_flyer, wait=True)

    yield from inner_plan()


def traj_panda_scan():
    """"""

    plan = common_plan_components()
    yield from ensure_connected(plan.pmac, plan.pi, plan.theta, plan.panda02)

    panda_trigger_logic = StandardFlyer(
        ScanSpecSeqTableTriggerLogic(plan.panda02.seq[1])
    )

    panda_deadtime = plan.panda02._controller.get_deadtime(0)  # noqa: SLF001

    # scan_spec_info is defined based on spec and det deadtime.
    scan_spec_info = ScanSpecInfo(spec=plan.spec, deadtime=panda_deadtime)

    # Create panda file writer info based on spec and det deadtime.
    panda_hdf_info = plan.trig_info(panda_deadtime)

    @attach_data_session_metadata_decorator()
    @bpp.stage_decorator(
        [
            plan.pmac_trajectory_flyer,
            panda_trigger_logic,
            plan.panda02,
        ]
    )
    @bpp.run_decorator()
    def inner_plan():
        # Prepare pmac with the trajectory
        yield from bps.prepare(
            plan.pmac_trajectory_flyer, plan.spec_trigger_logic, group="sync_prep"
        )
        # prepare sequencer table
        yield from bps.prepare(panda_trigger_logic, scan_spec_info, group="sync_prep")
        # prepare panda and hdf writer
        yield from bps.prepare(
            plan.panda02, panda_hdf_info, group="sync_prep", wait=True
        )

        # Need to run this after detectors are prepared
        yield from bps.declare_stream(plan.panda02, name="primary", collect=True)

        # ??? (seq table triggering).
        # Start the detectors and hdf writers acquiring.
        yield from bps.kickoff(plan.panda02, group="sync_kickoff")
        yield from bps.kickoff(panda_trigger_logic, group="sync_kickoff", wait=True)

        # Start the trajectory.
        yield from bps.kickoff(plan.pmac_trajectory_flyer, wait=True)

        yield from bps.collect_while_completing(
            flyers=[plan.pmac_trajectory_flyer, panda_trigger_logic, plan.panda02],
            dets=[plan.panda02],
            flush_period=0.5,
            stream_name="primary",
        )

    yield from inner_plan()


def grid_scan():
    """"""

    plan = common_plan_components()
    yield from ensure_connected(
        plan.pmac, plan.pi, plan.theta, plan.panda02, plan.detector
    )

    # Use PosOutScaleOffset if want to compare position after start of row (GPIO) signal
    # from pmac trajectory motion program.
    panda_trigger_logic = StandardFlyer(
        ScanSpecSeqTableTriggerLogic(
            plan.panda02.seq[1],
            {
                # motor_t: PosOutScaleOffset.from_inenc(panda=panda02, number=4)
            },
        )
    )

    # detector_deadtime needs to be increased slightly to allow for the internal panda
    # clock not being precisely synced with the detectors.  Without this the detector
    # will generally miss every other frame.
    detector_deadtime = plan.detector._controller.get_deadtime(0) * 1.005  # noqa: SLF001

    # scan_spec_info is defined based on spec and det deadtime.
    scan_spec_info = ScanSpecInfo(spec=plan.spec, deadtime=detector_deadtime)

    # Create panda and detector file writer infos based on spec and det deadtime.
    panda_hdf_info = plan.trig_info(detector_deadtime)
    detector_hdf_info = plan.trig_info(detector_deadtime)

    @attach_data_session_metadata_decorator()
    @bpp.stage_decorator(
        [
            plan.pmac_trajectory_flyer,
            panda_trigger_logic,
            plan.panda02,
            plan.detector,
        ]
    )
    @bpp.run_decorator()
    def inner_plan():
        # Prepare pmac with the trajectory
        yield from bps.prepare(
            plan.pmac_trajectory_flyer, plan.spec_trigger_logic, group="sync_prep"
        )
        # prepare sequencer table
        yield from bps.prepare(panda_trigger_logic, scan_spec_info, group="sync_prep")
        # prepare panda and hdf writer
        yield from bps.prepare(plan.panda02, panda_hdf_info, group="sync_prep")
        # prepare detector and hdf writer
        yield from bps.prepare(
            plan.detector, detector_hdf_info, group="sync_prep", wait=True
        )

        # Need to run this after detectors are prepared
        yield from bps.declare_stream(
            plan.panda02, plan.detector, name="primary", collect=True
        )

        # ??? (seq table triggering).
        # Start the detectors and hdf writers acquiring.
        yield from bps.kickoff(panda_trigger_logic, group="sync_kickoff")
        yield from bps.kickoff(plan.panda02, group="sync_kickoff")
        yield from bps.kickoff(plan.detector, group="sync_kickoff", wait=True)

        # Start the trajectory.
        yield from bps.kickoff(plan.pmac_trajectory_flyer, wait=True)

        # Wait for the scan to complete whilst continuously collecting the data.
        yield from bps.collect_while_completing(
            flyers=[
                plan.pmac_trajectory_flyer,
                panda_trigger_logic,
                plan.panda02,
                plan.detector,
            ],
            dets=[plan.panda02, plan.detector],
            flush_period=0.5,
            stream_name="primary",
        )

    yield from inner_plan()
