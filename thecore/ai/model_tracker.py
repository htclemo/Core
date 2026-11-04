"""Track GPU VRAM and system RAM before/after an LLM is loaded by Ollama.

Shows both absolute memory usage and the delta caused by loading a model.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

import psutil

from thecore.collectors.gpu import GpuCollector


@dataclass
class ModelMemorySnapshot:
    """Memory state at a single point in time."""

    timestamp: float
    system_ram_used_gb: float
    system_ram_total_gb: float
    system_ram_available_gb: float
    system_ram_percent: float
    gpu_available: bool
    gpu_name: str
    gpu_vram_used_mb: float
    gpu_vram_total_mb: float
    gpu_vram_percent: float
    gpu_utilization: float


@dataclass
class ModelMemoryDelta:
    """Delta between before and after loading a model."""

    model_name: str
    model_size_gb: float
    system_ram_delta_gb: float
    gpu_vram_delta_mb: float
    gpu_available: bool
    gpu_name: str
    gpu_vram_total_mb: float
    before: ModelMemorySnapshot
    after: ModelMemorySnapshot

    @property
    def system_ram_delta_mb(self) -> float:
        return self.system_ram_delta_gb * 1024.0

    @property
    def gpu_vram_delta_gb(self) -> float:
        return self.gpu_vram_delta_mb / 1024.0


class ModelTracker:
    """Samples system RAM and GPU VRAM around an LLM load."""

    def __init__(self) -> None:
        self._gpu = GpuCollector()

    @property
    def gpu(self) -> GpuCollector:
        """The shared GPU collector (NVML must only be initialised once)."""
        return self._gpu

    def snapshot(self) -> ModelMemorySnapshot:
        mem = psutil.virtual_memory()
        gpu = self._gpu.sample()
        gpu_vram_pct = 0.0
        if gpu.memory_total_mb > 0:
            gpu_vram_pct = (gpu.memory_used_mb / gpu.memory_total_mb) * 100.0
        return ModelMemorySnapshot(
            timestamp=time.monotonic(),
            system_ram_used_gb=mem.used / (1024**3),
            system_ram_total_gb=mem.total / (1024**3),
            system_ram_available_gb=mem.available / (1024**3),
            system_ram_percent=float(mem.percent),
            gpu_available=gpu.available,
            gpu_name=gpu.name,
            gpu_vram_used_mb=gpu.memory_used_mb,
            gpu_vram_total_mb=gpu.memory_total_mb,
            gpu_vram_percent=gpu_vram_pct,
            gpu_utilization=gpu.utilization,
        )

    def measure_load(
        self, model_name: str, model_size_gb: float, load_call
    ) -> ModelMemoryDelta:
        """Run `load_call()` while sampling memory before and after.

        `load_call` triggers Ollama to load the model (e.g. first chat request).
        Returns a ModelMemoryDelta with absolute and delta values.
        """
        before = self.snapshot()
        time.sleep(0.3)  # let counters settle

        load_call()

        # Ollama loads the model on first request; wait for it to settle in VRAM/RAM
        time.sleep(1.0)
        after = self.snapshot()

        return ModelMemoryDelta(
            model_name=model_name,
            model_size_gb=model_size_gb,
            system_ram_delta_gb=after.system_ram_used_gb - before.system_ram_used_gb,
            gpu_vram_delta_mb=after.gpu_vram_used_mb - before.gpu_vram_used_mb,
            gpu_available=after.gpu_available,
            gpu_name=after.gpu_name,
            gpu_vram_total_mb=after.gpu_vram_total_mb,
            before=before,
            after=after,
        )

    def close(self) -> None:
        self._gpu.close()
