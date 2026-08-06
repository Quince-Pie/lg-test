#!/bin/bash

# Run the preregistered unlocked-Retina provider experiment directly with
# Apple's Command Line Tools.  Repository validation happens under Nix; the
# Apple process and debugger deliberately do not inherit the Nix environment.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly binary=glass-transition-introspect-721293f
readonly selected_capture=Analysis/capture_backdrop_margin_case22_provider_local_macos_26_6_1_lldb.py
readonly complete_capture=Analysis/capture_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_lldb.py
readonly preflight=Analysis/check_local_retina_capture_session.swift
readonly preregistration=Analysis/backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_preregistration.json
readonly validator=Analysis/validate_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1.py
readonly selected_directory="local-case22-unlocked-selected-${run_label}"
readonly complete_directory="local-case22-unlocked-complete-${run_label}"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly lldb=/Library/Developer/CommandLineTools/usr/bin/lldb

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
require_sha256 "$selected_capture" 964b03394b837e3d0e0f312a56f593ffdbb7be6c325d98a53d56fbc216efd25b
require_sha256 "$complete_capture" 05e12987979401fa79615d86fc119084a5126aeac1ba3b79b44eeaf80988b9b1
require_sha256 "$preflight" 72e259882f0c9cc5f40e7f12d172dbbe2582da729b0ee176647917b07f172981
require_sha256 "$validator" 4911054a462b804246862960f46cd5ec3f4b7f7f8018cdfee0c543cf76821b86

if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "tracked repository state is dirty" >&2
    exit 1
fi
if [[ -e "$selected_directory" || -e "$complete_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi
mkdir "$selected_directory" "$complete_directory" || exit 1

# A fresh SSH process should not contain experiment variables.  Clear any that
# do exist, then pass the complete frozen set explicitly to each LLDB process.
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

write_context() {
    local directory=$1
    local capture=$2
    local trace_name=$3
    local trace_value=$4
    {
        git rev-parse HEAD
        /usr/bin/shasum -a 256 "$binary"
        /usr/bin/shasum -a 256 "$capture"
        /usr/bin/shasum -a 256 "$preregistration"
        /usr/bin/shasum -a 256 "$preflight"
        printf '%s=%s\n' "$trace_name" "$trace_value"
        printf '%s\n' "${common_environment[@]}" | LC_ALL=C sort
    } >"$directory/capture-context.txt"
}

run_preflight() {
    local directory=$1
    "$swift" "$preflight" >"$directory/capture-session-preflight.json"
}

# Keep the already-unlocked display awake only while this runner exists.
/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &

if ! run_preflight "$selected_directory"; then
    echo "selected-stage session preflight failed; no app was launched" >&2
    exit 2
fi

readonly selected_trace="$repository/$selected_directory/backdrop-margin-writer-trace.json"
write_context \
    "$selected_directory" \
    "$selected_capture" \
    LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT \
    "$selected_trace"

/usr/bin/env \
    "${common_environment[@]}" \
    LG_BACKDROP_MARGIN_WRITER_TRACE_OUTPUT="$selected_trace" \
    "$lldb" -b \
    -o "target create $binary" \
    -o "settings set -- target.run-args $selected_directory" \
    -o "settings set target.output-path $selected_directory/runtime-stdout.log" \
    -o "settings set target.error-path $selected_directory/runtime-stderr.log" \
    -o "command script import $selected_capture" \
    -o run \
    -o "script capture_backdrop_margin_case22_provider_local_macos_26_6_1_lldb.trace_selected_case22()" \
    -o continue \
    -o "script capture_backdrop_margin_case22_provider_local_macos_26_6_1_lldb.finalize()" \
    -o quit \
    >"$selected_directory/lldb.log" 2>&1
selected_status=$?
printf '%s\n' "$selected_status" >"$selected_directory/lldb-exit-status.txt"

# The second stage is value-unconditional.  Only the independently required
# session preflight can stop it before app launch.
if ! run_preflight "$complete_directory"; then
    echo "complete-stage session preflight failed; no second app was launched" >&2
    exit 3
fi

readonly complete_trace="$repository/$complete_directory/provider-object-matrix-trace.json"
write_context \
    "$complete_directory" \
    "$complete_capture" \
    LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT \
    "$complete_trace"

/usr/bin/env \
    "${common_environment[@]}" \
    LG_CASE22_PROVIDER_OBJECT_MATRIX_MINIMAL_TRACE_OUTPUT="$complete_trace" \
    "$lldb" -b \
    -o "target create $binary" \
    -o "settings set -- target.run-args $complete_directory" \
    -o "settings set target.output-path $complete_directory/runtime-stdout.log" \
    -o "settings set target.error-path $complete_directory/runtime-stderr.log" \
    -o "command script import $complete_capture" \
    -o run \
    -o "script import capture_backdrop_margin_case22_provider_object_matrix_complete_local_macos_26_6_1_lldb as complete; complete.finalize()" \
    -o quit \
    >"$complete_directory/lldb.log" 2>&1
complete_status=$?
printf '%s\n' "$complete_status" >"$complete_directory/lldb-exit-status.txt"

printf 'SELECTED_DIRECTORY=%s\n' "$selected_directory"
printf 'SELECTED_LLDB_STATUS=%s\n' "$selected_status"
printf 'COMPLETE_DIRECTORY=%s\n' "$complete_directory"
printf 'COMPLETE_LLDB_STATUS=%s\n' "$complete_status"

if [[ "$selected_status" -ne 0 || "$complete_status" -ne 0 ]]; then
    exit 4
fi
