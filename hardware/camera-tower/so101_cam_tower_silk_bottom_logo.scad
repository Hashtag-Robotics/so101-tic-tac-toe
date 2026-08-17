// Hashtag Robotics flush inlay for the rightmost mast shown on the print plate.
// Uses the same wordmark geometry and 0.30 mm outline thickening as the
// previously printed SO-101 arm logo.  OUTPUT: body, logo, preview_color,
// or preview_engraved.

// This requested plate-right/ground-nearest module is historically exported
// as "top" by the original CAD source.
PART_STL = "so101_cam_tower_silk_top.stl";
LOGO_SVG = "hashtag_robotics_wordmark.svg";
OUTPUT = "preview_color";

// The mast is 34 x 200 mm in its support-free print orientation.
LOGO_WIDTH = 115;
LOGO_THICKEN = 0.30;
LOGO_CENTER_X = 0;
LOGO_CENTER_Y = 100;

// Two 0.20 mm layers, flush with the broad face that touches the bed.
INLAY_DEPTH = 0.40;
CUT_OVERTRAVEL = 0.05;

module lower_mast() {
    import(PART_STL, convexity = 10);
}

module logo_2d() {
    offset(delta = LOGO_THICKEN)
        resize([LOGO_WIDTH, 0], auto = true)
            import(LOGO_SVG, center = true);
}

module logo_prism(start_z, depth) {
    translate([LOGO_CENTER_X, LOGO_CENTER_Y, start_z])
        rotate([0, 0, 90])
            // The logo sits on the Z=0 exterior face and is viewed from -Z
            // after assembly. Pre-mirror it so the finished face reads normally.
            mirror([1, 0, 0])
                linear_extrude(height = depth, convexity = 10)
                    logo_2d();
}

module logo_cutter() {
    // Overtravel only outside the face; the pocket roof remains exactly at
    // 0.40 mm so the red inlay bonds to the mast on the next layer.
    logo_prism(-CUT_OVERTRAVEL, INLAY_DEPTH + CUT_OVERTRAVEL);
}

module logo_inlay() {
    logo_prism(0, INLAY_DEPTH);
}

module engraved_body() {
    difference() {
        lower_mast();
        logo_cutter();
    }
}

if (OUTPUT == "body") {
    engraved_body();
} else if (OUTPUT == "logo") {
    logo_inlay();
} else if (OUTPUT == "preview_engraved") {
    color("#c8c8c8") engraved_body();
} else {
    color("#c8c8c8") engraved_body();
    color("#d02727") logo_inlay();
}
