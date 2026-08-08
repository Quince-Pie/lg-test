#!/bin/bash

# Execute the frozen v1 Walle-shaped Retina transfer gate locally on macOS.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly preregistration=Analysis/walle_retina_transfer_preregistration.json
readonly validator=Analysis/validate_walle_retina_transfer.py
readonly validator_test=Analysis/test_validate_walle_retina_transfer.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly probe=Sources/GlassIntrospect/main.swift
readonly output_root="local-walle-retina-transfer-${run_label}-v1"
readonly validation_output="$output_root/validation.json"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly swiftc=/Library/Developer/CommandLineTools/usr/bin/swiftc
readonly clang=/usr/bin/xcrun
readonly vtool=/Library/Developer/CommandLineTools/usr/bin/vtool
readonly codesign=/usr/bin/codesign
readonly macos_sdk=$(/usr/bin/xcrun --show-sdk-path)
readonly macos_sdk_version=$(/usr/bin/xcrun --show-sdk-version)
readonly nix=/nix/var/nix/profiles/default/bin/nix
readonly -a cases=(
    clear-light:clear:light
    clear-dark:clear:dark
    regular-light:regular:light
    regular-dark:regular:dark
)

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

require_sha256 "$probe" f12d4cc2c6f4889d044e954bd83a7cf5d892dfa40e6a19e87e33781b8fb86767
require_sha256 "$validator" e518bd30c3281ea4801e3ca6ba466df132b78da8a46f7b62e9779179e4a5def2
require_sha256 "$validator_test" 7a996d0b0f22d17341c9c84ce7fcfe8b033591080769dde4eca47bac2c0957e1
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1
require_sha256 "$preregistration" 7f595478a591735279e589b8bc85a95cb865fcd63da484ff8cb8ddba091fc01b
require_sha256 Sources/GlassIntrospect/MatrixBridge.c 841b30cc127582b6819ec997b99d360c9d3fc19e6bfc26cf718d402c78275057
require_sha256 Sources/GlassIntrospect/MatrixBridge.h a7dd8dd8978dffa1b42764b19868dc5b305caa2fea4b3ab171329d15f6e91d0c
require_sha256 Sources/GlassIntrospect/HalfBlendProbe.swift 6cadb5f286d9f97d80f40a1a8b82c2487fe660f4f2614ec0b44458f396ccb263
require_sha256 Sources/GlassIntrospect/HalfDotProbe.swift f27844610b4c051cd99ac474e48c05b7d40240782573d8040819411e7eadd1f0
require_sha256 Sources/GlassIntrospect/HalfIntrinsicProbe.swift ae8c28a4dbbf440c79adce3d63586b2a5087a181329414a00ff557115e280a41
require_sha256 Sources/GlassIntrospect/SDFStageProbe.swift 12d300f75ae875366e850c02d63ceadee72b3ee4f155e4a65f4b0585514b0208

if [[ -e "$output_root" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi

readonly build_directory=$(/usr/bin/mktemp -d -t lg-walle-retina)
if [[ ! "$build_directory" =~ ^/var/folders/.+/T/lg-walle-retina\..+$ ]]; then
    echo "unexpected temporary build directory" >&2
    exit 1
fi
cleanup() {
    /bin/rm -rf "$build_directory"
}
trap cleanup EXIT

/bin/mkdir -p "$output_root"
"$swift" "$preflight" >"$output_root/capture-session-preflight.json"
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
    >"$output_root/clang-stdout.log" \
    2>"$output_root/clang-stderr.log"
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
    >"$output_root/swiftc-stdout.log" \
    2>"$output_root/swiftc-stderr.log"
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
    >"$output_root/vtool-stdout.log" \
    2>"$output_root/vtool-stderr.log"
vtool_status=$?
if [[ "$vtool_status" -ne 0 ]]; then
    echo "native SDK load-command correction failed" >&2
    exit 3
fi
"$codesign" --force --sign - "$build_directory/glassintrospect" \
    >"$output_root/codesign-stdout.log" \
    2>"$output_root/codesign-stderr.log"
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
    LG_CASE22_PROVIDER_FIELD_PROBE=0
    LG_GEOMETRY_POLICY=0
    LG_GLASS_GEOMETRY=circle-800-center
    LG_TRANSITION_TIMELINE=0
    LG_WALLE_RETINA_TRANSFER_TRACE=1
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
    printf 'CASES=%s\n' "${cases[*]}"
    git status --short --untracked-files=no
} >"$output_root/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &
aggregate_capture_status=0
for case_specification in "${cases[@]}"; do
    IFS=: read -r case_label material appearance <<<"$case_specification"
    case_directory="$output_root/$case_label"
    /bin/mkdir -p "$case_directory"
    /usr/bin/env \
        "${capture_environment[@]}" \
        "LG_GLASS_MATERIAL=$material" \
        "LG_GLASS_APPEARANCE=$appearance" \
        "$build_directory/glassintrospect" "$case_directory" \
        >"$case_directory/runtime-stdout.log" \
        2>"$case_directory/runtime-stderr.log"
    case_status=$?
    printf '%s\n' "$case_status" >"$case_directory/capture-exit-status.txt"
    if [[ "$case_status" -ne 0 ]]; then
        aggregate_capture_status=1
    fi
done
printf '%s\n' "$aggregate_capture_status" \
    >"$output_root/capture-exit-status.txt"

"$nix" --extra-experimental-features "nix-command flakes" \
    develop --command python "$validator" \
    "$output_root" \
    --preregistration "$preregistration" \
    --preflight "$output_root/capture-session-preflight.json" \
    --output "$validation_output" \
    >"$output_root/validation-stdout.log" \
    2>"$output_root/validation-stderr.log"
validation_status=$?
printf '%s\n' "$validation_status" \
    >"$output_root/validation-exit-status.txt"

printf 'OUTPUT_ROOT=%s\n' "$output_root"
printf 'CAPTURE_STATUS=%s\n' "$aggregate_capture_status"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$aggregate_capture_status" -ne 0 || "$validation_status" -ne 0 ]]; then
    exit 4
fi
