#!/bin/bash

# Re-run opened circle-485 evidence through the live arithmetic overlay.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly binary=glass-transition-introspect-721293f
readonly capture=Analysis/capture_prepare_layer_live_crop_arithmetic_local_macos_26_6_1_lldb.py
readonly live_capture=Analysis/capture_prepare_layer_crop_policy_holdout_live_local_macos_26_6_1_lldb.py
readonly arithmetic=Analysis/prepare_layer_live_crop_arithmetic_local_macos_26_6_1.py
readonly validator=Analysis/validate_prepare_layer_live_crop_replay_v2_local_macos_26_6_1.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly output_directory="local-prepare-layer-live-crop-replay-v2-calibration-${run_label}"
readonly trace="$repository/$output_directory/prepare-layer-crop-policy-holdout-trace.json"
readonly timeline="$repository/$output_directory/transition-timeline.json"
readonly validation_output="$output_directory/validation.json"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly lldb=/Library/Developer/CommandLineTools/usr/bin/lldb
readonly nix=/nix/var/nix/profiles/default/bin/nix

cd "$repository" || exit 1

require_sha256() {
    local path=$1
    local expected=$2
    local observed
    observed=$(/usr/bin/shasum -a 256 "$path") || exit 1
    observed=${observed%% *}
    if [[ "$observed" != "$expected" ]]; then
        echo "SHA-256 differs for $path" >&2
        exit 1
    fi
}

if [[ $(/usr/bin/uname -m) != arm64 ]]; then
    echo "capture host is not Apple silicon" >&2
    exit 1
fi
if [[ $(/usr/bin/sw_vers -productVersion) != 26.6.1 ]] || \
    [[ $(/usr/bin/sw_vers -buildVersion) != 25G76 ]]; then
    echo "capture host is not the mapped macOS 26.6.1 build 25G76" >&2
    exit 1
fi
if [[ ! -x "$nix" ]]; then
    echo "Nix profile command is unavailable" >&2
    exit 1
fi
if /usr/bin/env | /usr/bin/grep -Fq '/nix/store/'; then
    echo "native capture environment contains a Nix store path" >&2
    exit 1
fi

require_sha256 "$binary" b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd
require_sha256 "$capture" 8808e92fe27a7d1c99ad1451dfbcd29674bd1ed1081218bdc2d13b7d29f0de60
require_sha256 "$live_capture" 7166b30cc047bc21c5db77ebc5e5c92d8dcdc5e23d3833b32c8a40b3dbba7820
require_sha256 "$arithmetic" 67db83b0ccb3c83a2555ab9932631fd1c771ce3acf9d70c253ec806d2516f04e
require_sha256 "$validator" 0f742ac9071ff552680d7a4661cfe2abe55e663a5cfd315ba0414824d26ffb98
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1

if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "tracked repository state is dirty" >&2
    exit 1
fi
if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi
mkdir "$output_directory" || exit 1

while IFS='=' read -r variable _; do
    case "$variable" in
        LG_*) unset "$variable" ;;
    esac
done < <(/usr/bin/env)

readonly -a capture_environment=(
    LG_GLASS_MATERIAL=regular
    LG_GLASS_APPEARANCE=dark
    LG_GLASS_GEOMETRY=circle-485-center
    LG_TRANSITION_TIMELINE=1
    LG_TRANSITION_DIRECTION=materialize
    LG_TRANSITION_UNIFORMS=1
    LG_TRANSITION_CONTROLLED_BACKDROP=0
    LG_TRANSITION_ALLOCATION_ONLY=1
    LG_TRANSITION_ALLOCATION_DENSE=1
    LG_TRANSITION_ALLOCATION_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_MESH_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_FIXED_STATE=0
    LG_TRANSITION_ALLOCATION_PATH_ISOLATION=0
    LG_TRANSITION_HIGHLIGHT_TRACE=0
    LG_TRANSITION_MATRIX_BASIS=0
    LG_PREPARE_LAYER_CROP_TRANSFER_TRACE_OUTPUT="$trace"
)

"$swift" "$preflight" >"$output_directory/capture-session-preflight.json"
preflight_status=$?
if [[ "$preflight_status" -ne 0 ]]; then
    echo "Retina session preflight failed; no app was launched" >&2
    exit 2
fi

{
    git rev-parse HEAD
    /usr/bin/sw_vers
    /usr/bin/shasum -a 256 \
        "$binary" "$capture" "$live_capture" "$arithmetic" \
        "$validator" "$preflight"
    printf '%s\n' "${capture_environment[@]}" | LC_ALL=C sort
} >"$output_directory/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

/usr/bin/env "${capture_environment[@]}" \
    "$lldb" -b \
    -o "target create $binary" \
    -o "settings set -- target.run-args $output_directory" \
    -o "settings set target.output-path $output_directory/runtime-stdout.log" \
    -o "settings set target.error-path $output_directory/runtime-stderr.log" \
    -o "breakpoint set --shlib $binary --name main" \
    -o run \
    -o "breakpoint delete --force" \
    -o "command script import $capture" \
    -o continue \
    -o "script import capture_prepare_layer_live_crop_arithmetic_local_macos_26_6_1_lldb as crop_capture; crop_capture.finalize()" \
    -o quit \
    >"$output_directory/lldb.log" 2>&1
lldb_status=$?
printf '%s\n' "$lldb_status" >"$output_directory/lldb-exit-status.txt"

validation_status=125
if [[ "$lldb_status" -eq 0 ]]; then
    "$nix" --extra-experimental-features "nix-command flakes" \
        develop --command python "$validator" \
        "$trace" \
        "$timeline" \
        --expected-geometry circle-485-center \
        --expected-material regular \
        --expected-appearance dark \
        --expected-direction materialize \
        --output "$validation_output" \
        >"$output_directory/validation-stdout.log" \
        2>"$output_directory/validation-stderr.log"
    validation_status=$?
else
    : >"$output_directory/validation-stdout.log"
    printf '%s\n' \
        "validation skipped because the native capture failed" \
        >"$output_directory/validation-stderr.log"
fi
printf '%s\n' "$validation_status" >"$output_directory/validation-exit-status.txt"

printf 'OUTPUT_DIRECTORY=%s\n' "$output_directory"
printf 'LLDB_STATUS=%s\n' "$lldb_status"
printf 'VALIDATION_OUTPUT=%s\n' "$validation_output"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$lldb_status" -ne 0 ]]; then
    exit 4
fi
if [[ "$validation_status" -ne 0 ]]; then
    exit 5
fi
