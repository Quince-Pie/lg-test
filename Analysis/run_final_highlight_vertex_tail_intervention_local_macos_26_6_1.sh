#!/bin/bash

# Execute the frozen Irsd vertex-tail intervention on the physical Retina M1.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly preregistration=Analysis/final_highlight_vertex_tail_intervention_preregistration.json
readonly validator=Analysis/validate_final_highlight_vertex_tail_intervention.py
readonly validator_test=Analysis/test_validate_final_highlight_vertex_tail_intervention.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly probe=Sources/GlassIntrospect/main.swift
readonly output_directory="local-final-highlight-vertex-tail-${run_label}"
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

require_sha256 "$probe" 2497b628a59e65b357ce2f53fc5720da481d52630e8c277813891c1103f8a9b3
require_sha256 "$validator" 7d9d6b0af95ceaec17e626ed8a8c0138d65b271951a02eaa6b82787cb43e0a50
require_sha256 "$validator_test" c0c4a69368581e7ce057bcc889a0e6300893b67522381d44451e7870f88b63e6
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1
require_sha256 "$preregistration" 15f7dc934d88e067c9f2b8175b5546752f68eeaf10cc7b2199b1adbbcd7843f0
require_sha256 Sources/GlassIntrospect/MatrixBridge.c 841b30cc127582b6819ec997b99d360c9d3fc19e6bfc26cf718d402c78275057
require_sha256 Sources/GlassIntrospect/MatrixBridge.h a7dd8dd8978dffa1b42764b19868dc5b305caa2fea4b3ab171329d15f6e91d0c
require_sha256 Sources/GlassIntrospect/HalfBlendProbe.swift 6cadb5f286d9f97d80f40a1a8b82c2487fe660f4f2614ec0b44458f396ccb263
require_sha256 Sources/GlassIntrospect/HalfDotProbe.swift f27844610b4c051cd99ac474e48c05b7d40240782573d8040819411e7eadd1f0
require_sha256 Sources/GlassIntrospect/HalfIntrinsicProbe.swift ae8c28a4dbbf440c79adce3d63586b2a5087a181329414a00ff557115e280a41
require_sha256 Sources/GlassIntrospect/SDFStageProbe.swift 12d300f75ae875366e850c02d63ceadee72b3ee4f155e4a65f4b0585514b0208

if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi

readonly build_directory=$(/usr/bin/mktemp -d -t lg-highlight-tail)
if [[ ! "$build_directory" =~ ^/var/folders/.+/T/lg-highlight-tail\..+$ ]]; then
    echo "unexpected temporary build directory" >&2
    exit 1
fi
cleanup() {
    /bin/rm -rf "$build_directory"
}
trap cleanup EXIT

/bin/mkdir -p "$output_directory"
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

# Swift 6.3.3 currently emits an LC_BUILD_VERSION SDK of 26.0 even when the
# selected native SDK is 26.5. SwiftUI uses this link-time SDK value for
# compatibility behavior: the 26.0 executable loses the presentation glass
# filter at sample 1, while the otherwise identical 26.5-linked executable
# retains the complete timeline. Declare the SDK that actually supplied the
# headers/frameworks, then restore the ad-hoc signature invalidated by vtool.
"$vtool" \
    -set-build-version macos 26.0 26.5 \
    -replace \
    -output "$build_directory/glassintrospect" \
    "$build_directory/glassintrospect-unlinked" \
    >"$output_directory/vtool-stdout.log" \
    2>"$output_directory/vtool-stderr.log"
vtool_status=$?
if [[ "$vtool_status" -ne 0 ]]; then
    echo "native SDK load-command correction failed" >&2
    exit 3
fi
"$codesign" --force --sign - "$build_directory/glassintrospect" \
    >"$output_directory/codesign-stdout.log" \
    2>"$output_directory/codesign-stderr.log"
codesign_status=$?
if [[ "$codesign_status" -ne 0 ]]; then
    echo "native probe ad-hoc signing failed" >&2
    exit 3
fi
if ! "$vtool" -show-build "$build_directory/glassintrospect" \
        | /usr/bin/grep -Eq 'sdk[[:space:]]+26\.5$'; then
    echo "native probe does not declare SDK 26.5" >&2
    exit 3
fi

while IFS='=' read -r variable _; do
    case "$variable" in
        LG_*) unset "$variable" ;;
    esac
done < <(/usr/bin/env)

readonly -a capture_environment=(
    LG_GEOMETRY_POLICY=0
    LG_GLASS_APPEARANCE=dark
    LG_GLASS_GEOMETRY=circle-480-center
    LG_GLASS_MATERIAL=regular
    LG_TRANSITION_ALLOCATION_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_DENSE=0
    LG_TRANSITION_ALLOCATION_FIXED_STATE=0
    LG_TRANSITION_ALLOCATION_MESH_CALIBRATION=0
    LG_TRANSITION_ALLOCATION_ONLY=0
    LG_TRANSITION_ALLOCATION_PATH_ISOLATION=0
    LG_TRANSITION_CONTROLLED_BACKDROP=0
    LG_TRANSITION_DIRECTION=dematerialize
    LG_TRANSITION_HIGHLIGHT_TRACE=0
    LG_TRANSITION_HIGHLIGHT_VERTEX_TAIL_TRACE=1
    LG_TRANSITION_MATRIX_BASIS=0
    LG_TRANSITION_TIMELINE=1
    LG_TRANSITION_UNIFORMS=1
)

{
    printf 'CAPTURE_COMMIT=%s\n' "$(git rev-parse HEAD)"
    printf '%s\n' NATIVE_CAPTURE_DEBUGGER_USED=0
    printf '%s\n' GITHUB_ACTIONS_USED=0
    printf '%s\n' TRACKED_DIRTY_STATE_PERMITTED_WITH_PINNED_BUILD_INPUTS=1
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
    printf '%s\n' "${capture_environment[@]}" | LC_ALL=C sort
    git status --short --untracked-files=no
} >"$output_directory/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &
/usr/bin/env "${capture_environment[@]}" \
    "$build_directory/glassintrospect" "$output_directory" \
    >"$output_directory/runtime-stdout.log" \
    2>"$output_directory/runtime-stderr.log"
capture_status=$?
printf '%s\n' "$capture_status" >"$output_directory/capture-exit-status.txt"

validation_status=125
if [[ "$capture_status" -eq 0 ]]; then
    "$nix" --extra-experimental-features "nix-command flakes" \
        develop --command python "$validator" \
        "$output_directory" \
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
