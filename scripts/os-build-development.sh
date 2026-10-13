#!/usr/bin/env bash
# Local development artifacts only: no finalization, release signing or phone operations.
set -euo pipefail

usage() {
  echo "Usage: $0 CHECKOUT --generated-inventory FILE --artifacts DIR" >&2
  echo "Set numeric BUILD_NUMBER and BUILD_DATETIME; optional BUILD_JOBS defaults to 8." >&2
}
blocked() { echo "BLOCKED: $*" >&2; exit 1; }
argument_error() { echo "$*" >&2; usage; exit 2; }

if [[ $# == 1 && "$1" == --help ]]; then usage; exit 0; fi
[[ $# -ge 1 && "$1" != --* ]] || argument_error "A prepared checkout is required"
[[ "$(uname -s)" == Linux ]] || blocked "development OS builds require Linux"
readonly development_project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
development_source_root="$(realpath -e -- "$1")"
[[ -d "$development_source_root" ]] || argument_error "Checkout must be a directory"
readonly development_source_root
shift
development_inventory=
development_artifacts=
while [[ $# -gt 0 ]]; do
  case "$1" in
    --generated-inventory|--artifacts)
      option="$1"
      [[ $# -ge 2 && "$2" != --* ]] || argument_error "Missing value for $option"
      if [[ "$option" == --generated-inventory ]]; then
        [[ -z "$development_inventory" ]] || argument_error "Duplicate $option"
        development_inventory="$(realpath -e -- "$2")"
      else
        [[ -z "$development_artifacts" ]] || argument_error "Duplicate $option"
        development_artifacts="$(realpath -e -- "$2")"
      fi
      shift 2
      ;;
    *) argument_error "Unknown development build option: $1" ;;
  esac
done
[[ -f "$development_inventory" && -r "$development_inventory" && -d "$development_artifacts" ]] \
  || argument_error "Readable --generated-inventory FILE and --artifacts DIR are required"
readonly development_inventory development_artifacts
[[ "${BUILD_NUMBER:-}" =~ ^[0-9]+$ ]] || blocked "set an explicit numeric BUILD_NUMBER"
[[ "${BUILD_DATETIME:-}" =~ ^[0-9]+$ ]] || blocked "set an explicit numeric BUILD_DATETIME (Unix seconds)"
readonly development_build_number="$BUILD_NUMBER" development_build_datetime="$BUILD_DATETIME"
readonly development_jobs="${BUILD_JOBS:-8}"
[[ "$development_jobs" =~ ^[1-9][0-9]*$ ]] || blocked "BUILD_JOBS must be a positive integer"

# Check resources and fresh outputs before executing any code from the checkout.
python3 - "$development_source_root" <<'PY'
import os, pathlib, shutil, sys
root = pathlib.Path(sys.argv[1])
memory = int(next(line.split()[1] for line in pathlib.Path('/proc/meminfo').read_text().splitlines()
                  if line.startswith('MemTotal:'))) * 1024
for name in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
    limit = pathlib.Path(name)
    if limit.exists():
        value = limit.read_text().strip()
        if value.isdigit():
            memory = min(memory, int(value))
if memory < 64 * 1024**3 or shutil.disk_usage(root).free < 400 * 1024**3:
    raise SystemExit('BLOCKED: need at least 64 GiB RAM and 400 GiB free disk on this runner')
if os.path.lexists(root / 'out'):
    raise SystemExit('BLOCKED: development build requires a fresh out directory; archive previous outputs separately')
PY

python3 "$development_project_root/scripts/os-pipeline.py" \
  --lock "$development_project_root/os/development-lock.json" --development verify-tree \
  --source "$development_source_root" --generated-inventory "$development_inventory" \
  --artifacts "$development_artifacts"

cd "$development_source_root"
# Upstream gettop prefers inherited TOP, including when sourcing shell_utils.sh.
# Pin that selector before loading any checkout code, and discard cached outputs.
unset OFFICIAL_BUILD OUT_DIR_COMMON_BASE DIST_DIR USE_LEFTOVERS BUILD_VAR_CACHE_READY
export TOP="$development_source_root" ANDROID_BUILD_TOP="$development_source_root"
export OUT_DIR="$development_source_root/out"
export BUILD_NUMBER="$development_build_number" BUILD_DATETIME="$development_build_datetime"
source build/envsetup.sh
lunch tegu-cur-userdebug
unset OFFICIAL_BUILD
export TOP="$development_source_root" ANDROID_BUILD_TOP="$development_source_root"
export OUT_DIR="$development_source_root/out"
unset OUT_DIR_COMMON_BASE DIST_DIR USE_LEFTOVERS
export BUILD_NUMBER="$development_build_number" BUILD_DATETIME="$development_build_datetime"

# Development keys must never receive GrapheneOS's production OTA channel.
development_packages="$(get_build_var PRODUCT_PACKAGES)"
[[ -n "${development_packages//[[:space:]]/}" ]] || blocked "cannot resolve PRODUCT_PACKAGES"
development_packages_debug="$(get_build_var PRODUCT_PACKAGES_DEBUG)"
while IFS= read -r package; do
  case "$package" in
    Updater|Updater:*|*:Updater) blocked "resolved PRODUCT_PACKAGES or PRODUCT_PACKAGES_DEBUG includes Updater; exclude it from the development product" ;;
  esac
done < <(printf '%s\n' "$development_packages" "$development_packages_debug" | tr '[:space:]' '\n')

echo "Building development tegu-cur-userdebug artifacts with $development_jobs jobs."
m "-j$development_jobs" target-files-package otatools-package
echo "Development artifacts are in $OUT_DIR/target/product/tegu. No release signing or phone operations performed."
