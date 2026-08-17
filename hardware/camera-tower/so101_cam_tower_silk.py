"""Lightweight, support-free SO-101 camera tower for PLA Silk+.

The mast consists of three 200 mm modules.  Every printed part is modeled in
its intended print orientation with a broad, flat face on Z=0.  The 32x32 mm
UVC camera board mounts to a separate tilt head using its standard four M2
holes.  Set PART to: base, bottom, middle, top, camera, or assembly.
"""

import cadquery as cq


try:
    PART
except NameError:
    PART = "assembly"


# Three nominal 200 mm mast modules
MODULE_PITCH = 200.0
RAIL_WIDTH = 34.0
RAIL_HEIGHT = 14.0
SKIN = 2.8
EDGE_RIB = 3.4
CENTER_RIB = 2.8
CENTER_RIB_HEIGHT = 8.0

# Tool-free puzzle alignment plus an M3 cross bolt at every mast joint
TAB_STEM_WIDTH = 14.0
TAB_HEAD_WIDTH = 24.0
TAB_STEM_LENGTH = 9.2
TAB_TOTAL_LENGTH = 18.0
JOINT_CLEARANCE_PER_SIDE = 0.25
JOINT_PIN_DIAMETER = 3.4
JOINT_PIN_Y = 13.6
JOINT_PIN_Z = RAIL_HEIGHT / 2.0

# 32x32 UVC board used by the official SO-101 camera design
CAMERA_BOARD = 32.0
CAMERA_HOLE_PITCH = 28.0
CAMERA_M2_CLEARANCE = 2.4
CAMERA_PLATE = 44.0
CAMERA_PLATE_T = 3.2
CAMERA_LENS_CLEARANCE = 18.0

# V4 adjustable head.  The already-printed V2 camera cradle stays unchanged:
# its two 8.2 mm ears fit around the strengthened head and use the original
# M3 x 40 mm metal bolt as the pivot/clamp.  No printed screw is required.
HINGE_PIN_DIAMETER = 3.4
HINGE_LUG_WIDTH = 16.0
HINGE_HEAD_WIDTH = 16.0
HINGE_HEAD_LENGTH = 16.0
HINGE_HEAD_CENTER_Y = 198.0
HINGE_HEAD_FILLET = 2.5
HINGE_CENTER_Y_TOP = 202.0
HINGE_CENTER_Y_CAMERA = -6.0
HINGE_CENTER_Z = RAIL_HEIGHT / 2.0
TOP_RAIL_LENGTH = 190.0

# Fixed/clamped tabletop base
BASE_X = 120.0
BASE_Y = 90.0
BASE_T = 5.0
BASE_SOCKET_X = 44.0
BASE_SOCKET_Y = 30.0
BASE_SOCKET_H = 24.0


def _box(x, y, z, x0=0.0, y0=0.0, z0=0.0):
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .box(x, y, z, centered=(True, True, False))
        .translate((x0, y0, 0.0))
    )


def _vertical_cylinder(diameter, z0, height, x=0.0, y=0.0):
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .center(x, y)
        .circle(diameter / 2.0)
        .extrude(height)
    )


def _x_axis_hole(diameter, y, z, span=70.0):
    # Workplane YZ local X/Y correspond to global Y/Z; extrusion is global X.
    return (
        cq.Workplane("YZ")
        .center(y, z)
        .circle(diameter / 2.0)
        .extrude(span, both=True)
    )


def _rounded_plate(x, y, thickness, x0=0.0, y0=0.0, z0=0.0, radius=5.0):
    plate = _box(x, y, thickness, x0, y0, z0)
    return plate.edges("|Z").fillet(radius)


def _u_channel(length=MODULE_PITCH):
    """Open channel optimized for fast flat printing and cable routing."""
    skin = _box(RAIL_WIDTH, length, SKIN, y0=length / 2.0)
    edge_offset = (RAIL_WIDTH - EDGE_RIB) / 2.0
    left = _box(EDGE_RIB, length, RAIL_HEIGHT, -edge_offset, length / 2.0)
    right = _box(EDGE_RIB, length, RAIL_HEIGHT, edge_offset, length / 2.0)
    center = _box(CENTER_RIB, length, CENTER_RIB_HEIGHT, 0.0, length / 2.0)
    return skin.union(left).union(right).union(center)


def _solid_end_pad(y0, length=24.0):
    return _box(RAIL_WIDTH, length, RAIL_HEIGHT, y0=y0 + length / 2.0)


