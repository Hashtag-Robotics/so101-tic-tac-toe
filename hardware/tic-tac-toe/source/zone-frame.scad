// Thin one-piece field marker for the large SO-101 tic-tac-toe setup.
// Two identical black prints mark the X and O regions.

OUTER_W = 250;
OUTER_H = 200;
BORDER = 6;
THICKNESS = 1.2;

$fn = 48;

module rectangular_frame() {
    linear_extrude(height = THICKNESS)
        difference() {
            square([OUTER_W, OUTER_H], center = true);
            square([
                OUTER_W - 2 * BORDER,
                OUTER_H - 2 * BORDER
            ], center = true);
        }
}

color("#111111") rectangular_frame();
