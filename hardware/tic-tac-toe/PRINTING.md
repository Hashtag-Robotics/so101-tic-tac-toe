# Printing guide

## Bambu Lab P2S validated path

Print the five plates separately with a Textured PEI Plate:

| Plate | Profile | Estimate |
| --- | --- | ---: |
| Board | 0.20 mm, 4 walls, 20% gyroid, monotonic top | 1 h 23 m / ~42 g |
| Six X tokens | 0.24 mm, 2 walls, 3 top/bottom, 8% gyroid | 1 h 52 m / 26.32 g |
| Six O tokens | 0.24 mm, 2 walls, 3 top/bottom, 8% gyroid | 1 h 35 m / 24.88 g |
| Each pickup frame | 0.20 mm, 2 walls, no skirt/brim | 21 m 33 s / 7.44 g |

The board nearly fills the P2S bed, leaving 8 mm at each edge. Clean the plate,
inspect the sliced first layer and do not auto-arrange the supplied 3MF. The
pickup frame spans X=3..253 mm; do not rotate, scale, add a skirt or add a brim
to the supplied machine job.

PLA-CF requires the P2S hardened-steel 0.4 mm nozzle. Do not substitute a 0.2 mm
or stainless-steel nozzle. When moisture is not known-good, dry PLA-CF and PLA
Silk+ according to the material manufacturer's current guidance; the source
validation used 55 °C for 8 hours.

Let the plate cool before removing either 1.2 mm frame so it stays flat.

## Other printers/materials

Do not run the supplied G-code. Import the STL files, confirm millimetres as the
unit, choose settings for your own machine/material and reslice. The minimum
practical bed must accommodate the 240 mm board and 250 mm frame with your
printer's required margins.

Before printing, verify:

- mesh dimensions against `manifest.json`;
- nozzle, plate and material compatibility;
- first-layer clearance and collision-free travel;
- no scale, mirror or axis conversion was introduced;
- the top-camera appearance remains close to the dataset if using the pretrained policy.

The two pickup-frame G-code files intentionally have identical checksums because
the geometry and process are identical; the filenames only label X and O zones.
