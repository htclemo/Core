"""Memory used by TheCore and Ollama — not by the whole machine.

The chat header shows two slim gauges.  They used to report the *total* system
RAM and VRAM, which is noise: what matters for this application is how much
memory TheCore itself and the Ollama server (plus the model runner) occupy.

This collector therefore sums:

* the resident set size of every Ollama process (server, app and runner), and
* the resident set size of TheCore's own process, and
* the GPU memory that NVML attributes to exactly those processes.

The percentages stay relative to the machine's capacity, so the bars remain
interpretable, but the *amounts* shown are only TheCore's and Ollama's.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

import psutil

from thecore.collectors.gpu import GpuCollector


@dataclass(frozen=True)
class AiMemorySnapshot:
    """Memory used by TheCore and Ollama only."""

    thecore_ram_gb: float
    ollama_ram_gb: float
    total_ram_gb: float
    thecore_vram_mb: float
    ollama_vram_mb: float
    total_vram_mb: float
    ram_capacity_gb: float
    vram_capacity_mb: float
    ollama_processes: int
    gpu_available: bool

    @property
    def ram_percent(self) -> float:
        if self.ram_capacity_gb <= 0:
            return 0.0
        return (self.total_ram_gb / self.ram_capacity_gb) * 100.0

    @property
    def vram_percent(self) -> float:
        if self.vram_capacity_mb <= 0:
            return 0.0
        return (self.total_vram_mb / self.vram_capacity_mb) * 100.0


def _is_ollama(name: str, cmdline: str = "") -> bool:
    """True for the Ollama server, the tray app and the model runner.

    On Windows the runner is called ``ollama.exe`` too, so the process *name*
    is enough.  The command line is not read on purpose: asking every process
    for its command line is by far the most expensive thing this collector
    could do.
    """
    return "ollama" in name.lower()


def ollama_vram_bytes(host: str = "127.0.0.1", port: int = 11434) -> int:
    """VRAM that Ollama currently holds for loaded models.

    On Windows the model runner lives *inside* ``ollama.exe`` and WDDM does
    not report per-process GPU memory, so NVML cannot attribute the VRAM.
    The Ollama API does know: ``/api/ps`` lists every loaded model with the
    amount of video memory it occupies.
    """
    url = f"http://{host}:{port}/api/ps"
    try:
        with urllib.request.urlopen(url, timeout=0.4) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return 0

    total = 0
    for model in payload.get("models") or []:
        try:
            total += int(model.get("size_vram") or 0)
        except (TypeError, ValueError):
            continue
    return total


class AiMemoryCollector:
    """Samples the memory that TheCore and Ollama are using."""

    def __init__(self, gpu: Optional[GpuCollector] = None) -> None:
        self._gpu = gpu
        self._self_pid = os.getpid()

    # ------------------------------------------------------------------ sample

    def sample(self) -> AiMemorySnapshot:
        ollama_pids: set[int] = set()
        ollama_ram_bytes = 0
        ollama_count = 0

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info["name"] or ""
                if "ollama" not in name.lower():
                    continue
                ollama_pids.add(int(proc.info["pid"]))
                ollama_count += 1
                mem = proc.memory_info()
                ollama_ram_bytes += int(mem.rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # TheCore's own footprint.
        thecore_ram_bytes = 0
        try:
            thecore_ram_bytes = int(psutil.Process(self._self_pid).memory_info().rss)
        except Exception:  # noqa: BLE001
            pass

        # GPU memory.  Ollama's own API is the reliable source on Windows
        # (the runner is part of ollama.exe and WDDM hides the per-process
        # numbers); NVML per-process is only a fallback.
        vram_by_pid: dict[int, float] = {}
        capacity_mb = 0.0
        gpu_available = False
        if self._gpu is not None:
            try:
                vram_by_pid = self._gpu.process_vram_mb()
                gpu = self._gpu.sample()
                gpu_available = gpu.available
                capacity_mb = gpu.memory_total_mb
            except Exception:  # noqa: BLE001
                vram_by_pid = {}

        ollama_vram_mb = ollama_vram_bytes() / (1024 * 1024)
        if ollama_vram_mb <= 0:
            # Fall back to what NVML attributes to the Ollama processes.
            ollama_vram_mb = sum(vram_by_pid.get(pid, 0.0) for pid in ollama_pids)
        thecore_vram = vram_by_pid.get(self._self_pid, 0.0)

        ram_capacity = psutil.virtual_memory().total / (1024 ** 3)
        gb = 1024 ** 3

        return AiMemorySnapshot(
            thecore_ram_gb=thecore_ram_bytes / gb,
            ollama_ram_gb=ollama_ram_bytes / gb,
            total_ram_gb=(thecore_ram_bytes + ollama_ram_bytes) / gb,
            thecore_vram_mb=thecore_vram,
            ollama_vram_mb=ollama_vram_mb,
            total_vram_mb=ollama_vram_mb + thecore_vram,
            ram_capacity_gb=ram_capacity,
            vram_capacity_mb=capacity_mb,
            ollama_processes=ollama_count,
            gpu_available=gpu_available,
        )

    def close(self) -> None:
        if self._gpu is not None:
            self._gpu.close()
