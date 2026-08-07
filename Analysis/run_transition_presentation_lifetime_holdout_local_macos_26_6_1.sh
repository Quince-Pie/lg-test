#!/bin/bash

# Run one frozen observer-independent presentation-lifetime case on the Retina M1.

set -uo pipefail

if [[ $# -ne 5 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL MATERIAL APPEARANCE DIRECTION GEOMETRY" >&2
    exit 64
fi

readonly run_label=$1
readonly material=$2
readonly appearance=$3
readonly direction=$4
readonly geometry=$5

case "$material:$appearance:$direction:$geometry" in
    clear:light:materialize:circle-452-center | \
    clear:light:dematerialize:circle-453-center | \
    clear:dark:materialize:circle-460-center | \
    clear:dark:dematerialize:circle-461-center | \
    regular:light:materialize:circle-468-center | \
    regular:light:dematerialize:circle-469-center | \
    regular:dark:materialize:circle-476-center | \
    regular:dark:dematerialize:circle-477-center) ;;
    *)
        echo "profile is not one frozen presentation-lifetime case" >&2
        exit 64
        ;;
esac

readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly binary=glass-transition-introspect-721293f
readonly validator=Analysis/validate_transition_presentation_lifetime_holdout.py
readonly preregistration=Analysis/transition_presentation_lifetime_holdout_preregistration.json
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly output_directory="local-transition-presentation-lifetime-${run_label}"
readonly timeline="$repository/$output_directory/transition-timeline.json"
readonly validation_output="$output_directory/validation.json"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
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
require_sha256 "$validator" d980712c71f7d2c9cf2cd72fc773c6c9e3900efca87b01e8dfd4991d5edb2881
require_sha256 "$preregistration" 4fe4c55fa02582c4c1b5b76f08a05415d1dca8a8c16fd9208d4619eecc373f55
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
    LG_TRANSITION_ALLOCATION_DENSE=0
    LG_TRANSITION_ALLOCATION_FIXED_STATE=0
    LG_TRANSITION_ALLOCATION_MESH_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_ONLY=0
    LG_TRANSITION_ALLOCATION_PATH_ISOLATION=0
    LG_TRANSITION_CONTROLLED_BACKDROP=0
    LG_TRANSITION_DIRECTION="$direction"
    LG_TRANSITION_HIGHLIGHT_TRACE=0
    LG_TRANSITION_MATRIX_BASIS=0
    LG_TRANSITION_TIMELINE=1
    LG_TRANSITION_UNIFORMS=0
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
    /usr/bin/sw_vers
    /usr/bin/uname -m
    /usr/bin/shasum -a 256 \
        "$binary" "$validator" "$preregistration" "$preflight"
    printf '%s\n' "${capture_environment[@]}" | LC_ALL=C sort
} >"$output_directory/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

/usr/bin/env "${capture_environment[@]}" \
    "$repository/$binary" "$output_directory" \
    >"$output_directory/runtime-stdout.log" \
    2>"$output_directory/runtime-stderr.log"
native_status=$?
printf '%s\n' "$native_status" >"$output_directory/native-exit-status.txt"

validation_status=125
if [[ "$native_status" -eq 0 ]]; then
    "$nix" --extra-experimental-features "nix-command flakes" \
        develop --command python "$validator" \
        "$timeline" \
        "$preregistration" \
        --material "$material" \
        --appearance "$appearance" \
        --direction "$direction" \
        --geometry "$geometry" \
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
printf 'NATIVE_STATUS=%s\n' "$native_status"
printf 'VALIDATION_OUTPUT=%s\n' "$validation_output"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$native_status" -ne 0 ]]; then
    exit 4
fi
if [[ "$validation_status" -ne 0 ]]; then
    exit 5
fi