def _male_tab():
    stem = _box(
        TAB_STEM_WIDTH,
        TAB_STEM_LENGTH,
        RAIL_HEIGHT,
        y0=MODULE_PITCH + TAB_STEM_LENGTH / 2.0,
    )
    head_length = TAB_TOTAL_LENGTH - TAB_STEM_LENGTH
    head = _box(
        TAB_HEAD_WIDTH,
        head_length,
        RAIL_HEIGHT,
        y0=MODULE_PITCH + TAB_STEM_LENGTH + head_length / 2.0,
    )
    tab = stem.union(head)
    return tab.cut(
        _x_axis_hole(
            JOINT_PIN_DIAMETER,
            MODULE_PITCH + JOINT_PIN_Y,
            JOINT_PIN_Z,
        )
    )


def _cut_female_joint(part):
    clearance = 2.0 * JOINT_CLEARANCE_PER_SIDE
    stem = _box(
        TAB_STEM_WIDTH + clearance,
        TAB_STEM_LENGTH + 0.3,
        RAIL_HEIGHT + 0.4,
        y0=(TAB_STEM_LENGTH + 0.3) / 2.0 - 0.1,
        z0=-0.2,
    )
    head_length = TAB_TOTAL_LENGTH - TAB_STEM_LENGTH + 0.3
    head = _box(
        TAB_HEAD_WIDTH + clearance,
        head_length,
        RAIL_HEIGHT + 0.4,
        y0=TAB_STEM_LENGTH + head_length / 2.0,
        z0=-0.2,
    )
    return (
        part.cut(stem.union(head))
        .cut(_x_axis_hole(JOINT_PIN_DIAMETER, JOINT_PIN_Y, JOINT_PIN_Z))
    )


def _rail_shell(bottom_pad=True, top_pad=True, length=MODULE_PITCH):
    rail = _u_channel(length)
    if bottom_pad:
        rail = rail.union(_solid_end_pad(0.0))
    if top_pad:
        rail = rail.union(_solid_end_pad(length - 24.0))
    return rail


def build_bottom():
    rail = _rail_shell(bottom_pad=True, top_pad=True).union(_male_tab())
    # This hole locks the bottom rail into the tabletop base socket.
    return rail.cut(_x_axis_hole(JOINT_PIN_DIAMETER, 10.0, JOINT_PIN_Z))


def build_middle():
    rail = _rail_shell(bottom_pad=True, top_pad=True).union(_male_tab())
    return _cut_female_joint(rail)


def build_top():
    # The full-width channel stops before the old camera ears.  A solid tapered
    # shoulder transfers the load into a compact rounded head that fits between
    # those ears.  This removes the V3 fork blocks and every diamond opening.
    rail = _cut_female_joint(
        _rail_shell(bottom_pad=True, top_pad=True, length=TOP_RAIL_LENGTH)
    )
    shoulder = (
        cq.Workplane("XY")
        .moveTo(-RAIL_WIDTH / 2.0, TOP_RAIL_LENGTH - 10.0)
        .lineTo(RAIL_WIDTH / 2.0, TOP_RAIL_LENGTH - 10.0)
        .lineTo(HINGE_HEAD_WIDTH / 2.0, TOP_RAIL_LENGTH)
        .lineTo(-HINGE_HEAD_WIDTH / 2.0, TOP_RAIL_LENGTH)
        .close()
        .extrude(RAIL_HEIGHT)
    )
    head = _box(
        HINGE_HEAD_WIDTH,
        HINGE_HEAD_LENGTH,
        RAIL_HEIGHT,
        y0=HINGE_HEAD_CENTER_Y,
    )
    head = head.edges("|X").fillet(HINGE_HEAD_FILLET)
    rail = rail.union(shoulder).union(head)
    return rail.cut(
        _x_axis_hole(
            HINGE_PIN_DIAMETER,
            HINGE_CENTER_Y_TOP,
            HINGE_CENTER_Z,
        )
    )


