#!/bin/bash

# Run a frozen writer/provider composition case on the active physical Retina M1.

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
    clear:light:circle-451-center | \
    clear:dark:circle-459-center | \
    regular:light:circle-467-center | \
    regular:dark:circle-475-center) ;;
    *)
        echo "profile is not one of the four frozen cases" >&2
        exit 64
        ;;
esac

readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly capture=Analysis/capture_backdrop_margin_writer_provider_composition_lldb.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly preregistration=Analysis/backdrop_margin_writer_provider_composition_local_macos_26_6_1_preregistration.json
readonly validator=Analysis/validate_backdrop_margin_writer_provider_composition_local_macos_26_6_1.py
readonly runner=Analysis/run_backdrop_margin_writer_provider_composition_local_macos_26_6_1.sh
readonly output_directory="local-backdrop-margin-provider-composition-${run_label}"
readonly trace="$repository/$output_directory/backdrop-margin-writer-trace.json"
readonly binary="$repository/glass-transition-introspect-721293f"
readonly validation="$repository/$output_directory/validation.json"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly lldb=/Library/Developer/CommandLineTools/usr/bin/lldb
readonly python=/Library/Developer/CommandLineTools/usr/bin/python3

cd "$repository" || exit 1

if [[ $(/usr/bin/uname -m) != arm64 ]]; then
    echo "the frozen native host architecture is arm64" >&2
    exit 1
fi
if [[ $(/usr/bin/sw_vers -productVersion) != 26.6.1 ]]; then
    echo "the frozen native host version is macOS 26.6.1" >&2
    exit 1
fi
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "tracked repository state is dirty" >&2
    exit 1
fi
if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi
if [[ $(/usr/bin/shasum -a 256 "$binary" | /usr/bin/awk '{print $1}') != \
    b9cb4068e77a61ff87794fa20a5c273e007f3ee20dd74503b1ab78839104e8dd ]]; then
    echo "the frozen stable presentation binary differs" >&2
    exit 1
fi
/bin/mkdir "$output_directory" || exit 1

while IFS='=' read -r variable _; do
    case "$variable" in
        LG_*) unset "$variable" ;;
    esac
done < <(/usr/bin/env)

readonly -a common_environment=(
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
    git rev-parse HEAD
    /usr/bin/sw_vers
    /usr/bin/uname -m
    /usr/bin/shasum -a 256 "$binary"
    /usr/bin/shasum -a 256 "$capture"
    /usr/bin/shasum -a 256 "$preflight"
    /usr/bin/shasum -a 256 "$preregistration"
    /usr/bin/shasum -a 256 "$validator"
    /usr/bin/shasum -a 256 "$runner"
    printf '%s=%s\n' LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT "$trace"
    printf '%s\n' "${common_environment[@]}" | LC_ALL=C sort
} >"$output_directory/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

/usr/bin/env \
    "${common_environment[@]}" \
    LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT="$trace" \
    "$lldb" --batch \
    -o "settings set target.output-path $output_directory/runtime-stdout.log" \
    -o "settings set target.error-path $output_directory/runtime-stderr.log" \
    -o "command script import $capture" \
    -o run \
    -o "script import capture_backdrop_margin_writer_provider_composition_lldb as capture; capture.finalize()" \
    -- "$binary" "$output_directory" \
    >"$output_directory/lldb.log" 2>&1
lldb_status=$?
printf '%s\n' "$lldb_status" >"$output_directory/lldb-exit-status.txt"

validation_status=125
if [[ "$lldb_status" -eq 0 ]]; then
    "$python" "$validator" \
        "$trace" \
        "$output_directory/transition-timeline.json" \
        "$preregistration" \
        --material "$material" \
        --appearance "$appearance" \
        --direction "$direction" \
        --geometry "$geometry" \
        --output "$validation" \
        >"$output_directory/validation-stdout.log" \
        2>"$output_directory/validation-stderr.log"
    validation_status=$?
else
    : >"$output_directory/validation-stdout.log"
    printf '%s\n' \
        "validation skipped because the unconditional capture process failed" \
        >"$output_directory/validation-stderr.log"
fi
printf '%s\n' "$validation_status" >"$output_directory/validation-exit-status.txt"

printf 'OUTPUT_DIRECTORY=%s\n' "$output_directory"
printf 'LLDB_STATUS=%s\n' "$lldb_status"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$lldb_status" -ne 0 ]]; then
    exit 4
fi
if [[ "$validation_status" -ne 0 ]]; then
    exit 5
fi
