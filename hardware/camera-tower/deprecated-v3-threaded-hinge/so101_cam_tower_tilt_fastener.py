"""Support-free PLA-CF hand fastener for the SO-101 camera tilt hinge.

The set uses a deliberately coarse, non-standard Tr12x3-style printed thread.
It is not interchangeable with a metal M12 fastener.  Set FASTENER_PART to ``bolt``,
``nut`` or ``set`` before executing this CadQuery source.
"""

import math

import cadquery as cq


try:
    FASTENER_PART
except NameError:
    FASTENER_PART = "set"


# Coarse thread sized for a hardened 0.4 mm nozzle and PLA-CF.
THREAD_PITCH = 3.0
THREAD_MAJOR_DIAMETER = 12.0
THREAD_ROOT_DIAMETER = 10.4
THREAD_LENGTH = 12.0

# The smooth shoulder carries hinge shear; the thread only supplies clamp load.
SHOULDER_DIAMETER = 11.7
# 34.0 mm is the fully clamped ear/lug stack.  The loose stack is 34.9 mm;
# tightening therefore closes both 0.45 mm design gaps without crushing it.
SHOULDER_LENGTH = 34.0
HEAD_THICKNESS = 8.0
TIP_LENGTH = 1.6

# Hand-operated six-lobe head and nut.
KNOB_OUTER_DIAMETER = 32.0
KNOB_INNER_DIAMETER = 25.0
KNOB_LOBES = 6
NUT_THICKNESS = 10.0

# Female thread clearances: 0.25-0.35 mm radially plus axial flank clearance.
NUT_BORE_DIAMETER = 10.9
NUT_GROOVE_MAJOR_DIAMETER = 12.7


def _cylinder(diameter, height, z0=0.0):
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .circle(diameter / 2.0)
        .extrude(height)
    )


def _star_knob(height):
    points = []
    for i in range(KNOB_LOBES * 2):
        angle = math.radians(90.0 + i * 180.0 / KNOB_LOBES)
        radius = (
            KNOB_OUTER_DIAMETER / 2.0
            if i % 2 == 0
            else KNOB_INNER_DIAMETER / 2.0
        )
        points.append((radius * math.cos(angle), radius * math.sin(angle)))
    return cq.Workplane("XY").polyline(points).close().extrude(height)


def _swept_thread(profile_points, path_radius, z0, height):
    """Sweep a printable trapezoid around a Z-axis helix."""
    path = cq.Wire.makeHelix(
        THREAD_PITCH,
        height,
        path_radius,
        center=(0.0, 0.0, z0),
        dir=(0.0, 0.0, 1.0),
        lefthand=False,
    )
    profile = cq.Workplane("XZ").polyline(profile_points).close().wire().val()
    return cq.Solid.sweep(
        profile,
        [],
        path,
        makeSolid=True,
        isFrenet=True,
        transitionMode="round",
    )


def _external_thread(z0, length):
    root_r = THREAD_ROOT_DIAMETER / 2.0
    major_r = THREAD_MAJOR_DIAMETER / 2.0
    profile = [
        # 45-degree flanks remain self-supporting when the bolt prints upright.
        (root_r, z0 - 1.05),
        (major_r, z0 - 0.25),
        (major_r, z0 + 0.25),
        (root_r, z0 + 1.05),
    ]
    return _swept_thread(profile, (root_r + major_r) / 2.0, z0, length)


def _internal_thread_cutter(z0, length):
    bore_r = NUT_BORE_DIAMETER / 2.0
    groove_r = NUT_GROOVE_MAJOR_DIAMETER / 2.0
    profile = [
        # The internal thread roof also stays at 45 degrees or steeper.
        (bore_r - 0.05, z0 - 1.20),
        (groove_r, z0 - 0.30),
        (groove_r, z0 + 0.30),
        (bore_r - 0.05, z0 + 1.20),
    ]
    return _swept_thread(profile, (bore_r + groove_r) / 2.0, z0, length)


def build_bolt_core():
    head = _star_knob(HEAD_THICKNESS)
    # A broad collar spreads clamp force over the printed camera ear.
    collar = _cylinder(23.0, 2.0, HEAD_THICKNESS - 0.01)
    shoulder = _cylinder(
        SHOULDER_DIAMETER,
        SHOULDER_LENGTH,
        HEAD_THICKNESS,
    )
    thread_z = HEAD_THICKNESS + SHOULDER_LENGTH
    core = _cylinder(THREAD_ROOT_DIAMETER, THREAD_LENGTH, thread_z)
    tip = (
        cq.Workplane("XY")
        .workplane(offset=thread_z + THREAD_LENGTH - 0.01)
        .circle(THREAD_ROOT_DIAMETER / 2.0)
        .workplane(offset=TIP_LENGTH)
        .circle(3.2)
        .loft(combine=True)
    )
    return (
        head.union(collar)
        .union(shoulder)
        .union(core)
        .union(tip)
        .clean()
    )


def build_bolt_thread():
    thread_z = HEAD_THICKNESS + SHOULDER_LENGTH
    return cq.Workplane(obj=_external_thread(thread_z, THREAD_LENGTH))


def build_bolt():
    return build_bolt_core().union(build_bolt_thread()).clean()


def build_nut():
    nut = _star_knob(NUT_THICKNESS)
    bore = _cylinder(NUT_BORE_DIAMETER, NUT_THICKNESS + 0.4, -0.2)
    # Extend the groove past both faces to avoid a closed first thread.
    groove = cq.Workplane(
        obj=_internal_thread_cutter(-THREAD_PITCH, NUT_THICKNESS + 2.0 * THREAD_PITCH)
    )
    nut = nut.cut(bore).cut(groove)

    # Symmetric lead-in cones counter first-layer elephant foot and make the
    # nut easy to start from either side.
    lower_lead = (
        cq.Workplane("XY")
        .workplane(offset=-0.2)
        .circle(6.7)
        .workplane(offset=1.4)
        .circle(NUT_BORE_DIAMETER / 2.0)
        .loft(combine=True)
    )
    upper_lead = (
        cq.Workplane("XY")
        .workplane(offset=NUT_THICKNESS - 1.4)
        .circle(NUT_BORE_DIAMETER / 2.0)
        .workplane(offset=1.6)
        .circle(6.7)
        .loft(combine=True)
    )
    return nut.cut(lower_lead).cut(upper_lead).clean()


def build_set():
    # Natural support-free print orientation: both parts stand on broad knobs.
    bolt = build_bolt().translate((-22.0, 0.0, 0.0)).val()
    nut = build_nut().translate((22.0, 0.0, 0.0)).val()
    return cq.Compound.makeCompound([bolt, nut])


if FASTENER_PART == "bolt":
    result = build_bolt()
elif FASTENER_PART == "bolt_core":
    result = build_bolt_core()
elif FASTENER_PART == "bolt_thread":
    result = build_bolt_thread()
elif FASTENER_PART == "nut":
    result = build_nut()
elif FASTENER_PART == "set":
    result = build_set()
else:
    raise ValueError(f"Unknown FASTENER_PART={FASTENER_PART!r}")
