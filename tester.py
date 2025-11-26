import dodal.beamlines.i13_1 as bl13j
from bluesky import RunEngine
from ophyd_async.plan_stubs import ensure_connected  # noqa: F401
from scanspec.specs import Fly, Linspace
from scripts.plans import CommonPlanComponents  # noqa: F401

RE = RunEngine()
plan = CommonPlanComponents()
stages = bl13j.sample_xyz()
RE(
    ensure_connected(
        stages, plan.pmac, plan.pi, plan.theta, plan.theta_virtual, plan.panda02
    )
)

frame_duration_traj = 0.005
num_fast_axis_pts = 1000
fast_axis_start = -5
fast_axis_stop = 4.9
num_slow_axis_pts = 5

spec_traj = Fly(
    frame_duration_traj
    @ (
        Linspace(plan.pi.y, -20, 20, num_slow_axis_pts)
        * ~Linspace(plan.pi.x, fast_axis_start, fast_axis_stop, num_fast_axis_pts)
    )
)
