// Large, camera-legible tic-tac-toe set for two SO-101 arms.
//
// The board is intentionally only the central hashtag: no backing plate, seats,
// tags, text, or colour changes.  Its 240 mm envelope leaves 8 mm per side on a
// Bambu Lab P2S 256 x 256 mm bed.  The 14 mm bars divide that envelope into
// three ~71 mm clear cells. Tokens are 52 mm wide, leaving ~19 mm of placement
// tolerance inside every cell. The lightweight revision uses an 8 mm grasp
// height, square X ends, and a smooth circular O.
//
// Render:
//   openscad -D 'PART="board"' -o out/ttt_p2s_hashtag.stl scad/tictactoe_p2s_large.scad
//   openscad -D 'PART="X"'     -o out/ttt_p2s_X.stl       scad/tictactoe_p2s_large.scad
//   openscad -D 'PART="O"'     -o out/ttt_p2s_O.stl       scad/tictactoe_p2s_large.scad

$fn = 72;

PART = "board";             // board | X | O | set_preview

// P2S: 256 x 256 mm bed.  240 mm keeps an 8 mm model margin on every side;
// the sliced skirt expands the occupied toolpath to 244 mm, leaving 6 mm.
BOARD_SIZE = 240;
BOARD_H = 5;
BAR_W = 14;
BAR_OFFSET = 42;

// Large enough to read cleanly from the overhead camera, still within the
// SO-101 gripper envelope. Reduced height and narrow strokes cut print mass.
TOKEN_SIZE = 52;
TOKEN_H = 8;
X_BAR_W = 10;
O_INNER_D = 38;
O_FACETS = 96;

EPS = 0.01;

// A capsule gives the hashtag rounded ends without pushing beyond BOARD_SIZE.
module capsule_2d(length, width) {
    hull()
        for (x = [-(length - width) / 2, (length - width) / 2])
            translate([x, 0]) circle(d = width);
}

module hashtag_2d() {
    union() {
        for (y = [-BAR_OFFSET, BAR_OFFSET])
            translate([0, y]) capsule_2d(BOARD_SIZE, BAR_W);
        for (x = [-BAR_OFFSET, BAR_OFFSET])
            translate([x, 0]) rotate(90) capsule_2d(BOARD_SIZE, BAR_W);
    }
}

module board() {
    linear_extrude(height = BOARD_H) hashtag_2d();
}

// Two square-ended bars. This length formula keeps the exact X/Y envelope at
// TOKEN_SIZE after the 45-degree rotations.
module x_2d() {
    stroke_len = TOKEN_SIZE * sqrt(2) - X_BAR_W;
    union()
        for (a = [45, -45]) rotate(a) square([stroke_len, X_BAR_W], center = true);
}

module o_2d() {
    difference() {
        circle(d = TOKEN_SIZE, $fn = O_FACETS);
        circle(d = O_INNER_D, $fn = O_FACETS);
    }
}

// A straight, support-free extrusion keeps the entire 8 mm side wall available
// to the gripper. The X has flat ends; the O is a smooth circular ring.
module token(shape = "X") {
    linear_extrude(height = TOKEN_H)
        if (shape == "X") x_2d(); else o_2d();
}

module set_preview() {
    color("#111111") board();
    for (p = [[-84, -84], [0, 0], [84, 84]])
        color("#D02727") translate([p[0], p[1], BOARD_H]) token("X");
    for (p = [[0, -84], [84, 0], [-84, 84]])
        color("#5F6367") translate([p[0], p[1], BOARD_H]) token("O");
}

if      (PART == "board")       board();
else if (PART == "X")           token("X");
else if (PART == "O")           token("O");
else if (PART == "set_preview") set_preview();
else assert(false, str("unknown PART ", PART));

CELL_CLEAR = (BOARD_SIZE - 2 * BAR_W) / 3;
echo(str("board=", BOARD_SIZE, "x", BOARD_SIZE, "x", BOARD_H,
         " bar=", BAR_W, " cell_clear=", CELL_CLEAR,
         " bed_margin=", (256 - BOARD_SIZE) / 2));
echo(str("token=", TOKEN_SIZE, "x", TOKEN_SIZE, "x", TOKEN_H,
         " cell_clearance=", CELL_CLEAR - TOKEN_SIZE));
