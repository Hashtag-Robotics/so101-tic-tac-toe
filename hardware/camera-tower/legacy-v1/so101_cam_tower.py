"""Parametric 600 mm modular camera tower for the SO-101 workcell.

The three modules each contribute 200 mm to the assembled height.  The bottom
and middle modules are 220 mm tall as printed because their 20 mm male tenons
slide into the next module; the overlap keeps the assembled height at 600 mm.

Set PART to one of: bottom, middle, top, assembly.
This source is intentionally self-contained so it can be rendered by the
Strands CAD CadQuery tools.
"""

import cadquery as cq


try:
    PART
except NameError:
    PART = "assembly"


# Stack and mast dimensions (mm)
MODULE_PITCH = 200.0
MALE_HEIGHT = 20.0
MAST_OUTER = 40.0
MAST_WALL = 3.2
MAST_INNER = MAST_OUTER - 2.0 * MAST_WALL

# Keyed slip-fit joint: rectangular section blocks 90-degree misassembly;
# the offset pin hole blocks the remaining 180-degree orientation.
PLUG_X = 31.4
PLUG_Y = 29.4
SOCKET_X = 32.0
SOCKET_Y = 30.0
SOCKET_DEPTH = 22.0
COLLAR_XY = 46.0
COLLAR_HEIGHT = 26.0
FIT_CLEARANCE_PER_SIDE = (SOCKET_X - PLUG_X) / 2.0

# Joint locking and cable routing
PIN_DIAMETER = 3.4       # M3 clearance
PIN_Y_OFFSET = 11.0      # makes the connector orientation unique
PIN_LOCAL_Z = 10.0
CABLE_BORE = 16.0

# Base and camera platform
BASE_X = 160.0
BASE_Y = 120.0
BASE_T = 8.0
PLATFORM_X = 100.0
PLATFORM_Y = 70.0
PLATFORM_T = 8.0


def _box(x, y, z, z0=0.0):
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .box(x, y, z, centered=(True, True, False))
    )


def _vertical_cylinder(diameter, z0, height, x=0.0, y=0.0):
    return (
        cq.Workplane("XY")
        .workplane(offset=z0)
        .center(x, y)
        .circle(diameter / 2.0)
        .extrude(height)
    )


def _cross_pin_hole(local_z):
    # Workplane YZ local coordinates map to global Y/Z; extrusion is along X.
    return (
        cq.Workplane("YZ")
        .center(PIN_Y_OFFSET, local_z)
        .circle(PIN_DIAMETER / 2.0)
        .extrude(COLLAR_XY + 8.0, both=True)
    )


def _rounded_plate(x, y, thickness, z0, radius):
    plate = _box(x, y, thickness, z0)
    return plate.edges("|Z").fillet(radius)


def _male_tenon():
    # A short tapered nose gives a printer-tolerant lead-in while preserving
    # the full-depth 0.30 mm/side slip fit below it.
    straight = _box(PLUG_X, PLUG_Y, MALE_HEIGHT - 1.5, MODULE_PITCH)
    nose = (
        cq.Workplane("XY")
        .workplane(offset=MODULE_PITCH + MALE_HEIGHT - 1.6)
        .rect(PLUG_X, PLUG_Y)
        .workplane(offset=1.6)
        .rect(PLUG_X - 1.2, PLUG_Y - 1.2)
        .loft(combine=True)
    )
    tenon = straight.union(nose)
    tenon = tenon.cut(
        _vertical_cylinder(CABLE_BORE, MODULE_PITCH - 0.2, MALE_HEIGHT + 0.4)
    )
    tenon = tenon.cut(_cross_pin_hole(MODULE_PITCH + PIN_LOCAL_Z))
    return tenon


def _male_mast():
    outer = _box(MAST_OUTER, MAST_OUTER, MODULE_PITCH)
    inner = _box(MAST_INNER, MAST_INNER, 182.0, 12.0)
    mast = outer.cut(inner)
    mast = mast.cut(_vertical_cylinder(CABLE_BORE, -0.2, MODULE_PITCH + MALE_HEIGHT + 0.4))
    return mast.union(_male_tenon())


def _female_mast(add_male=False):
    collar = _box(COLLAR_XY, COLLAR_XY, COLLAR_HEIGHT)
    upper = _box(MAST_OUTER, MAST_OUTER, MODULE_PITCH - 25.8, 25.8)
    mast = collar.union(upper)

    # Female socket is open from the print bed.  An 8 mm structural web above
    # it connects to the hollow mast; the cable bore passes through the web.
    socket = _box(SOCKET_X, SOCKET_Y, SOCKET_DEPTH + 0.2, -0.1)
    hollow = _box(MAST_INNER, MAST_INNER, 164.0, 30.0)
    mast = mast.cut(socket).cut(hollow)
    mast = mast.cut(_vertical_cylinder(CABLE_BORE, -0.2, MODULE_PITCH + MALE_HEIGHT + 0.4))
    mast = mast.cut(_cross_pin_hole(PIN_LOCAL_Z))

    if add_male:
        mast = mast.union(_male_tenon())
    return mast


