#!/usr/bin/env bash
# Build only. Never signs, publishes, flashes, unlocks or changes a phone.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 CHECKOUT [--emergency] [--generated-inventory FILE --artifacts DIR]" >&2
  exit 2
fi
source_root="$(realpath "$1")"
shift
# Before sourcing any checkout code, authenticate exact pinned source, selected
# patches, index/worktree bytes and every manifest copyfile/linkfile output.
verify_args=(verify-tree --source "$source_root")
have_inventory=false
have_artifacts=false
have_emergency=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --emergency)
      if $have_emergency; then echo "Duplicate --emergency" >&2; exit 2; fi
      have_emergency=true
      verify_args+=(--emergency)
      shift
      ;;
    --generated-inventory|--artifacts)
      option="$1"
      if [[ $# -lt 2 || "$2" == --* ]]; then echo "Missing value for $option" >&2; exit 2; fi
      if [[ "$option" == --generated-inventory ]]; then
        if $have_inventory; then echo "Duplicate $option" >&2; exit 2; fi
        have_inventory=true
      else
        if $have_artifacts; then echo "Duplicate $option" >&2; exit 2; fi
        have_artifacts=true
      fi
      verify_args+=("$option" "$(realpath "$2")")
      shift 2
      ;;
    *) echo "Unknown build option: $1" >&2; exit 2 ;;
  esac
done
if [[ "$have_inventory" != "$have_artifacts" ]]; then
  echo "Use --generated-inventory and --artifacts together" >&2
  exit 2
fi
python3 "$project_root/scripts/os-pipeline.py" "${verify_args[@]}"
python3 - "$project_root/os/upstream-lock.json" "$source_root" <<'PY'
import json, pathlib, shutil, sys, xml.etree.ElementTree as ET
lock = json.loads(pathlib.Path(sys.argv[1]).read_text())
root = pathlib.Path(sys.argv[2])
memory = int(next(line.split()[1] for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))) * 1024
for limit_path in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
    candidate = pathlib.Path(limit_path)
    if candidate.exists() and candidate.read_text().strip().isdigit():
        memory = min(memory, int(candidate.read_text().strip()))
if memory < 64 * 1024**3 or shutil.disk_usage(root).free < 400 * 1024**3:
    raise SystemExit('BLOCKED: need at least 64 GiB RAM and 400 GiB free disk on dedicated runner')
if (root / 'out').exists():
    raise SystemExit('BLOCKED: production build requires a fresh output tree; archive old outputs separately')
config = ET.parse(root / 'packages/apps/Updater/res/values/config.xml')
urls = [element.text.strip() for element in config.iter() if element.text and element.text.strip().startswith('https://')]
if lock['update_url'] not in urls or any('releases.grapheneos.org' in url for url in urls):
    raise SystemExit('BLOCKED: own updater URL must be applied and official release endpoint removed')
PY
cd "$source_root"
# The pinned release's adevtool definitions select the matching Pixel factory image.
# Run and archive their extraction logs and hash checks before this build command.
# envsetup sources shell_utils from TOP before discovering the working directory.
# An inherited TOP must never redirect execution away from the verified checkout.
export TOP="$source_root" ANDROID_BUILD_TOP="$source_root"
unset USE_LEFTOVERS BUILD_VAR_CACHE_READY OUT_DIR_COMMON_BASE DIST_DIR
export OUT_DIR="$source_root/out"
source build/envsetup.sh
lunch tegu-cur-user
export OFFICIAL_BUILD=true
: "${BUILD_NUMBER:?Set a reviewed, monotonic distribution BUILD_NUMBER}"
: "${BUILD_DATETIME:?Set the recorded Unix timestamp for reproducibility}"
export BUILD_NUMBER BUILD_DATETIME
m -j16 target-files-package otatools-package
script/finalize.sh
echo "Unsigned build artifacts finalized. Offline signing and all release gates remain required."