def build_camera():
    # Board center is at Y=22.  The rear cable notch is aligned with the
    # connector visible at the lower edge of the user's camera PCB.
    plate = _rounded_plate(
        CAMERA_PLATE,
        CAMERA_PLATE,
        CAMERA_PLATE_T,
        y0=CAMERA_PLATE / 2.0,
        radius=4.5,
    )

    # Original V2 ears: preserved exactly so the user's printed cradle fits.
    ear_width = 8.2
    ear_center_x = (HINGE_LUG_WIDTH / 2.0 + 0.6) + ear_width / 2.0
    for x in (-ear_center_x, ear_center_x):
        plate = plate.union(_box(ear_width, 17.0, RAIL_HEIGHT, x, -5.5))

    # Four small standoffs protect components on the front of the PCB.
    board_center_y = CAMERA_PLATE / 2.0
    half_pitch = CAMERA_HOLE_PITCH / 2.0
    for x in (-half_pitch, half_pitch):
        for y in (board_center_y - half_pitch, board_center_y + half_pitch):
            plate = plate.union(
                _vertical_cylinder(5.0, CAMERA_PLATE_T, 2.4, x, y)
            )

    # Lens, M2 fasteners and cable connector clearances.
    plate = plate.cut(
        _vertical_cylinder(
            CAMERA_LENS_CLEARANCE,
            -0.2,
            CAMERA_PLATE_T + 3.0,
            0.0,
            board_center_y,
        )
    )
    for x in (-half_pitch, half_pitch):
        for y in (board_center_y - half_pitch, board_center_y + half_pitch):
            plate = plate.cut(
                _vertical_cylinder(
                    CAMERA_M2_CLEARANCE,
                    -0.2,
                    CAMERA_PLATE_T + 3.2,
                    x,
                    y,
                )
            )

    cable_notch = _box(16.0, 11.0, CAMERA_PLATE_T + 0.4, y0=5.5, z0=-0.2)
    plate = plate.cut(cable_notch)
    return plate.cut(
        _x_axis_hole(
            HINGE_PIN_DIAMETER,
            HINGE_CENTER_Y_CAMERA,
            HINGE_CENTER_Z,
        )
    )


def _base_gussets():
    gussets = None
    # Two 45-degree ribs reinforce the socket while remaining support-free.
    for points in (
        [(22.0, 5.0), (35.0, 5.0), (22.0, 20.0)],
        [(-22.0, 5.0), (-35.0, 5.0), (-22.0, 20.0)],
    ):
        rib = cq.Workplane("XZ").polyline(points).close().extrude(3.0, both=True)
        gussets = rib if gussets is None else gussets.union(rib)
    return gussets


def build_base():
    base = _rounded_plate(BASE_X, BASE_Y, BASE_T, radius=8.0)
    socket = _box(
        BASE_SOCKET_X,
        BASE_SOCKET_Y,
        BASE_SOCKET_H,
        z0=BASE_T,
    )
    result = base.union(socket).union(_base_gussets())

    # Open-top socket accepts the 34x14 mm lower rail without supports.
    rail_socket = _box(
        RAIL_WIDTH + 0.5,
        RAIL_HEIGHT + 0.5,
        BASE_SOCKET_H + 0.3,
        z0=BASE_T - 0.1,
    )
    result = result.cut(rail_socket)
    result = result.cut(
        _x_axis_hole(
            JOINT_PIN_DIAMETER,
            0.0,
            BASE_T + 10.0,
        )
    )

    # Four M5 screw holes and two clamp/strap slots.
    for x in (-48.0, 48.0):
        for y in (-32.0, 32.0):
            result = result.cut(_vertical_cylinder(5.5, -0.2, BASE_T + 0.4, x, y))
            result = result.cut(_vertical_cylinder(10.0, 2.2, BASE_T + 0.2, x, y))
    for x in (-43.0, 43.0):
        slot = (
            cq.Workplane("XY")
            .workplane(offset=-0.2)
            .center(x, 0.0)
            .slot2D(26.0, 7.0, 90.0)
            .extrude(BASE_T + 0.4)
        )
        result = result.cut(slot)
    return result


def _vertical_rail(part, z0):
    # Printed Y becomes assembled Z; printed open channel faces rearward.
    return (
        part.rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 90.0)
        .translate((0.0, RAIL_HEIGHT / 2.0, z0))
    )


def build_assembly():
    base = build_base().val()
    bottom = _vertical_rail(build_bottom(), BASE_T).val()
    middle = _vertical_rail(build_middle(), BASE_T + MODULE_PITCH).val()
    top = _vertical_rail(build_top(), BASE_T + 2.0 * MODULE_PITCH).val()

    # Original camera cradle sits at a nominal 600 mm lens plane.  Only the top
    # mast head changed; the cradle geometry and its M3 interface did not.
    camera = (
        build_camera()
        .translate((0.0, -HINGE_CENTER_Y_CAMERA, 600.0))
        .val()
    )
    return cq.Compound.makeCompound([base, bottom, middle, top, camera])


if PART == "base":
    result = build_base()
elif PART == "bottom":
    result = build_bottom()
elif PART == "middle":
    result = build_middle()
elif PART == "top":
    result = build_top()
elif PART == "camera":
    result = build_camera()
elif PART == "assembly":
    result = build_assembly()
else:
    raise ValueError(f"Unknown PART={PART!r}")
