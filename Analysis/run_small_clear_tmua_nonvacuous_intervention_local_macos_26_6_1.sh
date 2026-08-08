#!/bin/bash

# Execute the finite-source-control Tmua/Tghn gate on the Retina M1.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly preregistration=Analysis/small_clear_tmua_nonvacuous_v3_preregistration.json
readonly validator=Analysis/validate_small_clear_tmua_nonvacuous_v3.py
readonly validator_test=Analysis/test_validate_small_clear_tmua_nonvacuous_v3.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly probe=Sources/GlassIntrospect/main.swift
readonly output_directory="local-small-clear-tmua-nonvacuous-v3-${run_label}"
readonly case_directory="$output_directory/clear-light-materialize-01"
readonly validation_output="$output_directory/validation.json"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly swiftc=/Library/Developer/CommandLineTools/usr/bin/swiftc
readonly clang=/usr/bin/xcrun
readonly vtool=/Library/Developer/CommandLineTools/usr/bin/vtool
readonly codesign=/usr/bin/codesign
readonly macos_sdk=$(/usr/bin/xcrun --show-sdk-path)
readonly macos_sdk_version=$(/usr/bin/xcrun --show-sdk-version)
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
    echo "capture host is not macOS 26.6.1 build 25G76" >&2
    exit 1
fi
if [[ ! -x "$nix" ]]; then
    echo "Nix profile command is unavailable" >&2
    exit 1
fi
if [[ "$macos_sdk_version" != 26.5 ]]; then
    echo "native capture SDK is not macOS 26.5" >&2
    exit 1
fi
if /usr/bin/env | /usr/bin/grep -Fq '/nix/store/'; then
    echo "native capture environment contains a Nix store path" >&2
    exit 1
fi

require_sha256 "$probe" 2d11eaf955feece023111a6056555da9e1777f54d1617b60b9a79e81d29c0f32
require_sha256 "$validator" 54e69a2906693a59ab0792901d720bc02ea3ad3986f74d33dcf9ac68c10c9bb0
require_sha256 "$validator_test" 1e05589ce132be4c3669ac675bff7056a1ab6cec85e81468a043821d44226410
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1
require_sha256 "$preregistration" 50498266d289b50f2537a2c0cf61922f8563099167698e9122ed7db6f12c9de9
require_sha256 Sources/GlassIntrospect/MatrixBridge.c 841b30cc127582b6819ec997b99d360c9d3fc19e6bfc26cf718d402c78275057
require_sha256 Sources/GlassIntrospect/MatrixBridge.h a7dd8dd8978dffa1b42764b19868dc5b305caa2fea4b3ab171329d15f6e91d0c
require_sha256 Sources/GlassIntrospect/HalfBlendProbe.swift 6cadb5f286d9f97d80f40a1a8b82c2487fe660f4f2614ec0b44458f396ccb263
require_sha256 Sources/GlassIntrospect/HalfDotProbe.swift f27844610b4c051cd99ac474e48c05b7d40240782573d8040819411e7eadd1f0
require_sha256 Sources/GlassIntrospect/HalfIntrinsicProbe.swift ae8c28a4dbbf440c79adce3d63586b2a5087a181329414a00ff557115e280a41
require_sha256 Sources/GlassIntrospect/SDFStageProbe.swift 12d300f75ae875366e850c02d63ceadee72b3ee4f155e4a65f4b0585514b0208

tracked_status=$(git status --short --untracked-files=no)
if [[ -n "$tracked_status" ]]; then
    echo "capture checkout has tracked modifications" >&2
    exit 1
fi
if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi

readonly build_directory=$(/usr/bin/mktemp -d -t lg-small-tmua-nonvacuous)
if [[ ! "$build_directory" =~ ^/var/folders/.+/T/lg-small-tmua-nonvacuous\..+$ ]]; then
    echo "unexpected temporary build directory" >&2
    exit 1
fi
cleanup() {
    /bin/rm -rf "$build_directory"
}
trap cleanup EXIT

