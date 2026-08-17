# Large SO-101 tic-tac-toe set

Three single-colour game plates plus two pickup-zone frames, designed around the
overhead view in the public Hashtag Robotics dataset.

| Part | Quantity | Finished geometry | Recommended file |
| --- | ---: | --- | --- |
| Hashtag board | 1 | 240 × 240 × 5 mm | `3mf/bambu-p2s/ttt_p2s_hashtag_black_pla_cf.3mf` |
| X token | 6 | 52 × 52 × 8 mm | `3mf/bambu-p2s/ttt_p2s_x6_red_silk_plus_lightweight.3mf` |
| O token | 6 | 52 × 52 × 8 mm | `3mf/bambu-p2s/ttt_p2s_o6_gray_silk_plus_lightweight.3mf` |
| X pickup frame | 1 | 250 × 200 × 1.2 mm | `3mf/bambu-p2s/black_x_zone_frame_250x200.3mf` |
| O pickup frame | 1 | 250 × 200 × 1.2 mm | `3mf/bambu-p2s/black_o_zone_frame_250x200.3mf` |

The 14 mm board bars leave approximately 70.7 mm clear cells. A 52 mm token has
about 18.7 mm total XY clearance; cells are deliberately vision-friendly loose
targets, not locating pockets.

Read in this order:

1. [`PRINTING.md`](PRINTING.md)
2. [`BOM.md`](BOM.md)
3. [`ASSEMBLY.md`](ASSEMBLY.md)
4. [`manifest.json`](manifest.json) and [`checksums.sha256`](checksums.sha256)

`source/` is authoritative and editable. `stl/` is printer-neutral geometry.
`3mf/bambu-p2s/` and `gcode/bambu-p2s/` are machine-specific convenience files.
`profiles/` records the process settings, and `renders/` contains slicer previews.

Validated source workflow: Bambu Studio 02.08.00.50, P2S 256 × 256 × 256 mm
build volume. The X/O meshes are manifold and their 3MF plates contain six
objects each. The exact public-release payload is checked by
`scripts/verify_release.py`.
