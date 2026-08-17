// Close-up of the V4 top head with the unchanged V2 camera cradle.
ANGLE_DEG = -35;
HINGE_Y = 202;
HINGE_Z = 7;
CAMERA_HINGE_Y = -6;
CAMERA_HINGE_Z = 7;

color("#c8c8c8")
    intersection() {
        import("so101_cam_tower_silk_top.stl", convexity = 10);
        translate([-24, 168, -1]) cube([48, 50, 22]);
    }

color("#eeeeee")
    translate([0, HINGE_Y, HINGE_Z])
        rotate([ANGLE_DEG, 0, 0])
            translate([0, -CAMERA_HINGE_Y, -CAMERA_HINGE_Z])
                import("so101_cam_tower_silk_camera.stl", convexity = 10);

// Metal M3 x 40 pivot shown schematically.
color("#30343b")
    translate([-18, HINGE_Y, HINGE_Z])
        rotate([0, 90, 0]) cylinder(h = 36, d = 3, $fn = 32);