/bin/mkdir -p "$case_directory"
"$nix" --extra-experimental-features "nix-command flakes" \
    develop --command env PYTHONPATH=Analysis python -m unittest \
        "$validator_test" \
    >"$output_directory/validator-test-stdout.log" \
    2>"$output_directory/validator-test-stderr.log"
validator_test_status=$?
printf '%s\n' "$validator_test_status" \
    >"$output_directory/validator-test-exit-status.txt"
if [[ "$validator_test_status" -ne 0 ]]; then
    echo "frozen validator tests failed; no app was launched" >&2
    exit 2
fi

"$swift" "$preflight" >"$output_directory/capture-session-preflight.json"
preflight_status=$?
if [[ "$preflight_status" -ne 0 ]]; then
    echo "Retina session preflight failed; no app was launched" >&2
    exit 2
fi

"$clang" clang \
    -std=c23 \
    -O2 \
    -Wall \
    -Wextra \
    -Werror \
    -target arm64-apple-macosx26.0 \
    -c Sources/GlassIntrospect/MatrixBridge.c \
    -o "$build_directory/MatrixBridge.o" \
    >"$output_directory/clang-stdout.log" \
    2>"$output_directory/clang-stderr.log"
clang_status=$?
if [[ "$clang_status" -ne 0 ]]; then
    echo "native C bridge build failed" >&2
    exit 3
fi

"$swiftc" -O -parse-as-library \
    -sdk "$macos_sdk" \
    -target arm64-apple-macosx26.0 \
    -import-objc-header Sources/GlassIntrospect/MatrixBridge.h \
    Sources/GlassIntrospect/HalfBlendProbe.swift \
    Sources/GlassIntrospect/HalfDotProbe.swift \
    Sources/GlassIntrospect/HalfIntrinsicProbe.swift \
    Sources/GlassIntrospect/SDFStageProbe.swift \
    Sources/GlassIntrospect/main.swift \
    "$build_directory/MatrixBridge.o" \
    -o "$build_directory/glassintrospect-unlinked" \
    >"$output_directory/swiftc-stdout.log" \
    2>"$output_directory/swiftc-stderr.log"
swiftc_status=$?
if [[ "$swiftc_status" -ne 0 ]]; then
    echo "native Swift probe build failed" >&2
    exit 3
fi

"$vtool" \
    -set-build-version macos 26.0 26.5 \
    -replace \
    -output "$build_directory/glassintrospect" \
    "$build_directory/glassintrospect-unlinked" \
    >"$output_directory/vtool-stdout.log" \
    2>"$output_directory/vtool-stderr.log"
vtool_status=$?
if [[ "$vtool_status" -ne 0 ]]; then
    echo "native build-version correction failed" >&2
    exit 3
fi
"$codesign" --force --sign - "$build_directory/glassintrospect" \
    >"$output_directory/codesign-stdout.log" \
    2>"$output_directory/codesign-stderr.log"
codesign_status=$?
if [[ "$codesign_status" -ne 0 ]]; then
    echo "native probe signing failed" >&2
    exit 3
fi
if /usr/bin/strings "$build_directory/glassintrospect" \
        | /usr/bin/grep -Fq '/nix/store/'; then
    echo "native probe contains a Nix store path" >&2
    exit 3
fi

while IFS='=' read -r variable _; do
    case "$variable" in
        LG_*) unset "$variable" ;;
    esac
done < <(/usr/bin/env)

