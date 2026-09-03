from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Protocol


class TCodeSink(Protocol):
    def open(self) -> None:
        ...

    def write(self, payload: bytes) -> None:
        ...

    def close(self) -> None:
        ...


class LogSink:
    def __init__(self) -> None:
        self.last_payload = b""

    def open(self) -> None:
        pass

    def write(self, payload: bytes) -> None:
        self.last_payload = payload

    def close(self) -> None:
        pass


@dataclass
class SerialSink:
    port: str
    baudrate: int = 115200
    timeout: float = 0.01

    def __post_init__(self) -> None:
        self._serial = None

    def open(self) -> None:
        import serial

        if not self.port:
            raise ValueError("请选择串口")
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)

    def write(self, payload: bytes) -> None:
        if self._serial is None:
            return
        self._serial.write(payload)

    def query(self, payload: bytes, wait_s: float = 0.6) -> bytes:
        if self._serial is None:
            return b""
        old_timeout = self._serial.timeout
        self._serial.timeout = 0.05
        try:
            self._serial.reset_input_buffer()
            self._serial.write(payload)
            self._serial.flush()
            collected = bytearray()
            deadline = time.perf_counter() + wait_s
            quiet_deadline = deadline
            while time.perf_counter() < deadline:
                waiting = self._serial.in_waiting
                if waiting:
                    collected.extend(self._serial.read(waiting))
                    quiet_deadline = time.perf_counter() + 0.18
                else:
                    chunk = self._serial.read(1)
                    if chunk:
                        collected.extend(chunk)
                        quiet_deadline = time.perf_counter() + 0.18
                    elif collected and time.perf_counter() >= quiet_deadline:
                        break
            return bytes(collected)
        finally:
            self._serial.timeout = old_timeout

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None


class BleSink:
    def __init__(self, address: str, write_uuid: str) -> None:
        self.address = address
        self.write_uuid = write_uuid
        self._queue: Queue[bytes | None] = Queue(maxsize=8)
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: Exception | None = None

    def open(self) -> None:
        if not self.address:
            raise ValueError("请选择 BLE 设备")
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=12):
            raise TimeoutError("BLE 连接超时")
        if self._error is not None:
            raise self._error

    def write(self, payload: bytes) -> None:
        if self._error is not None:
            raise self._error
        try:
            if self._queue.full():
                self._queue.get_nowait()
            self._queue.put_nowait(payload)
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    def _run_loop(self) -> None:
        try:
            asyncio.run(self._ble_worker())
        except Exception as exc:
            self._error = exc
            self._ready.set()

    async def _ble_worker(self) -> None:
        from bleak import BleakClient

        async with BleakClient(self.address) as client:
            if not client.is_connected:
                raise ConnectionError("BLE 未连接")
            self._ready.set()
            while True:
                try:
                    payload = await asyncio.to_thread(self._queue.get, True, 0.25)
                except Empty:
                    continue
                if payload is None:
                    break
                await client.write_gatt_char(self.write_uuid, payload, response=False)


@dataclass(frozen=True)
class SerialPortInfo:
    device: str
    description: str
    hwid: str = ""

    @property
    def display_name(self) -> str:
        if self.description:
            return f"{self.device} - {self.description}"
        return self.device


def list_serial_ports() -> list[str]:
    return [port.device for port in list_serial_port_infos()]


def list_serial_port_infos() -> list[SerialPortInfo]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [
        SerialPortInfo(port.device, port.description or "", port.hwid or "")
        for port in list_ports.comports()
    ]


def extract_serial_device(value: str) -> str:
    value = value.strip()
    if " - " in value:
        return value.split(" - ", 1)[0].strip()
    return value


def choose_best_serial_port(ports: list[SerialPortInfo]) -> str:
    if not ports:
        return ""
    preferred_needles = ("CH340", "USB-SERIAL", "USB SERIAL", "CP210", "FTDI", "ARDUINO")
    for needle in preferred_needles:
        for port in ports:
            haystack = f"{port.device} {port.description} {port.hwid}".upper()
            if needle in haystack:
                return port.display_name
    return ports[0].display_name


async def scan_ble_devices(name_filter: str = "") -> list[tuple[str, str]]:
    from bleak import BleakScanner

    devices = await BleakScanner.discover(timeout=5)
    needle = name_filter.lower().strip()
    found: list[tuple[str, str]] = []
    for device in devices:
        name = device.name or "(unnamed)"
        if needle and needle not in name.lower() and needle not in device.address.lower():
            continue
        found.append((name, device.address))
    return found
