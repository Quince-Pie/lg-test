#!/bin/bash

# Capture regular Liquid Glass producer/copy/mip bytes on the physical Retina
# Mac. Native build and capture deliberately exclude Nix; validation is a
# separate post-capture step.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly preregistration=Analysis/walle_regular_controlled_backdrop_preregistration.json
readonly validator=Analysis/validate_walle_regular_controlled_backdrop.py
readonly validator_test=Analysis/test_validate_walle_regular_controlled_backdrop.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly probe=Sources/GlassIntrospect/main.swift
readonly output_root="local-walle-regular-controlled-backdrop-${run_label}-v1"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly swiftc=/Library/Developer/CommandLineTools/usr/bin/swiftc
readonly xcrun=/usr/bin/xcrun
readonly vtool=/Library/Developer/CommandLineTools/usr/bin/vtool
readonly codesign=/usr/bin/codesign

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
if /usr/bin/env | /usr/bin/grep -Fq '/nix/store/'; then
    echo "native build/capture environment contains a Nix store path" >&2
    exit 1
fi
if [[ -n $(git status --short --untracked-files=no) ]]; then
    echo "capture checkout has tracked modifications" >&2
    exit 1
fi
if [[ -e "$output_root" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi

readonly macos_sdk=$($xcrun --show-sdk-path)
readonly macos_sdk_version=$($xcrun --show-sdk-version)
if [[ "$macos_sdk_version" != 26.5 ]]; then
    echo "native capture SDK is not macOS 26.5" >&2
    exit 1
fi

require_sha256 "$preregistration" bfe48f11d63b990a245b1f8959e03c0baebb9d26a7f7ba27fa805cba77262436
require_sha256 "$probe" dd3d7aa262424ce0b0d6351dd3fc8051b851a1464392caf0f1c36da1d38e9315
require_sha256 "$validator" 6b8a34c4e34d95fcbe1348654483e4368673748b2eaca3fa43a6a05ba9b5bd11
require_sha256 "$validator_test" 3bf51ac116ec4d2a0bf18aa0da0567cb98e4a98dccd0d35ff230dd92a61f9f62
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1
require_sha256 Sources/GlassIntrospect/MatrixBridge.c 841b30cc127582b6819ec997b99d360c9d3fc19e6bfc26cf718d402c78275057
require_sha256 Sources/GlassIntrospect/MatrixBridge.h a7dd8dd8978dffa1b42764b19868dc5b305caa2fea4b3ab171329d15f6e91d0c
require_sha256 Sources/GlassIntrospect/HalfBlendProbe.swift 6cadb5f286d9f97d80f40a1a8b82c2487fe660f4f2614ec0b44458f396ccb263
require_sha256 Sources/GlassIntrospect/HalfDotProbe.swift f27844610b4c051cd99ac474e48c05b7d40240782573d8040819411e7eadd1f0
require_sha256 Sources/GlassIntrospect/HalfIntrinsicProbe.swift ae8c28a4dbbf440c79adce3d63586b2a5087a181329414a00ff557115e280a41
require_sha256 Sources/GlassIntrospect/SDFStageProbe.swift 12d300f75ae875366e850c02d63ceadee72b3ee4f155e4a65f4b0585514b0208

readonly build_directory=$(/usr/bin/mktemp -d -t lg-walle-regular-controlled)
if [[ ! "$build_directory" =~ ^/var/folders/.+/T/lg-walle-regular-controlled\..+$ ]]; then
    echo "unexpected temporary build directory" >&2
    exit 1
fi
cleanup() {
    /bin/rm -rf "$build_directory"
}
trap cleanup EXIT

/bin/mkdir -p "$output_root"
"$swift" "$preflight" >"$output_root/capture-session-preflight.json"
if [[ $? -ne 0 ]]; then
    echo "Retina session preflight failed; no app was launched" >&2
    exit 2
fi

"$xcrun" clang \
    -std=c23 -O2 -Wall -Wextra -Werror \
    -target arm64-apple-macosx26.0 \
    -c Sources/GlassIntrospect/MatrixBridge.c \
    -o "$build_directory/MatrixBridge.o" \
    >"$output_root/clang-stdout.log" \
    2>"$output_root/clang-stderr.log"
if [[ $? -ne 0 ]]; then
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
    >"$output_root/swiftc-stdout.log" \
    2>"$output_root/swiftc-stderr.log"
if [[ $? -ne 0 ]]; then
    echo "native Swift probe build failed" >&2
    exit 3
fi

"$vtool" \
    -set-build-version macos 26.0 26.5 \
    -replace \
    -output "$build_directory/glassintrospect" \
    "$build_directory/glassintrospect-unlinked" \
    >"$output_root/vtool-stdout.log" \
    2>"$output_root/vtool-stderr.log"
if [[ $? -ne 0 ]]; then
    echo "native SDK load-command correction failed" >&2
    exit 3
fi
"$codesign" --force --sign - "$build_directory/glassintrospect" \
    >"$output_root/codesign-stdout.log" \
    2>"$output_root/codesign-stderr.log"
if [[ $? -ne 0 ]]; then
    echo "native probe ad-hoc signing failed" >&2
    exit 3
fi
if ! "$vtool" -show-build "$build_directory/glassintrospect" \
        | /usr/bin/grep -Eq 'sdk[[:space:]]+26\.5$'; then
    echo "native probe does not declare SDK 26.5" >&2
    exit 3
fi

readonly capture_commit=$(git rev-parse HEAD)
readonly probe_sha256=$(/usr/bin/shasum -a 256 "$probe" | /usr/bin/awk '{print $1}')
readonly preregistration_sha256=$(/usr/bin/shasum -a 256 "$preregistration" | /usr/bin/awk '{print $1}')
readonly runner_sha256=$(/usr/bin/shasum -a 256 "$0" | /usr/bin/awk '{print $1}')
{
    printf 'CAPTURE_COMMIT=%s\n' "$capture_commit"
    printf '%s\n' GITHUB_ACTIONS_USED=0
    printf '%s\n' NATIVE_CAPTURE_DEBUGGER_USED=0
    printf '%s\n' NIX_STORE_PATH_IN_NATIVE_BUILD_OR_CAPTURE=0
    printf 'MACOS_PRODUCT_VERSION=%s\n' "$(/usr/bin/sw_vers -productVersion)"
    printf 'MACOS_BUILD_VERSION=%s\n' "$(/usr/bin/sw_vers -buildVersion)"
    printf 'ARCHITECTURE=%s\n' "$(/usr/bin/uname -m)"
    printf 'NATIVE_SDK_PATH=%s\n' "$macos_sdk"
    printf 'NATIVE_SDK_VERSION=%s\n' "$macos_sdk_version"
    printf 'PROBE_SHA256=%s\n' "$probe_sha256"
    printf 'PREREGISTRATION_SHA256=%s\n' "$preregistration_sha256"
    printf 'RUNNER_SHA256=%s\n' "$runner_sha256"
    printf '%s\n' LG_GLASS_MATERIAL=regular
    printf '%s\n' LG_GLASS_APPEARANCE=dark
    printf '%s\n' LG_GLASS_GEOMETRY=circle-480-center
    printf '%s\n' LG_TRANSITION_TIMELINE=1
    printf '%s\n' LG_TRANSITION_UNIFORMS=1
    printf '%s\n' LG_TRANSITION_DIRECTION=dematerialize
    printf '%s\n' LG_TRANSITION_CONTROLLED_BACKDROP=1
    printf '%s\n' LG_TRANSITION_HIGHLIGHT_TRACE=0
    printf '%s\n' LG_TRANSITION_CURRENT_COMPOSITOR_TRANSFER_TRACE=0
    printf '%s\n' LG_TRANSITION_ISCD_BORDER_TRACE=0
    printf '%s\n' LG_ENABLE_UNSAFE_PRIVATE_INTERPOLANT_TRACE=0
    /usr/bin/shasum -a 256 \
        "$build_directory/glassintrospect-unlinked" \
        "$build_directory/glassintrospect"
    "$vtool" -show-build "$build_directory/glassintrospect"
    /usr/sbin/system_profiler SPDisplaysDataType
} >"$output_root/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &
/usr/bin/env \
    LG_GLASS_MATERIAL=regular \
    LG_GLASS_APPEARANCE=dark \
    LG_GLASS_GEOMETRY=circle-480-center \
    LG_TRANSITION_TIMELINE=1 \
    LG_TRANSITION_UNIFORMS=1 \
    LG_TRANSITION_DIRECTION=dematerialize \
    LG_TRANSITION_CONTROLLED_BACKDROP=1 \
    LG_TRANSITION_HIGHLIGHT_TRACE=0 \
    LG_TRANSITION_CURRENT_COMPOSITOR_TRANSFER_TRACE=0 \
    LG_TRANSITION_ISCD_BORDER_TRACE=0 \
    LG_ENABLE_UNSAFE_PRIVATE_INTERPOLANT_TRACE=0 \
    "$build_directory/glassintrospect" "$output_root" \
    >"$output_root/runtime-stdout.log" \
    2>"$output_root/runtime-stderr.log"
capture_status=$?
printf '%s\n' "$capture_status" >"$output_root/capture-exit-status.txt"

if [[ -f "$output_root/transition-timeline.json" ]]; then
    timeline_sha256=$(
        /usr/bin/shasum -a 256 "$output_root/transition-timeline.json" \
            | /usr/bin/awk '{print $1}'
    )
    printf 'TIMELINE_SHA256=%s\n' "$timeline_sha256" \
        >>"$output_root/capture-context.txt"
fi

printf 'OUTPUT_ROOT=%s\n' "$output_root"
printf 'CAPTURE_STATUS=%s\n' "$capture_status"
if [[ -f "$output_root/transition-timeline.json" ]]; then
    printf 'TIMELINE_SHA256=%s\n' "$timeline_sha256"
fi
exit "$capture_status"
