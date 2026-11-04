"""NVIDIA GPU metrics via NVML, with safe fallback when unavailable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GpuSnapshot:
    available: bool
    name: str
    utilization: float
    memory_used_mb: float
    memory_total_mb: float
    temperature_c: float | None
    message: str = ""


class GpuCollector:
    def __init__(self) -> None:
        self._handle = None
        self._name = ""
        self._init_error = ""
        self._nvml = None
        self._init()

    def _init(self) -> None:
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            count = pynvml.nvmlDeviceGetCount()
            if count < 1:
                self._init_error = "No NVIDIA GPU detected"
                return
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            raw = pynvml.nvmlDeviceGetName(self._handle)
            self._name = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        except ImportError:
            self._init_error = "nvidia-ml-py not installed"
        except Exception as exc:  # noqa: BLE001 — NVML can raise many vendor errors
            self._init_error = f"GPU not available ({exc})"

    def sample(self) -> GpuSnapshot:
        if self._handle is None or self._nvml is None:
            return GpuSnapshot(
                available=False,
                name="",
                utilization=0.0,
                memory_used_mb=0.0,
                memory_total_mb=0.0,
                temperature_c=None,
                message=self._init_error or "GPU not available",
            )

        nvml = self._nvml
        try:
            util = nvml.nvmlDeviceGetUtilizationRates(self._handle)
            mem = nvml.nvmlDeviceGetMemoryInfo(self._handle)
            temp: float | None
            try:
                temp = float(
                    nvml.nvmlDeviceGetTemperature(
                        self._handle, nvml.NVML_TEMPERATURE_GPU
                    )
                )
            except Exception:  # noqa: BLE001
                temp = None

            return GpuSnapshot(
                available=True,
                name=self._name,
                utilization=float(util.gpu),
                memory_used_mb=mem.used / (1024 * 1024),
                memory_total_mb=mem.total / (1024 * 1024),
                temperature_c=temp,
            )
        except Exception as exc:  # noqa: BLE001
            return GpuSnapshot(
                available=False,
                name=self._name,
                utilization=0.0,
                memory_used_mb=0.0,
                memory_total_mb=0.0,
                temperature_c=None,
                message=f"GPU read failed ({exc})",
            )

    def process_vram_mb(self) -> dict[int, float]:
        """GPU memory per process, as NVML reports it.

        Returns a mapping of pid -> megabytes of VRAM.  Used to attribute
        GPU memory to TheCore and Ollama instead of showing the whole card.
        """
        if self._handle is None or self._nvml is None:
            return {}
        nvml = self._nvml
        for getter in (
            "nvmlDeviceGetComputeRunningProcesses_v3",
            "nvmlDeviceGetComputeRunningProcesses_v2",
            "nvmlDeviceGetComputeRunningProcesses",
        ):
            fn = getattr(nvml, getter, None)
            if fn is None:
                continue
            try:
                processes = fn(self._handle)
            except Exception:  # noqa: BLE001
                continue
            result: dict[int, float] = {}
            for proc in processes:
                try:
                    used = getattr(proc, "usedGpuMemory", 0) or 0
                    result[int(proc.pid)] = float(used) / (1024 * 1024)
                except Exception:  # noqa: BLE001
                    continue
            return result
        return {}

    def close(self) -> None:
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:  # noqa: BLE001
                pass
            self._nvml = None
            self._handle = None
