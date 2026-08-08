#!/bin/bash

# Execute the frozen static regular producer-geometry holdout on the Retina M1.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly preregistration=Analysis/static_regular_producer_geometry_holdout_preregistration.json
readonly validator=Analysis/validate_static_regular_producer_geometry_holdout.py
readonly model=Analysis/static_regular_producer_geometry.py
readonly model_test=Analysis/test_static_regular_producer_geometry.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly probe=Sources/GlassIntrospect/main.swift
readonly output_directory="local-static-regular-producer-geometry-holdout-${run_label}"
readonly validation_output="$output_directory/validation.json"
readonly swift=/Library/Developer/CommandLineTools/usr/bin/swift
readonly swiftc=/Library/Developer/CommandLineTools/usr/bin/swiftc
readonly clang=/usr/bin/xcrun
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

require_sha256 "$probe" 114ae3c2c5f61b99fd377a20f6461cb2dc6513db819fe9978599b5da8075263b
require_sha256 "$model" a58f5b6acc8c5c863189079bfeb66f2c60c329d9ca385b4e67dee8c8a4898b36
require_sha256 "$validator" e71effe0dd1d697680ee2078e5e558965ba6fb3540800c5deac359ed2071943b
require_sha256 "$model_test" 17fbd0a901fe91efa76a4630565f3b6d4836639d9e38ee44083bb5d8a017020d
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1
require_sha256 "$preregistration" f0d4c328962af5b4b9ebab48dbab5772c55e449723becb83ca72faeef9598a36

if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "tracked repository state is dirty" >&2
    exit 1
fi
if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi

readonly build_directory=$(/usr/bin/mktemp -d -t lg-static-geometry-holdout)
if [[ ! "$build_directory" =~ ^/var/folders/.+/T/lg-static-geometry-holdout\..+$ ]]; then
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
    -target "$(/usr/bin/uname -m)-apple-macos26.0" \
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
    -target "$(/usr/bin/uname -m)-apple-macos26.0" \
    -import-objc-header Sources/GlassIntrospect/MatrixBridge.h \
    Sources/GlassIntrospect/HalfBlendProbe.swift \
    Sources/GlassIntrospect/HalfDotProbe.swift \
    Sources/GlassIntrospect/HalfIntrinsicProbe.swift \
    Sources/GlassIntrospect/SDFStageProbe.swift \
    Sources/GlassIntrospect/main.swift \
    "$build_directory/MatrixBridge.o" \
    -o "$build_directory/glassintrospect" \
    >"$output_directory/swiftc-stdout.log" \
    2>"$output_directory/swiftc-stderr.log"
swiftc_status=$?
if [[ "$swiftc_status" -ne 0 ]]; then
    echo "native Swift probe build failed" >&2
    exit 3
fi

while IFS='=' read -r variable _; do
    case "$variable" in
        LG_*) unset "$variable" ;;
    esac
done < <(/usr/bin/env)

readonly -a capture_environment=(
    MTL_CAPTURE_ENABLED=1
    LG_EXECUTE_INDEPENDENT_GLASS=1
    LG_GLASS_MATERIAL=regular
    LG_GLASS_APPEARANCE=light
    LG_GLASS_GEOMETRY=circle-377-fractional-holdout
)

{
    git rev-parse HEAD
    /usr/bin/sw_vers
    /usr/bin/system_profiler SPDisplaysDataType
    /usr/bin/shasum -a 256 \
        "$probe" "$model" "$validator" "$model_test" \
        "$preflight" "$preregistration" "$build_directory/glassintrospect"
    printf '%s\n' "${capture_environment[@]}" | LC_ALL=C sort
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
        "validation skipped because the native capture failed" \
        >"$output_directory/validation-stderr.log"
fi
printf '%s\n' "$validation_status" >"$output_directory/validation-exit-status.txt"

printf 'OUTPUT_DIRECTORY=%s\n' "$output_directory"
printf 'CAPTURE_STATUS=%s\n' "$capture_status"
printf 'VALIDATION_OUTPUT=%s\n' "$validation_output"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$capture_status" -ne 0 ]]; then
    exit 4
fi
if [[ "$validation_status" -ne 0 ]]; then
    exit 5
fi
