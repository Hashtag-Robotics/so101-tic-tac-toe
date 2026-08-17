# SO-101 32 × 32 mm camera tower — adjustable V4

This support-free modular tower places a 32 × 32 mm USB camera at a nominal
600 mm height using three 200 mm mast modules. Remove the middle module for an
approximately 400 mm configuration. V4 keeps the original V2 camera cradle and
adds a reinforced adjustable head to the logo mast.

## Print files

If you already printed the V2 camera cradle, print only:

- `so101_cam_tower_silk_v4_tilt_head_upgrade_ams_p2s.3mf` — new logo top mast;
  filament 1 is the main PLA Silk+ and filament 2 is red PLA Silk+.

`so101_cam_tower_silk_hinge_upgrade_ams_p2s.3mf` is a compatibility alias for
the same upgrade plate. Do not reprint the existing cradle, base, bottom or
middle sections. The large printed V3 bolt/nut design is retained only under
`deprecated-v3-threaded-hinge/` and should not be used.

For a complete new tower:

- `so101_cam_tower_silk_mast_logo_ams_p2s.3mf` — three mast pieces; the rightmost
  top piece has the red Hashtag Robotics inlay.
- `so101_cam_tower_silk_base_camera_plate.3mf` — base and unchanged V2 cradle.
- `so101_cam_tower_silk_mast_plate.3mf` — three mast pieces without the logo.

Neutral CAD exports include individual STL/STEP parts and
`so101_cam_tower_silk_assembly.step`. The parametric source is
`so101_cam_tower_silk.py`. `legacy-v1/` and `deprecated-v3-threaded-hinge/` are
historical references, not the current build.

## Camera and hinge contract

- Camera PCB: 32 × 32 mm
- PCB hole centres: 28 × 28 mm
- Printed PCB hole: 2.4 mm
- Lens opening: 18 mm
- Pivot: circular 3.4 mm hole
- Hinge fastener: one metal M3 × 40 mm bolt and M3 nyloc nut

Place the PCB on the four standoffs with the lens centred in the opening, secure
it with four M2 × 8–10 mm fasteners, then place the cradle ears around the mast
head and insert the M3 × 40 mm hinge bolt. Tighten only enough to hold the view;
do not whiten/crack the PLA ears or transfer force to the PCB.

CAD collision checks passed from -90° to +90° in 5° increments. Stay within
approximately ±70° in use so the USB cable is not loaded.

## Tower assembly

1. Seat `bottom` in the 34 × 14 mm base socket; lock with M3 × 50 mm.
2. Join `bottom` to `middle`; lock with M3 × 40 mm.
3. Join `middle` to `top`; lock with a second M3 × 40 mm.
4. Attach the camera cradle with the third M3 × 40 mm bolt.
5. Fasten the base with four M5 screws or two rigid table clamps.
6. Route the USB cable down the open rear channel with loose strain relief.

At 600 mm, never use the tower without the mast bolts and table fastening. The
complete hardware list is in [`BOM.csv`](BOM.csv).

## Validated PLA Silk+ profile

- 0.4 mm nozzle, 0.20 mm layer height
- 3 walls, 4 top/bottom layers, 15% gyroid
- supports off, brim off
- preserve the 3MF orientation; broad faces sit at Z=0

P2S slicer results:

- V4 logo top mast: approximately 38.40 g / 1 h 13 m
- Three-piece logo mast plate: approximately 120.40 g / 3 h 23 m
- Base plus V2 cradle: approximately 52.17 g / 1 h 36 m
- All checked plates: support off, no slicer warning, manifold geometry

## Safety

- The base is not freestanding; bolt or clamp it to the workbench.
- Keep the tower and cable outside the SO-101 motion envelope.
- Set the first camera angle and framing with robot torque disabled.
- Replace any hinge ear that shows a crack, whitening or layer separation.
- Re-check framing whenever the tower height, angle, table or arm base changes.
