# Hardware release

This directory contains the manufacturing package used by the SO-101
tic-tac-toe project.

- [`tic-tac-toe`](tic-tac-toe): large board, X/O tokens and pickup-zone frames
- [`camera-tower`](camera-tower): support-free modular 32 × 32 mm USB camera tower
- [`LICENSE`](LICENSE): CERN Open Hardware Licence Version 2 — Permissive
- [`NOTICE`](NOTICE): attribution and trademark boundary

Printer-specific 3MF/G-code is supplied as a convenience, not as a universal
machine profile. Prefer the editable source and STL/STEP files when your printer,
nozzle, plate, material or tolerances differ. Inspect every toolpath in your
slicer before printing.

The mechanical files reproduce parts, not the original arm/camera calibration.
For policy execution, the physical arm bases, board, pickup zones, camera view
and lighting must be validated against the public dataset. Fasten tall parts and
keep them outside the robot sweep.
