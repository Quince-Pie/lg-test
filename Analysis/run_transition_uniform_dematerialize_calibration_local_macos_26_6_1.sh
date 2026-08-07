#!/bin/bash

# Capture one opened four-profile dematerialize numeric-uniform calibration.

set -uo pipefail

if [[ $# -ne 4 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL MATERIAL APPEARANCE GEOMETRY" >&2
    exit 64
fi

readonly run_label=$1
readonly material=$2
readonly appearance=$3
readonly geometry=$4
readonly direction=dematerialize

case "$material:$appearance:$geometry" in
    clear:light:circle-453-center | \
    clear:dark:circle-461-center | \
    regular:light:circle-469-center | \
    regular:dark:circle-477-center) ;;
    *)
        echo "profile is not one dematerialize uniform calibration case" >&2
        exit 64
        ;;
esac

readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly binary=glass-transition-introspect-721293f
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly runner=Analysis/run_transition_uniform_dematerialize_calibration_local_macos_26_6_1.sh
readonly output_directory="local-transition-uniform-dematerialize-calibration-${run_label}"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift

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
if /usr/bin/env | /usr/bin/grep -Fq '/nix/store/'; then
    echo "native capture environment contains a Nix store path" >&2
    exit 1
fi

require_sha256 "$binary" b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1

if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "tracked repository state is dirty" >&2
    exit 1
fi
if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi
/bin/mkdir "$output_directory" || exit 1

while IFS='=' read -r variable _; do
    case "$variable" in
        LG_*) unset "$variable" ;;
    esac
done < <(/usr/bin/env)

readonly -a capture_environment=(
    LG_GEOMETRY_POLICY=0
    LG_GLASS_APPEARANCE="$appearance"
    LG_GLASS_GEOMETRY="$geometry"
    LG_GLASS_MATERIAL="$material"
    LG_TRANSITION_ALLOCATION_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_DENSE=1
    LG_TRANSITION_ALLOCATION_FIXED_STATE=0
    LG_TRANSITION_ALLOCATION_MESH_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_ONLY=1
    LG_TRANSITION_ALLOCATION_PATH_ISOLATION=0
    LG_TRANSITION_CONTROLLED_BACKDROP=0
    LG_TRANSITION_DIRECTION="$direction"
    LG_TRANSITION_HIGHLIGHT_TRACE=0
    LG_TRANSITION_MATRIX_BASIS=0
    LG_TRANSITION_TIMELINE=1
    LG_TRANSITION_UNIFORMS=1
)

"$swift" "$preflight" >"$output_directory/capture-session-preflight.json"
preflight_status=$?
if [[ "$preflight_status" -ne 0 ]]; then
    echo "Retina session preflight failed; no app was launched" >&2
    exit 2
fi

{
    printf 'CAPTURE_COMMIT=%s\n' "$(git rev-parse HEAD)"
    printf '%s\n' NATIVE_CAPTURE_DEBUGGER_USED=0
    printf '%s\n' GITHUB_ACTIONS_USED=0
    /usr/bin/sw_vers
    /usr/bin/uname -m
    /usr/bin/shasum -a 256 "$binary" "$preflight" "$runner"
    printf '%s\n' "${capture_environment[@]}" | LC_ALL=C sort
} >"$output_directory/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

/usr/bin/env "${capture_environment[@]}" \
    "$repository/$binary" "$output_directory" \
    >"$output_directory/runtime-stdout.log" \
    2>"$output_directory/runtime-stderr.log"
native_status=$?
printf '%s\n' "$native_status" >"$output_directory/native-exit-status.txt"

printf 'OUTPUT_DIRECTORY=%s\n' "$output_directory"
printf 'NATIVE_STATUS=%s\n' "$native_status"

if [[ "$native_status" -ne 0 ]]; then
    exit 4
fi
