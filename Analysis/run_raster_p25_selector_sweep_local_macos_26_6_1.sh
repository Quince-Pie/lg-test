#!/usr/bin/env bash
set -euo pipefail

if (( $# < 1 || $# > 2 )); then
    echo "usage: $0 OUTPUT_DIRECTORY [CASE_FILE]" >&2
    exit 2
fi

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_root=$(CDPATH= cd -- "$script_directory/.." && pwd)
retina_host=${LG_RETINA_HOST:-quince@10.0.41.19}
output_directory=$1
case_file=${2:-/tmp/walle-p25-cases-v1/cases-u32le.bin}
case_sha256=836faf360db6a9bcdf2beb2f994507afe2ce0276eab3c2d45ae64e6facf8da3e
capture_commit=$(git -C "$repository_root" rev-parse HEAD)

if [[ -n $(git -C "$repository_root" status --porcelain --untracked-files=no) ]]; then
    echo "tracked lg-test files must be committed before capture" >&2
    exit 1
fi
if [[ ! $capture_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "capture commit is not a full SHA-1" >&2
    exit 1
fi
if [[ ! -f $case_file ]]; then
    echo "P25 case file does not exist: $case_file" >&2
    exit 1
fi
actual_case_sha256=$(sha256sum "$case_file" | awk '{print $1}')
if [[ $actual_case_sha256 != "$case_sha256" ]]; then
    echo "P25 case file SHA-256 differs" >&2
    exit 1
fi

remote_directory=$(
    ssh "$retina_host" mktemp -d /tmp/lg-p25-selector.XXXXXX
)
if [[ $remote_directory != /tmp/lg-p25-selector.* ]]; then
    echo "remote temporary directory is outside the expected prefix" >&2
    exit 1
fi

echo "Retina capture commit: $capture_commit" >&2
echo "Retina work directory: $remote_directory" >&2
git -C "$repository_root" archive "$capture_commit" |
    ssh "$retina_host" tar -xf - -C "$remote_directory"
rsync -a --info=progress2 -- "$case_file" \
    "$retina_host:$remote_directory/Analysis/raster_p25_selector_cases_u32le.bin"

ssh "$retina_host" /bin/bash -s -- "$remote_directory" "$capture_commit" <<'REMOTE'
set -euo pipefail
remote_directory=$1
capture_commit=$2
cd "$remote_directory"
mkdir -p capture
/usr/bin/swiftc -O -parse-as-library \
    -target "$(uname -m)-apple-macos26.0" \
    Sources/GlassRasterP25SelectorSweep/main.swift \
    -o "$remote_directory/glass-raster-p25-selector-sweep"
if /usr/bin/otool -L "$remote_directory/glass-raster-p25-selector-sweep" |
    /usr/bin/grep -q /nix/store; then
    echo "native capture binary contains a Nix store dependency" >&2
    exit 1
fi
LG_CAPTURE_COMMIT=$capture_commit \
    "$remote_directory/glass-raster-p25-selector-sweep" \
    "$remote_directory/capture"
REMOTE

mkdir -p "$output_directory"
rsync -a --info=progress2 -- \
    "$retina_host:$remote_directory/capture/" "$output_directory/"

nix develop "$repository_root" -c env \
    PYTHONPATH="$repository_root/Analysis" \
    python3 \
    "$repository_root/Analysis/validate_raster_p25_selector_sweep.py" \
    "$output_directory" \
    --cases "$case_file" \
    --expected-commit "$capture_commit" \
    --output "$output_directory/validation.json"

echo "Retina evidence retained at $retina_host:$remote_directory" >&2
