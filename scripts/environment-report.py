#!/usr/bin/env python3
"""Print capacity and tool availability only; never dump environment or secrets."""
import json
import os
from pathlib import Path
import platform
import shutil


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


root = Path(__file__).resolve().parents[1]
memory = dict(line.split(':', 1) for line in (read('/proc/meminfo') or '').splitlines())
host_ram = int(memory.get('MemTotal', '0 kB').strip().split()[0]) * 1024
limit = read('/sys/fs/cgroup/memory.max')
effective_ram = min(host_ram, int(limit)) if limit and limit.isdecimal() else host_ram
cpu_max = read('/sys/fs/cgroup/cpu.max')
quota = None
if cpu_max and not cpu_max.startswith('max'):
    amount, period = map(int, cpu_max.split())
    quota = amount / period
print(json.dumps({
    'system': platform.system(),
    'architecture': platform.machine(),
    'logical_cpus': os.cpu_count(),
    'affinity_cpus': len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
    'cpu_quota_cores': quota,
    'effective_ram_gib': round(effective_ram / 1024**3, 2),
    'workspace_free_gib': round(shutil.disk_usage(root).free / 1024**3, 2),
    'kvm_available': os.access('/dev/kvm', os.R_OK | os.W_OK),
    'kvm_required_for_compilation': False,
    'tools': {name: shutil.which(name) for name in ['python3', 'java', 'javac', 'git', 'repo', 'sdkmanager', 'adb']},
}, indent=2))
