#!/bin/bash

# Capture the frozen black-to-white reveal coverage corpus on the Retina Mac.
# Nix is excluded from the native phase and entered only after capture exits.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly preregistration=Analysis/walle_reveal_coverage_corpus_preregistration.json
readonly validator=Analysis/validate_walle_reveal_coverage_corpus.py
readonly validator_test=Analysis/test_validate_walle_reveal_coverage_corpus.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly probe=Sources/GlassCapture/main.swift
readonly output_root="local-walle-reveal-coverage-${run_label}-v1"
readonly capture_root="$output_root/capture"
readonly validation_output="$output_root/validation.json"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly swiftc=/Library/Developer/CommandLineTools/usr/bin/swiftc
readonly vtool=/Library/Developer/CommandLineTools/usr/bin/vtool
readonly codesign=/usr/bin/codesign
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

readonly macos_sdk=$(/usr/bin/xcrun --show-sdk-path)
readonly macos_sdk_version=$(/usr/bin/xcrun --show-sdk-version)
if [[ "$macos_sdk_version" != 26.5 ]]; then
    echo "native capture SDK is not macOS 26.5" >&2
    exit 1
fi

require_sha256 "$preregistration" 2094b1e0355be2c774f048b58073d2573f0c12238d67e20842b42c1632307d64
require_sha256 "$probe" f2cf57c4724639be712955006db512184489aa58a745f2f8aedf5e788c109f0e
require_sha256 "$validator" 19afaaae06afbe69a5834d5c0d3c5e2a535db0a1303ce8d5a032c3fc0db11189
require_sha256 "$validator_test" 0e162d610ed2ed2d1d3069c33c8513ffdc690feb6435aff0e1c6bfd4e9ce5757
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1

readonly build_directory=$(/usr/bin/mktemp -d -t lg-walle-reveal-coverage)
if [[ ! "$build_directory" =~ ^/var/folders/.+/T/lg-walle-reveal-coverage\..+$ ]]; then
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

"$swiftc" -O -parse-as-library \
    -sdk "$macos_sdk" \
    -target arm64-apple-macosx26.0 \
    "$probe" \
    -o "$build_directory/glasscap-unlinked" \
    >"$output_root/swiftc-stdout.log" \
    2>"$output_root/swiftc-stderr.log"
swiftc_status=$?
if [[ "$swiftc_status" -ne 0 ]]; then
    echo "native Swift coverage build failed" >&2
    exit 3
fi

"$vtool" \
    -set-build-version macos 26.0 26.5 \
    -replace \
    -output "$build_directory/glasscap" \
    "$build_directory/glasscap-unlinked" \
    >"$output_root/vtool-stdout.log" \
    2>"$output_root/vtool-stderr.log"
vtool_status=$?
if [[ "$vtool_status" -ne 0 ]]; then
    echo "native SDK load-command correction failed" >&2
    exit 3
fi
"$codesign" --force --sign - "$build_directory/glasscap" \
    >"$output_root/codesign-stdout.log" \
    2>"$output_root/codesign-stderr.log"
codesign_status=$?
if [[ "$codesign_status" -ne 0 ]]; then
    echo "native capture ad-hoc signing failed" >&2
    exit 3
fi
if ! "$vtool" -show-build "$build_directory/glasscap" \
        | /usr/bin/grep -Eq 'sdk[[:space:]]+26\.5$'; then
    echo "native capture binary does not declare SDK 26.5" >&2
    exit 3
fi
if /usr/bin/strings "$build_directory/glasscap" | /usr/bin/grep -Fq '/nix/store/'; then
    echo "native capture binary contains a Nix store path" >&2
    exit 3
fi

readonly capture_commit=$(git rev-parse HEAD)
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
    printf '%s\n' CAPTURE_ARGUMENTS='--width 1024 --height 1024 --suite dynamic --dynamic-frames 3 --dynamic-duration 0.2 --dynamic-modes wallpaper-reveal --transition-origin 0.25,0.30 --reveal-coverage-probe'
    /usr/bin/shasum -a 256 \
        "$probe" "$preregistration" "$validator" "$validator_test" \
        "$preflight" "$build_directory/glasscap-unlinked" \
        "$build_directory/glasscap"
    "$vtool" -show-build "$build_directory/glasscap"
    /usr/sbin/system_profiler SPDisplaysDataType
} >"$output_root/capture-context.txt"

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &
"$build_directory/glasscap" \
    --out "$capture_root" \
    --width 1024 \
    --height 1024 \
    --suite dynamic \
    --dynamic-frames 3 \
    --dynamic-duration 0.2 \
    --dynamic-modes wallpaper-reveal \
    --transition-origin 0.25,0.30 \
    --reveal-coverage-probe \
    >"$output_root/runtime-stdout.log" \
    2>"$output_root/runtime-stderr.log"
capture_status=$?
printf '%s\n' "$capture_status" >"$output_root/capture-exit-status.txt"
if [[ "$capture_status" -ne 0 ]]; then
    echo "native reveal coverage capture failed" >&2
    exit 4
fi

"$nix" --extra-experimental-features "nix-command flakes" \
    develop --command python -m unittest discover \
    -s Analysis -p test_validate_walle_reveal_coverage_corpus.py \
    >"$output_root/validator-test-stdout.log" \
    2>"$output_root/validator-test-stderr.log"
test_status=$?
printf '%s\n' "$test_status" >"$output_root/validator-test-exit-status.txt"
if [[ "$test_status" -ne 0 ]]; then
    echo "coverage validator tests failed" >&2
    exit 5
fi

"$nix" --extra-experimental-features "nix-command flakes" \
    develop --command python "$validator" \
    "$capture_root" \
    --preregistration "$preregistration" \
    --preflight "$output_root/capture-session-preflight.json" \
    --output "$validation_output" \
    >"$output_root/validation-stdout.log" \
    2>"$output_root/validation-stderr.log"
validation_status=$?
printf '%s\n' "$validation_status" >"$output_root/validation-exit-status.txt"

printf 'OUTPUT_ROOT=%s\n' "$output_root"
printf 'CAPTURE_STATUS=%s\n' "$capture_status"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"
exit "$validation_status"
