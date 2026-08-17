# Contributing

Keep changes scoped to the existing architecture and preserve the separation
between LLM judgment and deterministic execution. New physical workflows must
default to no motion and include explicit resource ownership, units, dimensions,
joint limits, calibration, timeout, teardown, approval, telemetry and E-STOP
behavior.

Before opening a pull request:

```bash
uv run python scripts/verify_release.py
bash scripts/verify.sh
```

Do not commit `.env`, `.local-data`, calibration, device IDs, credentials,
datasets, model weights or diagnostic archives. For hardware changes, include
editable source, neutral STL/STEP where applicable, printer-specific files only
when clearly labeled, dimensions, BOM, assembly notes, checksums and the hardware
license notice. State exactly what was physically printed or tested.
