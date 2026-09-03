from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AudioAnalysis:
    positions: dict[str, float]
    activity: float
    level: float


def list_audio_devices() -> list[str]:
    try:
        import sounddevice as sd
    except ImportError:
        return []

    labels = ["System Output", "Default Input"]
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        for index, device in enumerate(devices):
            hostapi_name = hostapis[int(device["hostapi"])] ["name"]
            if device["max_input_channels"] > 0:
                labels.append(f"{index}: {device['name']} ({hostapi_name})")
    except Exception:
        return labels
    return labels


class AudioCapture:
    def __init__(self, device: str = "System Output", sample_rate: int = 44100, blocksize: int = 1024) -> None:
        self.device = device or "System Output"
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self._stream = None
        self._recorder = None
        self._entered = False
        self._backend = "sounddevice"
        if self.device == "System Output":
            self._open_system_output()
            return
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("声音监听需要 sounddevice 依赖，请运行 setup.ps1 安装。") from exc

        self.sd = sd
        stream_device = self._resolve_device()
        self._stream = sd.InputStream(
            device=stream_device,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            dtype="float32",
        )

    def _open_system_output(self) -> None:
        try:
            import soundcard as sc
        except ImportError as exc:
            raise RuntimeError("系统输出监听需要 soundcard 依赖，请运行 setup.ps1 安装。") from exc
        try:
            speaker = sc.default_speaker()
            if speaker is None:
                raise RuntimeError("没有找到默认系统扬声器。")
            loopback = sc.get_microphone(speaker.id, include_loopback=True)
            self._recorder = loopback.recorder(samplerate=self.sample_rate)
            self._backend = "soundcard"
        except Exception as exc:
            raise RuntimeError(f"无法打开系统输出回环: {exc}") from exc

    def _resolve_device(self) -> int | None:
        if self.device == "Default Input":
            return None
        match = re.match(r"^(\d+):", self.device)
        if match:
            return int(match.group(1))
        if self.device != "System Output":
            return self.device
        try:
            default_output = self.sd.query_devices(kind="output")
            default_name = str(default_output["name"]).lower()
            devices = self.sd.query_devices()
            hostapis = self.sd.query_hostapis()
            wasapi = []
            for index, info in enumerate(devices):
                hostapi_name = str(hostapis[int(info["hostapi"])] ["name"])
                if "wasapi" in hostapi_name.lower() and info["max_output_channels"] > 0:
                    wasapi.append((index, str(info["name"])))
            for index, name in wasapi:
                if name.lower() in default_name or default_name in name.lower():
                    return index
            if wasapi:
                return wasapi[0][0]
        except Exception:
            pass
        return None

    def __enter__(self) -> "AudioCapture":
        if self._backend == "soundcard":
            self._recorder.__enter__()
            self._entered = True
        else:
            self._stream.start()
            self._entered = True
        return self

    def read(self) -> tuple[np.ndarray, float]:
        if self._backend == "soundcard":
            data = self._recorder.record(numframes=self.blocksize)
        else:
            data, _overflowed = self._stream.read(self.blocksize)
        samples = np.asarray(data, dtype=np.float32).reshape(-1)
        return samples, len(samples) / float(self.sample_rate)

    def close(self) -> None:
        if self._backend == "soundcard" and self._recorder is not None:
            if self._entered:
                try:
                    self._recorder.__exit__(None, None, None)
                except RuntimeError:
                    pass
            self._recorder = None
        elif self._stream is not None:
            if self._entered:
                self._stream.stop()
            self._stream.close()
            self._stream = None
        self._entered = False

    def __exit__(self, *_: object) -> None:
        self.close()


class AudioAnalyzer:
    def __init__(
        self,
        mode: str = "Audio Level",
        gain: float = 2.5,
        threshold: float = 0.02,
        smoothing: float = 0.25,
    ) -> None:
        self.mode = mode
        self.gain = max(0.1, min(20.0, gain))
        self.threshold = max(0.0, min(1.0, threshold))
        self.smoothing = max(0.0, min(0.98, smoothing))
        self._envelope = 0.0
        self._previous = 0.0
        self._pulse_phase = 1.0

    def process(self, samples: np.ndarray, duration: float) -> AudioAnalysis:
        if samples.size == 0:
            return AudioAnalysis({"L0": 0.5}, 0.0, 0.0)
        rms = float(np.sqrt(np.mean(np.square(samples))))
        level = max(0.0, min(1.0, rms * self.gain))
        gated = max(0.0, min(1.0, (level - self.threshold) / max(0.001, 1.0 - self.threshold)))
        self._envelope = self._envelope * self.smoothing + gated * (1.0 - self.smoothing)
        onset = max(0.0, self._envelope - self._previous)
        self._previous = self._envelope
        mode = self.mode.lower()
        if mode.startswith("beat"):
            if onset > 0.025:
                self._pulse_phase = 0.0
            self._pulse_phase = min(1.0, self._pulse_phase + duration * 3.2)
            pulse = max(0.0, 1.0 - self._pulse_phase)
            position = 0.5 + min(0.48, pulse * (0.18 + self._envelope * 0.8))
            activity = max(self._envelope, onset * 3.0)
        elif mode.startswith("dynamic"):
            position = 0.5 + min(0.48, self._envelope * 0.96)
            activity = max(self._envelope, onset * 2.0)
        else:
            position = self._envelope
            activity = self._envelope
        return AudioAnalysis({"L0": max(0.0, min(1.0, position))}, activity, level)
