#!/bin/bash

# Run the value-blind producer census directly on the local M1 Retina Mac.
# Apple Command Line Tools are used exclusively; no Nix store path is native.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly binary=glass-transition-introspect-721293f
readonly capture=Analysis/capture_background_filter_constructor_timeline_marker_census_local_macos_26_6_1_lldb.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly preregistration=Analysis/background_filter_constructor_timeline_marker_census_local_macos_26_6_1_preregistration.json
readonly validator=Analysis/validate_background_filter_constructor_timeline_marker_census_local_macos_26_6_1.py
readonly runner=Analysis/run_background_filter_constructor_timeline_marker_census_local_macos_26_6_1.sh
readonly parent_result=Analysis/backdrop_margin_case22_provider_timeline_marker_retina_transfer_local_macos_26_6_1_result.json
readonly output_directory="local-background-filter-constructor-timeline-marker-census-${run_label}"
readonly trace="$repository/$output_directory/provider-timeline-marker-trace.json"
readonly validation_output="$output_directory/validation.json"
readonly validation_stdout="$output_directory/validation-stdout.log"
readonly validation_stderr="$output_directory/validation-stderr.log"
readonly validation_status_file="$output_directory/validation-exit-status.txt"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly lldb=/Library/Developer/CommandLineTools/usr/bin/lldb
readonly python=/Library/Developer/CommandLineTools/usr/bin/python3

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

require_sha256 "$binary" b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd
require_sha256 "$capture" e6b6656aabddcc240c3d4fa327a4c7114feedaea3c6d02cab9433bfe416be3c3
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1
require_sha256 "$validator" 244e0c73694a5e5e467bc35cc2e07ea35049a2e335a53814edce9ba9164cc72c
require_sha256 "$parent_result" 9ce1e32be073ef9ff0684fe8537d7fd44870f4b6566ac55498a25772bad7bc2e

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

readonly -a common_environment=(
    LG_GEOMETRY_POLICY=0
    LG_GLASS_APPEARANCE=light
    LG_GLASS_GEOMETRY=circle-127-center
    LG_GLASS_MATERIAL=regular
    LG_TRANSITION_ALLOCATION_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_DENSE=1
    LG_TRANSITION_ALLOCATION_FIXED_STATE=0
    LG_TRANSITION_ALLOCATION_MESH_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_ONLY=1
    LG_TRANSITION_ALLOCATION_PATH_ISOLATION=0
    LG_TRANSITION_CONTROLLED_BACKDROP=0
    LG_TRANSITION_DIRECTION=materialize
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
    git rev-parse HEAD
    /usr/bin/shasum -a 256 "$binary"
    /usr/bin/shasum -a 256 "$capture"
    /usr/bin/shasum -a 256 "$preregistration"
    /usr/bin/shasum -a 256 "$preflight"
    /usr/bin/shasum -a 256 "$validator"
    /usr/bin/shasum -a 256 "$runner"
    printf '%s=%s\n' \
        LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT \
        "$trace"
    printf '%s\n' "${common_environment[@]}" | LC_ALL=C sort
} >"$output_directory/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

/usr/bin/env \
    "${common_environment[@]}" \
    LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT="$trace" \
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
    -o "script import capture_background_filter_constructor_timeline_marker_census_local_macos_26_6_1_lldb as census; census.finalize()" \
    -o quit \
    >"$output_directory/lldb.log" 2>&1
lldb_status=$?
printf '%s\n' "$lldb_status" >"$output_directory/lldb-exit-status.txt"

validation_status=125
if [[ "$lldb_status" -eq 0 ]]; then
    "$python" "$validator" \
        --preregistration "$preregistration" \
        --artifact-directory "$output_directory" \
        --repository-root "$repository" \
        --output "$validation_output" \
        >"$validation_stdout" 2>"$validation_stderr"
    validation_status=$?
else
    : >"$validation_stdout"
    printf '%s\n' \
        "validation skipped because the unconditional capture process failed" \
        >"$validation_stderr"
fi
printf '%s\n' "$validation_status" >"$validation_status_file"

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
