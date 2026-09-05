"""Capability-based Intiface output, downstream of the existing safe TCode mapper.

Wire format: https://buttplug.io/docs/spec-v3/spec/
Only the explicitly selected device feature receives commands.
"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
import json
import math
import re
import threading
import time
from urllib.parse import urlsplit

from . import APP_NAME


DEVICE_FAMILIES = {
    "tcode": "OSR / SR6/OSR6 (TCode)",
    "custom": "Custom (Intiface)",
    "ossm": "OSSM (TCode firmware)",
    "intiface": "Intiface / Buttplug",
    "handy": "The Handy",
    "lovense": "Lovense",
    "kiiroo": "Kiiroo / FeelTechnology",
    "vorze": "Vorze",
    "wevibe": "We-Vibe",
    "satisfyer": "Satisfyer",
    "mysteryvibe": "MysteryVibe",
    "motorbunny": "Motorbunny",
    "autoblow": "Autoblow",
}
NATIVE_FAMILIES = {"tcode", "ossm"}
DEFAULT_INTIFACE_URL = "ws://127.0.0.1:12345"
_TOKEN = re.compile(r"([LR][0-2])(\d{4})(?:I(\d+))?")
_SCALAR_TYPES = {"Vibrate", "Oscillate", "Rotate", "Constrict", "Inflate"}


def normalized(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite output value")
    return max(0.0, min(1.0, value))


def validate_server_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Intiface URL must be ws://host:port or wss://host:port (no credentials)")
    if parsed.query or parsed.fragment:
        raise ValueError("Intiface URL must not contain a query or fragment")
    return url.strip()


@dataclass(frozen=True)
class DeviceFeature:
    command: str
    index: int
    actuator: str
    description: str

    @property
    def key(self) -> str:
        return f"{self.command}:{self.index}:{self.actuator}"


@dataclass(frozen=True)
class IntifaceDevice:
    index: int
    name: str
    display_name: str
    timing_gap_ms: int
    features: tuple[DeviceFeature, ...]

    @property
    def identity(self) -> tuple[str, str]:
        return self.name, self.display_name

    @classmethod
    def from_message(cls, data: dict) -> "IntifaceDevice":
        features = []
        messages = data.get("DeviceMessages", {})
        for command in ("LinearCmd", "RotateCmd", "ScalarCmd"):
            for index, attr in enumerate(messages.get(command, [])):
                actuator = attr.get("ActuatorType", "")
                if command == "ScalarCmd" and actuator not in _SCALAR_TYPES:
                    continue
                features.append(DeviceFeature(command, index, actuator, attr.get("FeatureDescriptor", "")))
        return cls(int(data["DeviceIndex"]), str(data["DeviceName"]),
                   str(data.get("DeviceDisplayName") or ""),
                   max(0, int(data.get("DeviceMessageTimingGap", 0))), tuple(features))


class ButtplugClient:
    """One receiver routes correlated replies, hotplug events and heartbeat errors."""

    def __init__(self, url: str) -> None:
        self.url = validate_server_url(url)
        self.devices: dict[int, IntifaceDevice] = {}
        self.removed: set[int] = set()
        self.error: Exception | None = None
        self.ws = None
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 0
        self._receiver = None
        self._heartbeat = None

    async def open(self) -> None:
        # The legacy connector is supported by the project's websockets>=12 dependency.
        from websockets.legacy.client import connect

        self.ws = await connect(self.url, open_timeout=3, close_timeout=0.5,
                                ping_interval=None, max_size=1024 * 1024)
        self._receiver = asyncio.create_task(self._receive())
        try:
            kind, info = await self.request("RequestServerInfo", ClientName=APP_NAME, MessageVersion=3)
            if kind != "ServerInfo" or info.get("MessageVersion") != 3:
                raise RuntimeError("Intiface server must support Buttplug protocol v3")
            ping_ms = int(info.get("MaxPingTime", 0))
            if ping_ms > 0:
                self._heartbeat = asyncio.create_task(self._ping(max(0.01, ping_ms / 2500)))
            kind, data = await self.request("RequestDeviceList")
            if kind != "DeviceList":
                raise RuntimeError("Intiface did not return a device list")
        except BaseException:
            await self.close()
            raise

    async def request(self, kind: str, **body) -> tuple[str, dict]:
        if self.error:
            raise self.error
        self._next_id += 1
        ident = self._next_id
        future = asyncio.get_running_loop().create_future()
        self._pending[ident] = future
        try:
            await self.ws.send(json.dumps([{kind: {"Id": ident, **body}}]))
            return await asyncio.wait_for(future, timeout=1.5)
        finally:
            self._pending.pop(ident, None)

    async def _receive(self) -> None:
        try:
            async for payload in self.ws:
                batch = json.loads(payload)
                if not isinstance(batch, list):
                    raise ValueError("Invalid Intiface message")
                for message in batch:
                    kind, data = next(iter(message.items()))
                    if kind == "DeviceList":
                        self.devices = {int(d["DeviceIndex"]): IntifaceDevice.from_message(d) for d in data["Devices"]}
                    elif kind == "DeviceAdded":
                        device = IntifaceDevice.from_message(data)
                        self.devices[device.index] = device
                    elif kind == "DeviceRemoved":
                        index = int(data["DeviceIndex"])
                        self.removed.add(index)
                        self.devices.pop(index, None)
                    future = self._pending.get(data.get("Id"))
                    if kind == "Error":
                        # Do not echo arbitrary remote text (it can contain local device identifiers).
                        error = RuntimeError(f"Intiface rejected command (code {data.get('ErrorCode', '?')})")
                        if future is None:
                            raise error
                        if not future.done():
                            future.set_exception(error)
                    elif future is not None and not future.done():
                        future.set_result((kind, data))
            raise ConnectionError("Intiface disconnected")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = exc
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(exc)

    async def _ping(self, period: float) -> None:
        try:
            while True:
                await asyncio.sleep(period)
                await self.request("Ping")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = exc

    async def close(self) -> None:
        for task in (self._heartbeat, self._receiver):
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
        if self.ws:
            await self.ws.close()
            self.ws = None


async def discover_devices(url: str, scan_seconds: float = 4.0) -> list[IntifaceDevice]:
    client = ButtplugClient(url)
    try:
        await client.open()
        await client.request("StartScanning")
        try:
            await asyncio.sleep(scan_seconds)
        finally:
            await client.request("StopScanning")
        kind, _ = await client.request("RequestDeviceList")
        if kind != "DeviceList":
            raise RuntimeError("Intiface did not return a device list")
        return list(client.devices.values())
    finally:
        await client.close()


class FeatureMapper:
    """Linear features follow position. Speed/intensity features follow motion speed."""

    def __init__(self, feature: DeviceFeature, axis: str, limit: float, gap_ms: int) -> None:
        if axis not in {"L0", "L1", "L2", "R0", "R1", "R2"}:
            raise ValueError("Invalid source axis")
        self.feature = feature
        self.axis = axis
        self.limit = normalized(limit)
        self.gap_ms = max(50, gap_ms)
        self._previous: tuple[float, float] | None = None
        self._linear_state: tuple[float, float, float, float, float] | None = None

    @staticmethod
    def parse_positions(payload: bytes) -> dict[str, tuple[int, int]]:
        parsed = {}
        for token in payload.decode("ascii").split():
            match = _TOKEN.fullmatch(token)
            if not match:
                raise ValueError("External output accepts limited four-digit TCode positions only")
            parsed[match[1]] = (int(match[2]), max(1, min(10000, int(match[3] or 20))))
        return parsed

    def command(self, payload: bytes, now: float) -> tuple[str, dict] | None:
        return self.command_from_positions(self.parse_positions(payload), now)

    def command_from_positions(self, parsed: dict, now: float) -> tuple[str, dict] | None:
        if self.axis not in parsed:
            return None
        value, interval = parsed[self.axis]
        position = normalized(value / 9999)
        previous = self._previous
        self._previous = (position, now)
        delta = position - previous[0] if previous else 0.0
        dt = max(self.gap_ms / 1000, now - previous[1]) if previous else 0.05
        velocity = max(-1.0, min(1.0, delta / dt))
        level = min(self.limit, abs(velocity))
        if abs(delta) < 0.001:
            level = 0.0
        f = self.feature
        if f.command == "LinearCmd":
            if self.limit <= 0:
                return None
            # First target uses a full-stroke duration because initial physical position is unknown.
            low, high = 0.0, 1.0
            if self._linear_state is not None:
                low, high, target, started, duration_s = self._linear_state
                progress = normalized((now - started) / duration_s)
                low += (target - low) * progress
                high += (target - high) * progress
            distance = max(abs(position - low), abs(position - high))
            duration = max(interval, self.gap_ms, math.ceil(1000 * distance / self.limit))
            self._linear_state = (low, high, position, now, duration / 1000)
            return "LinearCmd", {"Vectors": [{"Index": f.index, "Position": position, "Duration": duration}]}
        if f.command == "RotateCmd":
            return "RotateCmd", {"Rotations": [{"Index": f.index, "Speed": level, "Clockwise": velocity >= 0}]}
        if f.command == "ScalarCmd":
            if f.actuator not in _SCALAR_TYPES:
                raise ValueError("Unsupported scalar output type")
            return "ScalarCmd", {"Scalars": [{"Index": f.index, "Scalar": level, "ActuatorType": f.actuator}]}
        raise ValueError("Unsupported device feature")


class DeviceMapper:
    """Group same-type features; rotate groups using fresh input at each device gap."""

    def __init__(self, device: IntifaceDevice, bindings: dict[str, str], limit: float) -> None:
        if not 1 <= len(bindings) <= 6:
            raise ValueError("Bind at least one axis, up to six")
        if len(set(bindings.values())) != len(bindings):
            raise ValueError("A device function cannot be bound to multiple axes")
        features = {f.key: f for f in device.features}
        self.groups: dict[str, list[FeatureMapper]] = {}
        self.axes = tuple(bindings)
        self.gap_ms = max(50, device.timing_gap_ms)
        for axis, key in bindings.items():
            if key not in features:
                raise ValueError("Select a supported device feature")
            feature = features[key]
            self.groups.setdefault(feature.command, []).append(FeatureMapper(feature, axis, limit, self.gap_ms))
        self.reset()

    def reset(self) -> None:
        self._next_group = 0
        self._processed: dict[str, float] = {}
        self.missing_axes = False
        for group in self.groups.values():
            for mapper in group:
                mapper._previous = None
                mapper._linear_state = None

    def command(self, payload: bytes, now: float, sample_time: float) -> tuple[str, dict] | None:
        parsed = FeatureMapper.parse_positions(payload)
        self.missing_axes = not all(axis in parsed for axis in self.axes)
        if self.missing_axes:
            return None
        kinds = tuple(self.groups)
        for _ in kinds:
            kind = kinds[self._next_group]
            self._next_group = (self._next_group + 1) % len(kinds)
            if self._processed.get(kind) == sample_time:
                continue
            self._processed[kind] = sample_time
            body = {}
            for mapper in self.groups[kind]:
                command = mapper.command_from_positions(parsed, now)
                if command:
                    for key, values in command[1].items():
                        body.setdefault(key, []).extend(values)
            if body:
                return kind, body
        return None


class IntifaceSink:
    """Latest-frame mailbox; network work never runs in Tk or the analysis thread."""

    def __init__(self, url: str, device: IntifaceDevice, feature_key: str = "",
                 axis: str = "L0", limit: float = 0.2, *, bindings: dict[str, str] | None = None) -> None:
        self.url = validate_server_url(url)
        self.device = device
        self.feature_key = feature_key
        self.axis = axis
        self.limit = normalized(limit)
        self.bindings = dict(bindings) if bindings is not None else {axis: feature_key}
        self.axes = tuple(self.bindings)
        DeviceMapper(device, self.bindings, self.limit)
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._paused = False
        self._stop_requested = False
        self._latest: tuple[bytes, float] | None = None
        self._error: Exception | None = None
        self._thread: threading.Thread | None = None

    @property
    def error(self) -> Exception | None:
        return self._error

    def open(self) -> None:
        self._thread = threading.Thread(target=self._run, name="intiface-output", daemon=True)
        self._thread.start()
        if not self._ready.wait(8):
            self.close()
            raise TimeoutError("Intiface connection timed out")
        if self._error:
            raise self._error

    def write(self, payload: bytes) -> None:
        if self._error:
            raise self._error
        if self._closed.is_set():
            raise ConnectionError("Intiface output is closed")
        with self._lock:
            if not self._paused:
                self._latest = (payload, time.monotonic())

    def stop_output(self) -> None:
        with self._lock:
            self._paused = True
            self._latest = None
            self._stop_requested = True

    def resume_output(self) -> None:
        if self._error or self._closed.is_set():
            raise ConnectionError("Reconnect the Intiface device before output")
        with self._lock:
            self._paused = False

    def close(self) -> None:
        self.stop_output()
        self._closed.set()
        # Shutdown remains bounded even if the server no longer acknowledges commands.
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.8)

    def _run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as exc:
            self._error = exc
        finally:
            self._ready.set()

    async def _run_async(self) -> None:
        client = ButtplugClient(self.url)
        selected = None
        try:
            await client.open()
            # Never trust an index retained across Intiface sessions.
            matches = [d for d in client.devices.values() if d.identity == self.device.identity]
            if len(matches) != 1:
                raise ValueError("Device missing or ambiguous; give identical devices unique names in Intiface and scan again")
            selected = matches[0]
            if selected.features != self.device.features:
                raise ValueError("Device capabilities changed; scan and select again")
            mapper = DeviceMapper(selected, self.bindings, self.limit)
            gap = mapper.gap_ms / 1000
            last_sent = 0.0
            last_input = time.monotonic()
            active = False
            self._ready.set()
            while not self._closed.is_set():
                if client.error:
                    raise client.error
                if selected.index in client.removed or client.devices.get(selected.index) != selected:
                    raise ConnectionError("Selected device disconnected; reconnect manually")
                now = time.monotonic()
                with self._lock:
                    stop = self._stop_requested
                    self._stop_requested = False
                    frame = None
                    if not stop and not self._paused and now - last_sent >= gap:
                        frame = self._latest
                if stop or (active and now - last_input > 0.6):
                    await client.request("StopDeviceCmd", DeviceIndex=selected.index)
                    active = False
                    mapper.reset()
                    if not stop:
                        self.stop_output()
                        raise TimeoutError("No fresh output for 600 ms; device stopped. Reconnect before restarting")
                elif frame is not None:
                    payload, created = frame
                    if now - created <= 0.3:
                        last_input = created
                        command = mapper.command(payload, now, created)
                        if command:
                            # Recheck the latch after formatting, before touching the transport.
                            with self._lock:
                                paused = self._paused or self._closed.is_set()
                            if not paused:
                                kind, body = command
                                reply, _ = await client.request(kind, DeviceIndex=selected.index, **body)
                                if reply != "Ok":
                                    raise RuntimeError("Intiface did not acknowledge output")
                                last_sent = time.monotonic()
                                active = True
                        elif active and mapper.missing_axes:
                            await client.request("StopDeviceCmd", DeviceIndex=selected.index)
                            active = False
                            mapper.reset()
                await asyncio.sleep(0.01)
        finally:
            if selected is not None and selected.index not in client.removed:
                with suppress(Exception):
                    await client.request("StopDeviceCmd", DeviceIndex=selected.index)
            await client.close()
