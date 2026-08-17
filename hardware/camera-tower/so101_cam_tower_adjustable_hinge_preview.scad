// V4 visual assembly check: original V2 camera cradle on the strengthened
// round M3 tilt head.  No printed PLA-CF fastener and no diamond openings.

ANGLE_DEG = -35;
HINGE_Y = 202;
HINGE_Z = 7;
CAMERA_HINGE_Y = -6;
CAMERA_HINGE_Z = 7;

color("#c8c8c8")
    import("so101_cam_tower_silk_top.stl", convexity = 10);

color("#e0e0e0")
    translate([0, HINGE_Y, HINGE_Z])
        rotate([ANGLE_DEG, 0, 0])
            translate([0, -CAMERA_HINGE_Y, -CAMERA_HINGE_Z])
                import("so101_cam_tower_silk_camera.stl", convexity = 10);

// Schematic metal M3 pivot.  The user's existing M3 x 40 bolt and locknut fit.
color("#30343b")
    translate([-18, HINGE_Y, HINGE_Z])
        rotate([0, 90, 0]) cylinder(h = 36, d = 3, $fn = 32);
