"""Mute / unmute all Windows microphone (capture) endpoints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MicActionResult:
    ok: bool
    muted: bool
    count: int
    message: str


class MicController:
    """Controls all active capture endpoints via Windows Core Audio (pycaw)."""

    def all_muted(self) -> bool | None:
        volumes = self._capture_volumes()
        if volumes is None:
            return None
        if not volumes:
            return False
        try:
            return all(bool(v.GetMute()) for v in volumes)
        except Exception:  # noqa: BLE001
            return None

    def set_all_muted(self, muted: bool) -> MicActionResult:
        volumes = self._capture_volumes()
        if volumes is None:
            return MicActionResult(
                ok=False,
                muted=False,
                count=0,
                message="Mic control unavailable",
            )
        if not volumes:
            return MicActionResult(
                ok=False,
                muted=False,
                count=0,
                message="No microphones found",
            )

        failed = 0
        for volume in volumes:
            try:
                volume.SetMute(1 if muted else 0, None)
            except Exception:  # noqa: BLE001
                failed += 1

        ok = failed == 0
        state = "MUTED" if muted else "LIVE"
        if ok:
            message = f"ALL MICS {state} ({len(volumes)})"
        else:
            message = f"MIC {state} · {failed} ERROR(S)"
        return MicActionResult(
            ok=ok, muted=muted, count=len(volumes), message=message
        )

    def toggle_all(self) -> MicActionResult:
        current = self.all_muted()
        # Mixed/unknown -> mute for safety
        target_mute = current is not True
        return self.set_all_muted(target_mute)

    @staticmethod
    def _capture_volumes() -> list | None:
        try:
            from pycaw.constants import DEVICE_STATE, EDataFlow
            from pycaw.pycaw import AudioUtilities
        except ImportError:
            return None

        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            collection = enumerator.EnumAudioEndpoints(
                EDataFlow.eCapture.value,
                DEVICE_STATE.ACTIVE.value,
            )
            volumes = []
            for i in range(collection.GetCount()):
                device = AudioUtilities.CreateDevice(collection.Item(i))
                if device is None or device.EndpointVolume is None:
                    continue
                volumes.append(device.EndpointVolume)
            return volumes
        except Exception:  # noqa: BLE001
            return []
