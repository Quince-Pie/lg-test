#!/bin/bash

# Execute the frozen combined transition-geometry holdout on the Retina M1.

set -uo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "usage: $0 RUN_LABEL" >&2
    exit 64
fi

readonly run_label=$1
readonly repository=$(cd "$(dirname "$0")/.." && pwd -P)
readonly preregistration=Analysis/combined_transition_geometry_holdout_preregistration.json
readonly validator=Analysis/validate_combined_transition_geometry_holdout_local_macos_26_6_1.py
readonly validator_test=Analysis/test_validate_combined_transition_geometry_holdout_local_macos_26_6_1.py
readonly analyzer=Analysis/analyze_transition_geometry_corpus_local_macos_26_6_1.py
readonly analyzer_test=Analysis/test_analyze_transition_geometry_corpus_local_macos_26_6_1.py
readonly preflight=Analysis/check_local_retina_capture_session_v2.swift
readonly probe=Sources/GlassIntrospect/main.swift
readonly output_directory="local-combined-transition-geometry-holdout-${run_label}"
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
if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
    echo "tracked repository state is dirty" >&2
    exit 1
fi
if [[ -e "$output_directory" ]]; then
    echo "capture output already exists for run label $run_label" >&2
    exit 1
fi

require_sha256 "$preregistration" 2d8dea3efc988259341ed716b00a4f439d3780bfd029e693e0599eb5e553baeb
require_sha256 "$validator" a6ba3a5c37e37a8850991f4a3aeedf1daf44bb8bf78adebb09f5197f45af140b
require_sha256 "$validator_test" 75def84b2c2ec76d191c4d20bb2267410e8ff18acfa7d678a40456f897032886
require_sha256 "$analyzer" 75a2afded65ebf3b44c1c67a93e52d1bb44d5b25ce6a2f9c93af06dde36c3386
require_sha256 "$analyzer_test" 61cbb7ea201738fdfb9b5bc1c4e4d2f8cbe52a0c45f3c65a525dd2b591c76498
require_sha256 "$preflight" f12a1cbe29629dc843cc3250a46fa686225f3c08bcf1bf1dbdf50aea913926f1
require_sha256 "$probe" 67f0bcf8bb3df98157c72f52b959c5b159578fec4b09b9f8596b2183c93de2d3
require_sha256 Sources/GlassIntrospect/MatrixBridge.c 841b30cc127582b6819ec997b99d360c9d3fc19e6bfc26cf718d402c78275057
require_sha256 Sources/GlassIntrospect/MatrixBridge.h a7dd8dd8978dffa1b42764b19868dc5b305caa2fea4b3ab171329d15f6e91d0c
require_sha256 Sources/GlassIntrospect/HalfBlendProbe.swift 6cadb5f286d9f97d80f40a1a8b82c2487fe660f4f2614ec0b44458f396ccb263
require_sha256 Sources/GlassIntrospect/HalfDotProbe.swift f27844610b4c051cd99ac474e48c05b7d40240782573d8040819411e7eadd1f0
require_sha256 Sources/GlassIntrospect/HalfIntrinsicProbe.swift ae8c28a4dbbf440c79adce3d63586b2a5087a181329414a00ff557115e280a41
require_sha256 Sources/GlassIntrospect/SDFStageProbe.swift 12d300f75ae875366e850c02d63ceadee72b3ee4f155e4a65f4b0585514b0208

readonly build_directory=$(/usr/bin/mktemp -d -t lg-combined-transition)
if [[ ! "$build_directory" =~ ^/var/folders/.+/T/lg-combined-transition\..+$ ]]; then
    echo "unexpected temporary build directory" >&2
    exit 1
fi
cleanup() {
    /bin/rm -rf "$build_directory"
}
trap cleanup EXIT

/bin/mkdir -p "$output_directory"

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
        LG_*|MTL_CAPTURE_ENABLED) unset "$variable" ;;
    esac
done < <(/usr/bin/env)

readonly capture_commit=$(git rev-parse HEAD)
capture_binary_sha256=$(
    /usr/bin/shasum -a 256 "$build_directory/glassintrospect"
)
capture_binary_sha256=${capture_binary_sha256%% *}
readonly capture_binary_sha256
readonly -a cases=(
    'clear-light-materialize-01|clear|light|materialize|circle-combined-holdout-01'
    'clear-dark-materialize-02|clear|dark|materialize|circle-combined-holdout-02'
    'regular-light-materialize-03|regular|light|materialize|circle-combined-holdout-03'
    'regular-dark-materialize-04|regular|dark|materialize|circle-combined-holdout-04'
    'clear-light-dematerialize-05|clear|light|dematerialize|circle-combined-holdout-05'
    'clear-dark-dematerialize-06|clear|dark|dematerialize|circle-combined-holdout-06'
    'regular-light-dematerialize-07|regular|light|dematerialize|circle-combined-holdout-07'
    'regular-dark-dematerialize-08|regular|dark|dematerialize|circle-combined-holdout-08'
)

