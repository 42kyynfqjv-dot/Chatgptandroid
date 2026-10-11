#!/usr/bin/env bash
# Build only. Never signs, publishes, flashes, unlocks or changes a phone.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 || $# -gt 2 || ( $# -eq 2 && "$2" != "--emergency" ) ]]; then
  echo "Usage: $0 /srv/android/verified-patched-checkout [--emergency]" >&2
  exit 2
fi
source_root="$(realpath "$1")"
# Before sourcing any checkout code, authenticate exact pinned source, selected
# patches, index/worktree bytes and every manifest copyfile/linkfile output.
verify_args=(verify-tree --source "$source_root")
if [[ $# -eq 2 ]]; then verify_args+=(--emergency); fi
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
source build/envsetup.sh
lunch tegu-cur-user
export OFFICIAL_BUILD=true
: "${BUILD_NUMBER:?Set a reviewed, monotonic distribution BUILD_NUMBER}"
: "${BUILD_DATETIME:?Set the recorded Unix timestamp for reproducibility}"
export BUILD_NUMBER BUILD_DATETIME
m -j16 target-files-package otatools-package
script/finalize.sh
echo "Unsigned build artifacts finalized. Offline signing and all release gates remain required."
