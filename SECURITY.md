# Security and physical safety

## Reporting

Do not publish a live credential, private dataset sample, device identifier or
unredacted diagnostic archive in a GitHub issue. Revoke an exposed credential
first. Use GitHub's private vulnerability reporting/security-advisory channel
when available; otherwise open a minimal issue that contains no exploit detail
or secret so a private contact path can be established.

Include the affected revision, operating system, whether physical adapters were
enabled and a redacted reproduction. Never attach `.env`, `.local-data`, robot
calibration files or raw terminal history.

## Trust boundaries

- The web control plane is local-first and should remain bound to loopback.
- LLM output is advisory until deterministic schemas, roles, leases, limits and
  approval gates accept it.
- Client-supplied policy paths are not trusted; policies resolve to pinned,
  server-owned Hugging Face snapshots.
- Secrets belong in an OS secret store or process environment, never source,
  JSON profiles, notebooks or logs.
- `HASHTAG_ENABLE_PHYSICAL=true` is only one gate. It does not replace per-run
  opt-in, calibration checks, operator approval or a physical E-STOP.

## Robot incident response

If motion is unsafe, use the physical power cut/E-STOP first. Software stop,
Ctrl-C and dashboard controls are secondary. Do not reach into the arm sweep.
After an incident, keep logs and the exact artifact revisions, inspect mounting,
gearing, calibration and cables with torque disabled, and do not resume from the
failed state without a fresh preflight.
