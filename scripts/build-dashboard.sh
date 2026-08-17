#!/usr/bin/env bash
# Build the dashboard bundle without Node.
#
# `npm run build` is the real build and it is what CI runs. This exists for the
# Jetson Orin, which has no Node at all: without it that board can install the
# control plane but cannot produce a panel for it to serve. esbuild ships a
# native arm64 binary inside node_modules, so bundling works there even though
# nothing else in the toolchain does.
#
# What this does NOT do is type-check: `npm run build` runs `tsc -b` first, and
# there is no way to run tsc without Node. A bundle produced here is therefore
# provisional and belongs on the machine that built it, not in a release --
# `src/hashtag_robotics/web/` is ignored by git for exactly that reason. Note
# also that the two builds do not produce the same filenames: vite emits
# `index-<hash>.{js,css}` where esbuild emits `main-<hash>.{js,css}`.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

esbuild="frontend/node_modules/@esbuild/linux-arm64/bin/esbuild"
if [[ ! -x "$esbuild" ]]; then
  esbuild="$(command -v esbuild || true)"
fi
if [[ -z "$esbuild" || ! -x "$esbuild" ]]; then
  echo "No esbuild binary found. Run 'npm --prefix frontend ci' first." >&2
  exit 1
fi

# esbuild bundles happily around an identifier that was never imported: the
# page then dies at render with a ReferenceError and shows nothing. `tsc` would
# catch it, and `tsc` needs Node. This is the one case common enough on this
# board to be worth catching without it -- an icon used in JSX but missing from
# the lucide import list.
python3 - <<'GUARD'
import re
import sys
from pathlib import Path

source = Path("frontend/src/App.tsx").read_text()
block = re.search(r'import \{(.*?)\} from "lucide-react";', source, re.S)
if block is None:
    raise SystemExit("App.tsx no longer imports from lucide-react")
imported = {
    name.strip().removeprefix("type ").strip()
    for name in block.group(1).split(",")
    if name.strip()
}
used = set(re.findall(r"<([A-Z][A-Za-z0-9]*) size=\{", source))


def bound_locally(name: str) -> bool:
    """Declared in this file rather than imported: a local const, a component,
    or a prop renamed into scope (`icon: Icon`)."""
    return bool(
        re.search(rf"\b(?:const|let|function)\s+{name}\b", source)
        or re.search(rf"\b\w+:\s*{name}\b,", source)
    )


missing = sorted(name for name in used if name not in imported and not bound_locally(name))
if missing:
    print(f"icons used in JSX but never imported: {missing}", file=sys.stderr)
    raise SystemExit(1)
GUARD

out="src/hashtag_robotics/web"
# Stale hashed assets are never overwritten, only orphaned, and an orphan that
# index.html no longer names is invisible until it ships inside the wheel.
rm -rf "$out"
mkdir -p "$out/assets"

"$esbuild" frontend/src/main.tsx \
  --bundle \
  --minify \
  --format=esm \
  --target=es2022 \
  --jsx=automatic \
  --loader:.svg=dataurl \
  --entry-names="[name]-[hash]" \
  --asset-names="[name]-[hash]" \
  --outdir="$out/assets" \
  --define:process.env.NODE_ENV=\"production\"

# The favicon is served from /assets because that is the only directory the
# control plane mounts statically; a file at the root would fall through to the
# SPA handler and come back as index.html.
if [[ -d frontend/public/assets ]]; then
  cp -r frontend/public/assets/. "$out/assets/"
fi

script_name="$(cd "$out/assets" && ls main-*.js)"
style_name="$(cd "$out/assets" && ls main-*.css)"

python3 - "$out" "$script_name" "$style_name" <<'PY'
import re
import sys
from pathlib import Path

out, script, style = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
html = Path("frontend/index.html").read_text()
# Vite rewrites the dev entry into hashed tags; esbuild does not, so the same
# substitution is made here rather than keeping a second copy of index.html.
html = html.replace(
    '<script type="module" src="/src/main.tsx"></script>',
    f'<script type="module" crossorigin src="/assets/{script}"></script>',
)
html = html.replace(
    "</head>",
    f'  <link rel="stylesheet" crossorigin href="/assets/{style}" />\n  </head>',
)
if "/src/main.tsx" in html:
    raise SystemExit("frontend/index.html no longer carries the expected entry tag")
Path(out / "index.html").write_text(html)
missing = [
    reference
    for reference in re.findall(r'(?:src|href)="/assets/([^"]+)"', html)
    if not (out / "assets" / reference).is_file()
]
if missing:
    raise SystemExit(f"index.html references assets that were not built: {missing}")
print(f"dashboard built: {script}, {style}")
PY
