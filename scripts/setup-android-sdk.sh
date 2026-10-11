#!/usr/bin/env bash
# Installs build tools only; never touches a phone. sdkmanager displays licenses.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_root="${ANDROID_HOME:-$project_root/.sdk}"
export ANDROID_USER_HOME="${ANDROID_USER_HOME:-$project_root/.android}"
mkdir -p "$sdk_root/cmdline-tools" "$ANDROID_USER_HOME"
sdk_root="$(cd "$sdk_root" && pwd)"
version=11076708
sha256=2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258
if [[ ! -x "$sdk_root/cmdline-tools/12.0/bin/sdkmanager" ]]; then
  task_dir="$(mktemp -d)"
  trap 'rm -rf "$task_dir"' EXIT
  curl --fail --location --proto '=https' --tlsv1.2 \
    "https://dl.google.com/android/repository/commandlinetools-linux-${version}_latest.zip" \
    --output "$task_dir/tools.zip"
  printf '%s  %s\n' "$sha256" "$task_dir/tools.zip" | sha256sum --check --status
  unzip -q "$task_dir/tools.zip" -d "$task_dir/unpacked"
  mv "$task_dir/unpacked/cmdline-tools" "$sdk_root/cmdline-tools/12.0"
fi

# sdkmanager's Java HTTP client does not consume HTTPS_PROXY automatically.
# Preserve TLS validation and use the configured proxy; do not discover secrets.
proxy_args=()
if [[ -n "${HTTPS_PROXY:-${https_proxy:-}}" ]]; then
  mapfile -t proxy_fields < <(python3 - <<'PY'
import os, urllib.parse
p = urllib.parse.urlsplit(os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy', ''))
if p.scheme != 'http' or not p.hostname or p.username or p.password:
    print('unsupported')
else:
    print(p.hostname)
    print(p.port or 80)
PY
)
  [[ "${#proxy_fields[@]}" == 2 ]] || {
    echo 'Configure the Java proxy securely: this bootstrap supports credential-free HTTP CONNECT proxy URLs.' >&2
    exit 1
  }
  proxy_args=(--proxy=http "--proxy_host=${proxy_fields[0]}" "--proxy_port=${proxy_fields[1]}")
fi
"$sdk_root/cmdline-tools/12.0/bin/sdkmanager" --sdk_root="$sdk_root" \
  "${proxy_args[@]}" 'platforms;android-35' 'build-tools;35.0.0'
printf 'SDK ready at %s\nSet ANDROID_HOME to this path before building.\n' "$sdk_root"
