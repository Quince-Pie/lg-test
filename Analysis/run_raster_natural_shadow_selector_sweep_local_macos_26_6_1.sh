#!/usr/bin/env bash
set -euo pipefail

if (( $# != 1 )); then
    echo "usage: $0 OUTPUT_DIRECTORY" >&2
    exit 2
fi

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_root=$(CDPATH= cd -- "$script_directory/.." && pwd)
retina_host=${LG_RETINA_HOST:-quince@10.0.41.19}
output_directory=$1
capture_commit=$(git -C "$repository_root" rev-parse HEAD)

if [[ -n $(git -C "$repository_root" status --porcelain --untracked-files=no) ]]; then
    echo "tracked lg-test files must be committed before capture" >&2
    exit 1
fi
if [[ ! $capture_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "capture commit is not a full SHA-1" >&2
    exit 1
fi

remote_directory=$(
    ssh "$retina_host" mktemp -d /tmp/lg-natural-shadow-selector.XXXXXX
)
if [[ $remote_directory != /tmp/lg-natural-shadow-selector.* ]]; then
    echo "remote temporary directory is outside the expected prefix" >&2
    exit 1
fi

echo "Retina capture commit: $capture_commit" >&2
echo "Retina work directory: $remote_directory" >&2
git -C "$repository_root" archive "$capture_commit" |
    ssh "$retina_host" tar -xf - -C "$remote_directory"

ssh "$retina_host" /bin/bash -s -- "$remote_directory" "$capture_commit" <<'REMOTE'
set -euo pipefail
remote_directory=$1
capture_commit=$2
cd "$remote_directory"
mkdir -p capture
/usr/bin/swiftc -O -parse-as-library \
    -target "$(uname -m)-apple-macos26.0" \
    Sources/GlassRasterNaturalShadowSelectorSweep/main.swift \
    -o "$remote_directory/glass-raster-natural-shadow-selector-sweep"
LG_CAPTURE_COMMIT=$capture_commit \
    "$remote_directory/glass-raster-natural-shadow-selector-sweep" \
    "$remote_directory/capture"
REMOTE

mkdir -p "$output_directory"
rsync -a -- "$retina_host:$remote_directory/capture/" "$output_directory/"

nix develop "$repository_root" -c env \
    PYTHONPATH="$repository_root/Analysis" \
    python3 \
    "$repository_root/Analysis/validate_raster_natural_shadow_selector_sweep.py" \
    "$output_directory" \
    --expected-commit "$capture_commit" \
    --output "$output_directory/validation.json"

echo "Retina evidence retained at $retina_host:$remote_directory" >&2
