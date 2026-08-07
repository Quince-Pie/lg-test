#!/bin/bash

# Run one corrected v2 materialize uniform holdout on the direct Retina Mac.

set -uo pipefail

if [[ $# -ne 4 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL MATERIAL APPEARANCE GEOMETRY" >&2
    exit 64
fi

readonly run_label=$1
readonly material=$2
readonly appearance=$3
readonly geometry=$4
readonly direction=materialize

case "$material:$appearance:$geometry" in
    clear:light:circle-455-center)
        readonly case_name=clear-light-circle455
        ;;
    clear:dark:circle-463-center)
        readonly case_name=clear-dark-circle463
        ;;
    regular:light:circle-471-center)
        readonly case_name=regular-light-circle471
        ;;
    regular:dark:circle-479-center)
        readonly case_name=regular-dark-circle479
        ;;
    *)
        echo "profile is not one frozen v2 uniform holdout case" >&2
        exit 64
        ;;
esac

readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly binary=glass-transition-introspect-721293f
readonly model=Analysis/analyze_transition_uniform_profile_calibration.py
readonly native_clamp=Analysis/analyze_transition_uniform_profile_clamp_v2_local_macos_26_6_1.swift
readonly calibration=Analysis/transition_uniform_profile_calibration_result.json
readonly failure=Analysis/transition_uniform_profile_06150f0_v1_aggregate_failure_result.json
readonly validator=Analysis/validate_transition_uniform_profile_holdout_v2.py
readonly preregistration=Analysis/transition_uniform_profile_holdout_v2_preregistration.json
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly output_directory="local-transition-uniform-profile-v2-${run_label}"
readonly timeline="$repository/$output_directory/transition-timeline.json"
readonly clamp_result="$repository/$output_directory/native-clamp-validation.json"
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
require_sha256 "$model" 0fe38fbe4a55689af2157524545698bad021b39f3da830cbd86f6540c0370c5b
require_sha256 "$native_clamp" f6ed214aa7dbcaec0ea4eeebe8aed2924ac1c0802a38793bec68eca9c828d59d
require_sha256 "$calibration" 3f3c9e657378e528653bd8c255fe7ac8bb632331a0bfe8a6a39ab870045a77d5
require_sha256 "$failure" 2b4144cf91b30db7adf42eef9faed72ab2eec94d735b925073d818a9439e78a8
require_sha256 "$validator" 9ae228495af7706a5be6e4c83e2c2f5df532aa4c294529c6f99109809ccfc495
require_sha256 "$preregistration" 8855771447b257ffbcde01334b3a243e09cf689427a559870ebe69b20245e875
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
    /usr/bin/sw_vers
    /usr/bin/uname -m
    /usr/bin/shasum -a 256 \
        "$binary" "$model" "$native_clamp" "$calibration" "$failure" \
        "$validator" "$preregistration" "$preflight"
    printf '%s\n' "${capture_environment[@]}" | LC_ALL=C sort
} >"$output_directory/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

/usr/bin/env "${capture_environment[@]}" \
    "$repository/$binary" "$output_directory" \
    >"$output_directory/runtime-stdout.log" \
    2>"$output_directory/runtime-stderr.log"
native_status=$?
printf '%s\n' "$native_status" >"$output_directory/native-exit-status.txt"

clamp_status=125
validation_status=125
if [[ "$native_status" -eq 0 ]]; then
    "$swift" "$native_clamp" \
        --case "$case_name=$timeline" \
        --output "$clamp_result" \
        >"$output_directory/native-clamp-stdout.log" \
        2>"$output_directory/native-clamp-stderr.log"
    clamp_status=$?
else
    : >"$output_directory/native-clamp-stdout.log"
    printf '%s\n' \
        "native clamp validation skipped because capture failed" \
        >"$output_directory/native-clamp-stderr.log"
fi
printf '%s\n' "$clamp_status" >"$output_directory/native-clamp-exit-status.txt"

if [[ "$clamp_status" -eq 0 ]]; then
    "$nix" --extra-experimental-features "nix-command flakes" \
        develop --command python "$validator" \
        "$timeline" \
        "$preregistration" \
        "$clamp_result" \
        --material "$material" \
        --appearance "$appearance" \
        --geometry "$geometry" \
        --output "$validation_output" \
        >"$output_directory/validation-stdout.log" \
        2>"$output_directory/validation-stderr.log"
    validation_status=$?
else
    : >"$output_directory/validation-stdout.log"
    printf '%s\n' \
        "validation skipped because native clamp validation failed" \
        >"$output_directory/validation-stderr.log"
fi
printf '%s\n' "$validation_status" >"$output_directory/validation-exit-status.txt"

printf 'OUTPUT_DIRECTORY=%s\n' "$output_directory"
printf 'NATIVE_STATUS=%s\n' "$native_status"
printf 'CLAMP_STATUS=%s\n' "$clamp_status"
printf 'VALIDATION_OUTPUT=%s\n' "$validation_output"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$native_status" -ne 0 ]]; then
    exit 4
fi
if [[ "$clamp_status" -ne 0 ]]; then
    exit 5
fi
if [[ "$validation_status" -ne 0 ]]; then
    exit 6
fi
