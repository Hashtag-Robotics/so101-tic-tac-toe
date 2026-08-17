// Bottom-face preview matching the P2S mast plate placement.
color("#c8c8c8")
    translate([40, 20, 0])
        import("so101_cam_tower_silk_bottom.stl", convexity = 10);

color("#c8c8c8")
    translate([80, 20, 0])
        import("so101_cam_tower_silk_middle.stl", convexity = 10);

color("#c8c8c8")
    translate([120, 20, 0])
        import("so101_cam_tower_silk_bottom_logo_body.stl", convexity = 10);

color("#d02727")
    translate([120, 20, 0])
        import("so101_cam_tower_silk_bottom_logo_red.stl", convexity = 10);