def _base_gussets():
    gussets = None

    # X/Z triangles, extruded in Y.
    for points in (
        [(20.0, 8.0), (47.0, 8.0), (20.0, 46.0)],
        [(-20.0, 8.0), (-47.0, 8.0), (-20.0, 46.0)],
    ):
        rib = cq.Workplane("XZ").polyline(points).close().extrude(4.0, both=True)
        gussets = rib if gussets is None else gussets.union(rib)

    # Y/Z triangles, extruded in X.
    for points in (
        [(20.0, 8.0), (47.0, 8.0), (20.0, 46.0)],
        [(-20.0, 8.0), (-47.0, 8.0), (-20.0, 46.0)],
    ):
        rib = cq.Workplane("YZ").polyline(points).close().extrude(4.0, both=True)
        gussets = gussets.union(rib)

    return gussets


def build_bottom():
    base = _rounded_plate(BASE_X, BASE_Y, BASE_T, 0.0, 9.0)
    result = base.union(_male_mast()).union(_base_gussets())

    # Four M5 clearance/counterbore holes for screw-down mounting.
    for x in (-65.0, 65.0):
        for y in (-45.0, 45.0):
            result = result.cut(_vertical_cylinder(5.5, -0.2, BASE_T + 0.4, x, y))
            result = result.cut(_vertical_cylinder(10.0, 5.0, BASE_T - 4.8, x, y))

    # Two rounded clamp/strap slots.  They also accept small F-clamps.
    for x in (-55.0, 55.0):
        slot = (
            cq.Workplane("XY")
            .workplane(offset=-0.2)
            .center(x, 0.0)
            .slot2D(32.0, 8.0, 90.0)
            .extrude(BASE_T + 0.4)
        )
        result = result.cut(slot)

    # Rear cable exit above the base.  The internal path remains optional;
    # larger molded USB plugs can simply be routed outside the mast.
    cable_exit = _box(18.0, 54.0, 18.0, 11.0).translate((0.0, -27.0, 0.0))
    result = result.cut(cable_exit)
    return result


def build_middle():
    return _female_mast(add_male=True)


def _platform_gussets():
    gussets = None
    for y in (-15.0, 15.0):
        for points in (
            [(20.0, 160.0), (49.0, 192.0), (20.0, 192.0)],
            [(-20.0, 160.0), (-49.0, 192.0), (-20.0, 192.0)],
        ):
            rib = (
                cq.Workplane("XZ")
                .polyline(points)
                .close()
                .extrude(2.5, both=True)
                .translate((0.0, y, 0.0))
            )
            gussets = rib if gussets is None else gussets.union(rib)
    return gussets


def build_top():
    result = _female_mast(add_male=False)
    platform = _rounded_plate(
        PLATFORM_X, PLATFORM_Y, PLATFORM_T, MODULE_PITCH - PLATFORM_T, 5.0
    )
    result = result.union(platform).union(_platform_gussets())

    # 1/4"-20 camera bolt adjustment slot (6.8 mm clearance).
    camera_slot = (
        cq.Workplane("XY")
        .workplane(offset=MODULE_PITCH - PLATFORM_T - 0.2)
        .slot2D(38.0, 6.8, 0.0)
        .extrude(PLATFORM_T + 0.4)
    )
    result = result.cut(camera_slot)

    # Two wide strap slots for webcams without a tripod thread.
    for x in (-36.0, 36.0):
        strap_slot = (
            cq.Workplane("XY")
            .workplane(offset=MODULE_PITCH - PLATFORM_T - 0.2)
            .center(x, 0.0)
            .slot2D(28.0, 6.5, 90.0)
            .extrude(PLATFORM_T + 0.4)
        )
        result = result.cut(strap_slot)
    return result


def build_assembly():
    bottom = build_bottom().val()
    middle = build_middle().translate((0.0, 0.0, MODULE_PITCH)).val()
    top = build_top().translate((0.0, 0.0, 2.0 * MODULE_PITCH)).val()
    return cq.Compound.makeCompound([bottom, middle, top])


if PART == "bottom":
    result = build_bottom()
elif PART == "middle":
    result = build_middle()
elif PART == "top":
    result = build_top()
elif PART == "assembly":
    result = build_assembly()
else:
    raise ValueError(f"Unknown PART={PART!r}")

