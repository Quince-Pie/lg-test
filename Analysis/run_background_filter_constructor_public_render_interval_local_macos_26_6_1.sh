#!/bin/bash

# Run the frozen Parameters/BackgroundFilter/public-render join directly with
# Apple's Command Line Tools. The native process never inherits a Nix path.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly binary=glass-transition-introspect-721293f
readonly capture=Analysis/capture_background_filter_constructor_public_render_interval_local_macos_26_6_1_lldb.py
readonly preflight=Analysis/check_local_retina_capture_session.swift
readonly preregistration=Analysis/background_filter_constructor_public_render_interval_local_macos_26_6_1_preregistration.json
readonly validator=Analysis/validate_background_filter_constructor_public_render_interval_local_macos_26_6_1.py
readonly predecessor_directory=local-case22-provider-public-render-interval-c1bfabd-run1
readonly predecessor_preregistration=Analysis/backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1_preregistration.json
readonly predecessor_validator=Analysis/validate_backdrop_margin_case22_provider_public_render_interval_transfer_local_macos_26_6_1.py
readonly output_directory="local-background-filter-constructor-public-render-interval-${run_label}"
readonly trace="$repository/$output_directory/background-filter-constructor-public-render-interval-trace.json"
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
require_sha256 "$capture" 0a093feabe5f06444a7350b86cb3a4111faa15338a818a48f62d61142ca971e5
require_sha256 "$preflight" 72e259882f0c9cc5f40e7f12d172dbbe2582da729b0ee176647917b07f172981
require_sha256 "$validator" be5d18f66b200d1746c405a70fab19f50a9bc152fbf0f49383d2a77087944293
require_sha256 "$predecessor_validator" ec499088080c2959a00276d9ef00d3da63906af7440e4713c288770a515556c1

if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "tracked repository state is dirty" >&2
    exit 1
fi
if [[ ! -d "$predecessor_directory" ]]; then
    echo "required predecessor artifact is absent" >&2
    exit 2
fi
if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi
mkdir "$output_directory" || exit 1

"$python" "$predecessor_validator" \
    --preregistration "$predecessor_preregistration" \
    --artifact-directory "$predecessor_directory" \
    --output "$output_directory/predecessor-validation.json" \
    >"$output_directory/predecessor-validation-stdout.log" \
    2>"$output_directory/predecessor-validation-stderr.log"
predecessor_status=$?
printf '%s\n' "$predecessor_status" \
    >"$output_directory/predecessor-validation-exit-status.txt"
if [[ "$predecessor_status" -ne 0 ]]; then
    echo "required predecessor validation failed" >&2
    exit 3
fi

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

{
    git rev-parse HEAD
    /usr/bin/shasum -a 256 "$binary"
    /usr/bin/shasum -a 256 "$capture"
    /usr/bin/shasum -a 256 "$preregistration"
    /usr/bin/shasum -a 256 "$preflight"
    /usr/bin/shasum -a 256 "$validator"
    /usr/bin/shasum -a 256 "$0"
    printf '%s=%s\n' \
        LG_BACKGROUND_FILTER_CONSTRUCTOR_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT \
        "$trace"
    printf '%s\n' "${common_environment[@]}" | LC_ALL=C sort
} >"$output_directory/capture-context.txt"

if ! "$swift" "$preflight" \
    >"$output_directory/capture-session-preflight.json"
then
    echo "presentation-session preflight failed; no app was launched" >&2
    exit 2
fi

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

/usr/bin/env \
    "${common_environment[@]}" \
    LG_BACKGROUND_FILTER_CONSTRUCTOR_PUBLIC_RENDER_INTERVAL_TRACE_OUTPUT="$trace" \
    "$lldb" -b \
    -o "target create $binary" \
    -o "settings set -- target.run-args $output_directory" \
    -o "settings set target.output-path $output_directory/runtime-stdout.log" \
    -o "settings set target.error-path $output_directory/runtime-stderr.log" \
    -o "command script import $capture" \
    -o run \
    -o "script import capture_background_filter_constructor_public_render_interval_local_macos_26_6_1_lldb as transfer; transfer.finalize()" \
    -o quit \
    >"$output_directory/lldb.log" 2>&1
lldb_status=$?
printf '%s\n' "$lldb_status" >"$output_directory/lldb-exit-status.txt"

validation_status=125
if [[ "$lldb_status" -eq 0 ]]; then
    "$python" "$validator" \
        --preregistration "$preregistration" \
        --artifact-directory "$output_directory" \
        --output "$validation_output" \
        >"$validation_stdout" 2>"$validation_stderr"
    validation_status=$?
else
    : >"$validation_stdout"
    printf '%s\n' \
        "validation skipped because the LLDB process failed" \
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