/usr/bin/caffeinate -d -i -u -w $$ >/dev/null 2>&1 &
capture_failures=0
for specification in "${cases[@]}"; do
    IFS='|' read -r case_id material appearance direction geometry \
        <<<"$specification"
    case_directory="$output_directory/$case_id"
    /bin/mkdir -p "$case_directory"

    "$swift" "$preflight" >"$case_directory/capture-session-preflight.json"
    preflight_status=$?
    printf '%s\n' "$preflight_status" \
        >"$case_directory/preflight-exit-status.txt"

    capture_environment=(
        LG_GEOMETRY_POLICY=0
        "LG_GLASS_APPEARANCE=$appearance"
        "LG_GLASS_GEOMETRY=$geometry"
        "LG_GLASS_MATERIAL=$material"
        LG_TRANSITION_ALLOCATION_CALIBRATION=0
        LG_TRANSITION_ALLOCATION_DENSE=1
        LG_TRANSITION_ALLOCATION_FIXED_STATE=0
        LG_TRANSITION_ALLOCATION_MESH_CALIBRATION=0
        LG_TRANSITION_ALLOCATION_ONLY=0
        LG_TRANSITION_ALLOCATION_PATH_ISOLATION=0
        LG_TRANSITION_CONTROLLED_BACKDROP=0
        "LG_TRANSITION_DIRECTION=$direction"
        LG_TRANSITION_HIGHLIGHT_TRACE=0
        LG_TRANSITION_HIGHLIGHT_VERTEX_TAIL_TRACE=0
        LG_TRANSITION_MATRIX_BASIS=0
        LG_TRANSITION_TIMELINE=1
        LG_TRANSITION_UNIFORMS=1
    )

    {
        printf 'CAPTURE_COMMIT=%s\n' "$capture_commit"
        printf 'CAPTURE_BINARY_SHA256=%s\n' "$capture_binary_sha256"
        printf '%s\n' NATIVE_CAPTURE_DEBUGGER_USED=0
        printf '%s\n' GITHUB_ACTIONS_USED=0
        printf '%s\n' TRACKED_DIRTY_STATE=0
        printf '%s\n' MTL_CAPTURE_ENABLED=0
        printf 'NATIVE_SDK_PATH=%s\n' "$macos_sdk"
        printf 'NATIVE_SDK_VERSION=%s\n' "$macos_sdk_version"
        printf '%s\n' NATIVE_DECLARED_SDK_VERSION=26.5
        /usr/bin/sw_vers
        /usr/bin/uname -m
        /usr/sbin/system_profiler SPDisplaysDataType
        /usr/bin/shasum -a 256 \
            "$preregistration" "$validator" "$validator_test" \
            "$analyzer" "$analyzer_test" "$preflight" "$probe" \
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
    } >"$case_directory/capture-context.txt"

    capture_status=126
    if [[ "$preflight_status" -eq 0 ]]; then
        /usr/bin/env "${capture_environment[@]}" \
            "$build_directory/glassintrospect" "$case_directory" \
            >"$case_directory/runtime-stdout.log" \
            2>"$case_directory/runtime-stderr.log"
        capture_status=$?
    else
        : >"$case_directory/runtime-stdout.log"
        printf '%s\n' \
            "capture skipped because the Retina preflight failed" \
            >"$case_directory/runtime-stderr.log"
    fi
    printf '%s\n' "$capture_status" \
        >"$case_directory/capture-exit-status.txt"
    if [[ "$capture_status" -ne 0 ]]; then
        capture_failures=$((capture_failures + 1))
    fi
done

validation_status=125
if [[ "$capture_failures" -eq 0 ]]; then
    "$nix" --extra-experimental-features "nix-command flakes" \
        develop --command python "$validator" \
        "$output_directory" \
        --preregistration "$preregistration" \
        --output "$validation_output" \
        >"$output_directory/validation-stdout.log" \
        2>"$output_directory/validation-stderr.log"
    validation_status=$?
else
    : >"$output_directory/validation-stdout.log"
    printf '%s\n' \
        "validation skipped because one or more native captures failed" \
        >"$output_directory/validation-stderr.log"
fi
printf '%s\n' "$validation_status" \
    >"$output_directory/validation-exit-status.txt"

printf 'OUTPUT_DIRECTORY=%s\n' "$output_directory"
printf 'CAPTURE_FAILURES=%s\n' "$capture_failures"
printf 'VALIDATION_OUTPUT=%s\n' "$validation_output"
printf 'VALIDATION_STATUS=%s\n' "$validation_status"

if [[ "$capture_failures" -ne 0 || "$validation_status" -ne 0 ]]; then
    exit 4
fi