{
    printf 'CAPTURE_COMMIT=%s\n' "$(git rev-parse HEAD)"
    printf '%s\n' NATIVE_CAPTURE_DEBUGGER_USED=0
    printf '%s\n' GITHUB_ACTIONS_USED=0
    /usr/bin/sw_vers
    /usr/bin/uname -m
    printf 'NATIVE_SDK_PATH=%s\n' "$macos_sdk"
    printf 'NATIVE_SDK_VERSION=%s\n' "$macos_sdk_version"
    /usr/sbin/system_profiler SPDisplaysDataType
    /usr/bin/shasum -a 256 \
        "$probe" "$validator" "$validator_test" \
        "$preflight" "$preregistration" \
        Sources/GlassIntrospect/MatrixBridge.c \
        Sources/GlassIntrospect/MatrixBridge.h \
        Sources/GlassIntrospect/HalfBlendProbe.swift \
        Sources/GlassIntrospect/HalfDotProbe.swift \
        Sources/GlassIntrospect/HalfIntrinsicProbe.swift \
        Sources/GlassIntrospect/SDFStageProbe.swift \
        "$build_directory/glassintrospect-unlinked" \
        "$build_directory/glassintrospect"
    "$vtool" -show-build "$build_directory/glassintrospect-unlinked"
    "$vtool" -show-build "$build_directory/glassintrospect"
    git status --short --untracked-files=no
} >"$output_directory/capture-context.txt"

capture_environment=(
    LG_GEOMETRY_POLICY=0
    LG_GLASS_APPEARANCE=light
    LG_GLASS_GEOMETRY=circle-combined-holdout-01
    LG_GLASS_MATERIAL=clear
    LG_TRANSITION_ALLOCATION_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_DENSE=0
    LG_TRANSITION_ALLOCATION_FIXED_STATE=0
    LG_TRANSITION_ALLOCATION_MESH_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_ONLY=0
    LG_TRANSITION_ALLOCATION_PATH_ISOLATION=0
    LG_TRANSITION_CONTROLLED_BACKDROP=0
    LG_TRANSITION_DIRECTION=materialize
    LG_TRANSITION_FINAL_SOURCE_TRACE=0
    LG_TRANSITION_HIGHLIGHT_TRACE=0
    LG_TRANSITION_HIGHLIGHT_VERTEX_TAIL_TRACE=0
    LG_TRANSITION_MATRIX_BASIS=0
    LG_TRANSITION_SMALL_CLEAR_BACKGROUND_TRACE=0
    LG_TRANSITION_SMALL_CLEAR_FINAL_COLOR_TRACE=0
    LG_TRANSITION_SMALL_CLEAR_TMUA_COMPOSITION_TRACE=0
    LG_TRANSITION_SMALL_CLEAR_TMUA_NONVACUOUS_TRACE=1
    LG_TRANSITION_TIMELINE=1
    LG_TRANSITION_UNIFORMS=1
)
{
    printf '%s\n' "${capture_environment[@]}" | LC_ALL=C sort
} >"$case_directory/capture-environment.txt"
/usr/bin/caffeinate -d -i -u \
    /usr/bin/env "${capture_environment[@]}" \
    "$build_directory/glassintrospect" "$case_directory" \
    >"$case_directory/runtime-stdout.log" \
    2>"$case_directory/runtime-stderr.log"
capture_status=$?
printf '%s\n' "$capture_status" >"$case_directory/capture-exit-status.txt"

validation_status=125
if [[ "$capture_status" -eq 0 ]]; then
    "$nix" --extra-experimental-features "nix-command flakes" \
        develop --command env PYTHONPATH=Analysis python "$validator" \
        "$case_directory" \
        --preregistration "$preregistration" \
        --preflight "$output_directory/capture-session-preflight.json" \
        --output "$validation_output" \
        >"$output_directory/validation-stdout.log" \
        2>"$output_directory/validation-stderr.log"
    validation_status=$?
else
    : >"$output_directory/validation-stdout.log"
    printf '%s\n' \
        "validation skipped because native capture failed" \
        >"$output_directory/validation-stderr.log"
fi
printf '%s\n' "$validation_status" \
    >"$output_directory/validation-exit-status.txt"

printf 'OUTPUT_DIRECTORY=%s\n' "$output_directory"
printf 'CAPTURE_STATUS=%s\n' "$capture_status"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$capture_status" -ne 0 || "$validation_status" -ne 0 ]]; then
    exit 4
fi
