from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading

_PROC_STAT = Path("/proc/stat")
_PROC_MEMINFO = Path("/proc/meminfo")

_SNAPSHOT_LOCK = threading.Lock()


@dataclass(frozen=True)
class _CpuTimes:
    total: int
    idle: int


@dataclass(frozen=True)
class _CpuSnapshot:
    total: _CpuTimes
    cores: tuple[_CpuTimes, ...]


_CPU_SNAPSHOTS: dict[str, _CpuSnapshot] = {}


def _read_memory_from_proc(path: Path) -> tuple[int, int]:
    memory_kib: dict[str, int] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, _, raw_value = line.partition(":")
        parts = raw_value.strip().split()
        if not parts:
            continue
        value = int(parts[0])
        unit = parts[1].lower() if len(parts) > 1 else "kb"
        if unit != "kb":
            raise ValueError(f"unsupported /proc/meminfo unit '{unit}' for {key}")
        memory_kib[key] = value

    total_kib = memory_kib.get("MemTotal")
    available_kib = memory_kib.get("MemAvailable")
    if total_kib is None or available_kib is None:
        raise ValueError("/proc/meminfo missing MemTotal or MemAvailable")
    if total_kib <= 0:
        raise ValueError("invalid MemTotal in /proc/meminfo")

    available_kib = max(0, min(available_kib, total_kib))
    used_kib = total_kib - available_kib

    total_bytes = total_kib * 1024
    used_bytes = used_kib * 1024
    return used_bytes, total_bytes


def _parse_cpu_times(parts: list[str]) -> _CpuTimes:
    if len(parts) < 5:
        raise ValueError("invalid /proc/stat cpu line")
    values = [int(value) for value in parts[1:]]
    total = sum(values)
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    if total <= 0:
        raise ValueError("invalid /proc/stat cpu counters")
    return _CpuTimes(total=total, idle=idle)


def _read_cpu_snapshot(path: Path) -> _CpuSnapshot:
    total: _CpuTimes | None = None
    per_core: dict[int, _CpuTimes] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("cpu"):
            continue
        parts = line.split()
        if not parts:
            continue
        label = parts[0]
        if label == "cpu":
            total = _parse_cpu_times(parts)
            continue
        if not label.startswith("cpu"):
            continue
        core_id_raw = label[3:]
        if not core_id_raw.isdigit():
            continue
        per_core[int(core_id_raw)] = _parse_cpu_times(parts)

    if total is None:
        raise ValueError("/proc/stat does not contain aggregate cpu line")
    if not per_core:
        raise ValueError("/proc/stat does not contain per-core cpu lines")

    cores = tuple(per_core[index] for index in sorted(per_core))
    return _CpuSnapshot(total=total, cores=cores)


def _percent_from_deltas(current: _CpuTimes, previous: _CpuTimes) -> float:
    delta_total = current.total - previous.total
    delta_idle = current.idle - previous.idle
    if delta_total <= 0:
        return 0.0
    busy = delta_total - delta_idle
    if busy <= 0:
        return 0.0
    return max(0.0, min(100.0, (busy / delta_total) * 100.0))


def _compute_cpu_percent(server_id: str, snapshot: _CpuSnapshot) -> tuple[float, list[float]]:
    with _SNAPSHOT_LOCK:
        previous = _CPU_SNAPSHOTS.get(server_id)
        _CPU_SNAPSHOTS[server_id] = snapshot

    if previous is None:
        return 0.0, [0.0] * len(snapshot.cores)

    if len(previous.cores) != len(snapshot.cores):
        return 0.0, [0.0] * len(snapshot.cores)

    total_percent = _percent_from_deltas(snapshot.total, previous.total)
    per_core_percent = [
        _percent_from_deltas(current, prev)
        for current, prev in zip(snapshot.cores, previous.cores)
    ]
    return total_percent, per_core_percent


def read_runtime_stats(server_id: str) -> dict[str, object]:
    try:
        memory_used, memory_limit = _read_memory_from_proc(_PROC_MEMINFO)
        cpu_snapshot = _read_cpu_snapshot(_PROC_STAT)
    except Exception as error:  # noqa: BLE001
        return {"available": False, "error": str(error)}

    cpu_percent, cpu_cores_percent = _compute_cpu_percent(server_id, cpu_snapshot)
    cpu_cores_total = len(cpu_cores_percent)
    cpu_used_cores = (cpu_percent / 100.0) * cpu_cores_total if cpu_cores_total > 0 else 0.0
    memory_percent = (memory_used / memory_limit) * 100.0 if memory_limit > 0 else None

    return {
        "available": True,
        "cpu_percent": cpu_percent,
        "cpu_cores_total": cpu_cores_total,
        "cpu_cores_percent": cpu_cores_percent,
        "cpu_used_cores": cpu_used_cores,
        "memory_used_bytes": memory_used,
        "memory_limit_bytes": memory_limit,
        "memory_percent": memory_percent,
    }
