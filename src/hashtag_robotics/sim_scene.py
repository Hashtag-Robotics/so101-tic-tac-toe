"""The simulated workspace a dataset can actually be recorded in.

The contract model in `simulation.py` answers "do six joints move within their
limits". This answers a different question -- "can this arm pick that cube up
and drop it in that bin" -- and the difference is almost entirely physics that
had to be measured rather than reasoned about.

Every constant and every model patch below comes from
`so101-sim-lab/ornekler/_ortak.py`, where it was found the hard way over four
iterations in July 2026. The measurements are kept in the comments because a
number without its measurement is a number somebody will "clean up" later.

Two things worth knowing before changing anything here:

MuJoCo replaces a collision mesh with its convex hull. The SO-101's fingers are
hollow and curved, so their hulls fill the gap between them: the cube was being
held 16 mm away from any surface it appeared to touch. The fix replaces the
fingertip collision geoms with boxes derived from the mesh vertices.

MuJoCo's stock contact settings do not hold objects. Pyramidal friction cones,
no torsional friction and a soft solref meant a two-fingered grasp twisted the
cube out, drifted it millimetres per second, and drove the jaw visibly into it.
The recipe here -- elliptic cone, impratio 10, noslip, condim 6, priority 1 on
the jaw pair only -- is what made grasping work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hashtag_robotics.simulation import SimulationError, so101_scene_path

# The generated SO-101 draws its meshes 30.1 mm above the base body frame, so a
# base at z=0 leaves the arm floating. This drops it onto the floor.
BASE_OFFSET_Z = -0.0301

CUBE_EDGE = 0.04
CUBE_START = (0.0, -0.30, CUBE_EDGE / 2)

# The arm's workspace is toward -y, so the bin sits within reach on that side.
BIN_CENTRE = (0.18, -0.22)
BIN_WIDTH = 0.12
BIN_DEPTH = 0.12
BIN_HEIGHT = 0.05
BIN_WALL = 0.006

# Framing verified by rendering, not by reasoning about the frame.
FRONT_CAMERA = ((0.0, -0.85, 0.45), (0.0, -0.20, 0.05))

# In the gripper's local frame. The sim-lab values were measured against a scene
# built through strands_robots, whose gripper frame is not this model's: dropped
# in directly they aimed the camera at the horizon. Re-measured here instead --
# the fingertip pads sit at local z between -0.080 and -0.090, separated along
# local x, so the grasp point is a little past them and the camera looks down
# that axis from just above and behind.
WRIST_CAMERA = ((0.0, 0.045, -0.02), (0.0, 0.0, -0.12))

# Body and mesh names in the generated model. The sim-lab code addressed these
# through a `so101/` namespace that strands_robots added; loaded directly they
# carry no prefix, and a silently unmatched name here means the physics patch
# does nothing at all -- which looks exactly like it working.
GRIPPER_BODY = "gripper"
JAW_BODY = "moving_jaw_so101_v1"
GRASP_BODIES = (GRIPPER_BODY, JAW_BODY)
FIXED_FINGER_MESH = "wrist_roll_follower_so101_v1"
MOVING_JAW_MESH = "moving_jaw_so101_v1"
GRIPPER_MOTOR_MESH = "sts3215_03a_v1"

# mesh name -> (vertex z threshold in metres, box-fitting method). The threshold
# selects the fingertip pad region. An oriented box is required on the slanted
# fixed finger: an axis-aligned one bridges across the curve and leaves 12 mm.
FINGER_PAD_TARGETS = {
    FIXED_FINGER_MESH: (0.050, "obb"),
    MOVING_JAW_MESH: (0.005, "aabb"),
}


@dataclass(frozen=True)
class SceneSpec:
    """What to build. Defaults are the configuration that recorded 50 episodes."""

    name: str = "cube-to-bin"
    task: str = "pick up the red cube and drop it in the bin"
    cube: bool = True
    bin: bool = True
    cameras: tuple[str, ...] = ("front", "wrist")
    cube_start: tuple[float, float, float] = CUBE_START


@dataclass
class LoadedScene:
    model: Any
    data: Any
    spec: SceneSpec
    camera_names: list[str] = field(default_factory=list)


def _look_at(position, target) -> list[float]:
    """A camera orientation quaternion, given where it is and what it watches.

    MuJoCo cameras look down their own -z. Expressed as a target point rather
    than a target body because the wrist camera watches a point in front of the
    fingers, and there is no body there.
    """
    import numpy as np

    forward = np.array(target, dtype=float) - np.array(position, dtype=float)
    norm = np.linalg.norm(forward)
    if norm == 0:
        raise SimulationError("A camera cannot look at the point it sits on.")
    z_axis = -forward / norm
    world_up = np.array([0.0, 0.0, 1.0])
    if abs(float(z_axis @ world_up)) > 0.999:
        world_up = np.array([0.0, 1.0, 0.0])
    x_axis = np.cross(world_up, z_axis)
    x_axis /= np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)

    import mujoco

    rotation = np.column_stack([x_axis, y_axis, z_axis]).flatten()
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, rotation)
    return [float(value) for value in quat]


def _add_box(parent: Any, name: str, size, position, colour, static: bool) -> None:
    import mujoco

    body = parent.add_body()
    body.name = name
    body.pos = list(position)
    geom = body.add_geom()
    geom.name = f"{name}_geom"
    geom.type = mujoco.mjtGeom.mjGEOM_BOX
    # MuJoCo box size is the half-extent; the sim-lab helper took full edges, so
    # the halving happens here rather than in every call site.
    geom.size = [value / 2 for value in size]
    geom.rgba = list(colour)
    if not static:
        body.add_freejoint()


def _add_bin(worldbody: Any) -> None:
    """A floor plus four walls, all static.

    The success predicate anchors on the floor body; the walls are what stop the
    cube from being nudged straight back out again. Side walls are shortened by
    two wall thicknesses so the corners do not overlap.
    """
    centre_x, centre_y = BIN_CENTRE
    colour = (1.0, 0.85, 0.0, 1.0)
    _add_box(
        worldbody,
        "bin",
        (BIN_WIDTH, BIN_DEPTH, BIN_WALL),
        (centre_x, centre_y, BIN_WALL / 2),
        colour,
        static=True,
    )
    walls = (
        ("bin_wall_yp", (BIN_WIDTH, BIN_WALL, BIN_HEIGHT), (0.0, BIN_DEPTH / 2 - BIN_WALL / 2)),
        ("bin_wall_yn", (BIN_WIDTH, BIN_WALL, BIN_HEIGHT), (0.0, -BIN_DEPTH / 2 + BIN_WALL / 2)),
        (
            "bin_wall_xp",
            (BIN_WALL, BIN_DEPTH - 2 * BIN_WALL, BIN_HEIGHT),
            (BIN_WIDTH / 2 - BIN_WALL / 2, 0.0),
        ),
        (
            "bin_wall_xn",
            (BIN_WALL, BIN_DEPTH - 2 * BIN_WALL, BIN_HEIGHT),
            (-BIN_WIDTH / 2 + BIN_WALL / 2, 0.0),
        ),
    )
    for name, size, (offset_x, offset_y) in walls:
        _add_box(
            worldbody,
            name,
            size,
            (centre_x + offset_x, centre_y + offset_y, BIN_HEIGHT / 2),
            colour,
            static=True,
        )


def build(spec: SceneSpec | None = None, scene_path=None) -> LoadedScene:
    """Compile the workspace and apply the physics that makes grasping work."""
    import mujoco

    spec = spec or SceneSpec()
    path = so101_scene_path(scene_path)
    if path is None:
        raise SimulationError(
            "The mesh-accurate SO-101 model is required to record in simulation and "
            "was not found on this machine. Fetch it with the robot_descriptions "
            "package."
        )

    model_spec = mujoco.MjSpec.from_file(str(path))
    model_spec.body("base").pos = [0.0, 0.0, BASE_OFFSET_Z]

    if spec.cube:
        _add_box(
            model_spec.worldbody,
            "cube",
            (CUBE_EDGE, CUBE_EDGE, CUBE_EDGE),
            spec.cube_start,
            (1.0, 0.0, 0.0, 1.0),
            static=False,
        )
    if spec.bin:
        _add_bin(model_spec.worldbody)

    camera_names: list[str] = []
    if "front" in spec.cameras:
        position, target = FRONT_CAMERA
        camera = model_spec.worldbody.add_camera()
        camera.name = "front"
        camera.pos = list(position)
        camera.quat = _look_at(position, target)
        camera_names.append("front")
    if "wrist" in spec.cameras:
        position, target = WRIST_CAMERA
        camera = model_spec.body(GRIPPER_BODY).add_camera()
        camera.name = "wrist"
        camera.pos = list(position)
        camera.quat = _look_at(position, target)
        camera_names.append("wrist")

    model = model_spec.compile()
    data = mujoco.MjData(model)
    pad_finger_geoms(model)
    tune_grasp_contacts(model, data)
    return LoadedScene(model=model, data=data, spec=spec, camera_names=camera_names)


def pad_finger_geoms(model: Any) -> list[str]:
    """Replace fingertip collision meshes with boxes fitted to their vertices.

    MuJoCo collides meshes by their convex hull, and the SO-101's fingers are
    hollow and curved, so the hull spans the grasp gap. Measured on this model:
    the cube was held with a 16.4 mm visible gap at the fixed finger and 2.4 mm
    at the jaw; after this, 0.3 mm and 1.8 mm.

    The price is that the non-tip parts of the fingers stop colliding at all.
    That is a deliberate trade -- grasp realism over edge-case collisions -- and
    it is why this belongs in a recording scene rather than in a safety model.
    """
    import mujoco
    import numpy as np

    patched: list[str] = []
    for geom in range(model.ngeom):
        if model.geom_type[geom] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        if not (model.geom_contype[geom] | model.geom_conaffinity[geom]):
            continue  # a purely visual mesh
        mesh_name = (
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_MESH, int(model.geom_dataid[geom])) or ""
        )
        if mesh_name not in FINGER_PAD_TARGETS:
            continue

        threshold, method = FINGER_PAD_TARGETS[mesh_name]
        mesh_id = model.geom_dataid[geom]
        start, count = model.mesh_vertadr[mesh_id], model.mesh_vertnum[mesh_id]
        vertices = model.mesh_vert[start : start + count]
        # +z in the geom frame points along the finger toward the tip.
        tip = vertices[vertices[:, 2] >= threshold]
        if len(tip) < 4:
            continue

        centre = tip.mean(0)
        if method == "obb":
            rotation = np.linalg.svd(tip - centre, full_matrices=False)[2].T
            if np.linalg.det(rotation) < 0:
                rotation[:, 2] *= -1
        else:
            rotation = np.eye(3)

        local = (tip - centre) @ rotation
        low, high = local.min(0), local.max(0)
        half = (high - low) / 2
        offset = centre + rotation @ ((low + high) / 2)

        geom_rotation = np.zeros(9)
        mujoco.mju_quat2Mat(geom_rotation, model.geom_quat[geom])
        model.geom_pos[geom] = model.geom_pos[geom] + geom_rotation.reshape(3, 3) @ offset
        extra = np.zeros(4)
        mujoco.mju_mat2Quat(extra, rotation.flatten())
        combined = np.zeros(4)
        mujoco.mju_mulQuat(combined, model.geom_quat[geom], extra)
        model.geom_quat[geom] = combined
        model.geom_type[geom] = mujoco.mjtGeom.mjGEOM_BOX
        model.geom_size[geom] = half
        # The broadphase caches these separately; a stale bound silently skips
        # collisions that the new box should have.
        model.geom_rbound[geom] = float(np.linalg.norm(half))
        model.geom_aabb[geom] = [0.0, 0.0, 0.0, *half]
        patched.append(mesh_name)
    return patched


def tune_grasp_contacts(model: Any, data: Any) -> None:
    """MuJoCo's grasping recipe. With the stock settings the cube slides out.

    Stock: pyramidal cone, impratio 1, fingers at condim 3 with
    friction [1, .005, 1e-4] -- no torsional friction at all, so a two-fingered
    grasp twists the cube free.

    `priority=1` applies the hard contact to the cube-jaw pair *only*. Applied
    globally, the cube-floor rolling resistance beats the tipping moment and the
    cube freezes standing on one corner.
    """
    import mujoco

    model.opt.cone = mujoco.mjtCone.mjCONE_ELLIPTIC
    model.opt.impratio = 10.0
    # Only the noslip solver stops a held cube creeping out of the gripper, and
    # only while condim 6 rolling rows exist. Measured: 9-16 mm per 10 s to 0.00.
    model.opt.noslip_iterations = 10

    for geom in range(model.ngeom):
        if not (model.geom_contype[geom] | model.geom_conaffinity[geom]):
            continue
        body_name = (
            mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, int(model.geom_bodyid[geom])) or ""
        )
        geom_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, geom) or ""
        mesh_name = ""
        if model.geom_dataid[geom] >= 0:
            mesh_name = (
                mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_MESH, int(model.geom_dataid[geom]))
                or ""
            )

        if GRIPPER_MOTOR_MESH in mesh_name and body_name == GRIPPER_BODY:
            # The gripper servo sits inside the housing with collision enabled;
            # its convex hull gripped a deeply-inserted cube through a surface
            # nobody can see. Ghost grasp number two.
            model.geom_contype[geom] = 0
            model.geom_conaffinity[geom] = 0
        elif body_name in GRASP_BODIES:
            model.geom_priority[geom] = 1
            # condim 6 adds torsional and rolling rows; rolling 0.01 is what
            # stops the cube rolling out from between the jaw faces.
            model.geom_condim[geom] = 6
            model.geom_friction[geom] = [2.0, 0.05, 0.01]
            # The default solref [0.02, 1] is far too soft for a grasp: the servo
            # drives the jaw *into* the cube and the stored push flings it away.
            # Measured penetration 15.6 mm to 0.5 mm. timeconst 0.005 is at least
            # two timesteps, so it is hard without going unstable.
            model.geom_solref[geom] = [0.005, 1.0]
            model.geom_solimp[geom][:3] = [0.95, 0.99, 0.001]
        elif geom_name == "cube_geom":
            # Cube against the floor stays stock-like, so tipping, sliding and
            # settling all still look right.
            model.geom_condim[geom] = 3
            model.geom_friction[geom] = [1.0, 0.01, 0.0001]
            model.geom_solref[geom] = [0.02, 1.0]
            model.geom_solimp[geom][:3] = [0.9, 0.95, 0.001]

    _fix_cube_inertia(model, data)


def _fix_cube_inertia(model: Any, data: Any) -> None:
    """A 2 cm, 50 g cube given a flywheel's inertia will not behave like a cube.

    Changing `body_inertia` alone is not enough: the solver precomputes
    `dof_invweight0` from it, and that scale stays stale until `mj_setConst`
    recomputes it.
    """
    import mujoco

    cube = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cube")
    if cube < 0:
        return
    mass = float(model.body_mass[cube])
    model.body_inertia[cube] = [mass * (CUBE_EDGE**2 + CUBE_EDGE**2) / 12.0] * 3
    mujoco.mj_setConst(model, data)
