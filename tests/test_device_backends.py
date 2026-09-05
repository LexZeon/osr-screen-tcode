import asyncio
import json
import threading
import time
import unittest

from osr_screen_tcode.device_backends import (
    ButtplugClient, DeviceFeature, DeviceMapper, FeatureMapper, IntifaceDevice,
    IntifaceSink, discover_devices, validate_server_url,
)


def device_message(index=4, name="Test Device", messages=None):
    return {"DeviceIndex": index, "DeviceName": name, "DeviceMessageTimingGap": 50,
            "DeviceMessages": messages or {"LinearCmd": [{"ActuatorType": "Linear", "StepCount": 100}], "StopDeviceCmd": {}}}


class FakeIntiface:
    def __init__(self, devices=None):
        self.devices = devices if devices is not None else [device_message()]
        self.calls = []
        self.clients = set()
        self.ready = threading.Event()
        self.version = 3
        self.reject = None
        self.delay = 0

    def __enter__(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        if not self.ready.wait(3):
            raise RuntimeError("Test server failed to start")
        return self

    def _run(self):
        from websockets.legacy.server import serve
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.server = self.loop.run_until_complete(serve(self._handle, "127.0.0.1", 0))
        self.url = f"ws://127.0.0.1:{self.server.sockets[0].getsockname()[1]}"
        self.ready.set()
        self.loop.run_forever()
        self.loop.close()

    async def _handle(self, ws, *_args):
        from websockets.exceptions import ConnectionClosed
        self.clients.add(ws)
        try:
            async for raw in ws:
                for message in json.loads(raw):
                    kind, data = next(iter(message.items()))
                    self.calls.append((kind, data, time.monotonic()))
                    ident = data["Id"]
                    if kind == "RequestServerInfo":
                        response = {"ServerInfo": {"Id": ident, "MessageVersion": self.version,
                                                   "ServerName": "Local test only", "MaxPingTime": 200}}
                    elif kind == "RequestDeviceList":
                        response = {"DeviceList": {"Id": ident, "Devices": self.devices}}
                    elif kind == self.reject:
                        response = {"Error": {"Id": ident, "ErrorCode": 3, "ErrorMessage": "test"}}
                    else:
                        if kind in ("LinearCmd", "ScalarCmd", "RotateCmd"):
                            await asyncio.sleep(self.delay)
                        response = {"Ok": {"Id": ident}}
                    await ws.send(json.dumps([response]))
        except ConnectionClosed:
            pass
        finally:
            self.clients.discard(ws)

    def event(self, kind, data):
        self.events([{kind: {"Id": 0, **data}}])

    def events(self, messages):
        async def broadcast():
            for ws in list(self.clients):
                await ws.send(json.dumps(messages))
        asyncio.run_coroutine_threadsafe(broadcast(), self.loop).result(2)

    def __exit__(self, *_args):
        async def shutdown():
            self.server.close()
            await self.server.wait_closed()
        asyncio.run_coroutine_threadsafe(shutdown(), self.loop).result(3)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(3)


def wait_until(predicate, timeout=2.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Condition did not become true")


class MappingTests(unittest.TestCase):
    def test_custom_grouped_features_and_independent_axes(self):
        dev = IntifaceDevice.from_message(device_message(messages={"LinearCmd": [{"ActuatorType": "Linear"}] * 2}))
        mapper = DeviceMapper(dev, {"L0": dev.features[0].key, "R1": dev.features[1].key}, 0.2)
        kind, body = mapper.command(b"L02500I20 R17500I20", 1, 1)
        self.assertEqual(kind, "LinearCmd")
        self.assertEqual([v["Index"] for v in body["Vectors"]], [0, 1])
        self.assertAlmostEqual(body["Vectors"][1]["Position"], 7500 / 9999)
        self.assertIsNone(mapper.command(b"L02500I20 R17500I20", 1.1, 1))
        self.assertFalse(mapper.missing_axes)
        self.assertIsNone(mapper.command(b"L02500I20", 1.2, 1.2))
        self.assertTrue(mapper.missing_axes)

    def test_custom_round_robin_prevents_starving_other_functions(self):
        dev = IntifaceDevice.from_message(device_message(messages={
            "LinearCmd": [{"ActuatorType": "Linear"}], "RotateCmd": [{"ActuatorType": "Rotate"}],
            "ScalarCmd": [{"ActuatorType": "Vibrate"}]}))
        mapper = DeviceMapper(dev, dict(zip(("L0", "R0", "L2"), (f.key for f in dev.features))), 0.2)
        kinds = [mapper.command(b"L05000I20 R05000I20 L25000I20", n / 20, n / 20)[0] for n in range(6)]
        self.assertEqual(kinds, ["LinearCmd", "RotateCmd", "ScalarCmd"] * 2)
        for bindings in ({}, {"L0": dev.features[0].key, "R0": dev.features[0].key}, {"L0": "missing"}):
            with self.assertRaises(ValueError):
                DeviceMapper(dev, bindings, 0.2)
    def feature(self, command, actuator, index=0):
        return DeviceFeature(command, index, actuator, "test")

    def test_linear_preserves_limited_position_and_feature_index(self):
        mapper = FeatureMapper(self.feature("LinearCmd", "Linear", 2), "L0", 0.2, 100)
        kind, data = mapper.command(b"L07500I20 R00999I20", 0)
        vector = data["Vectors"][0]
        self.assertEqual(kind, "LinearCmd")
        self.assertEqual(vector["Index"], 2)
        self.assertAlmostEqual(vector["Position"], 7500 / 9999)
        self.assertGreaterEqual(vector["Duration"], 3750)

    def test_fast_target_updates_still_bound_linear_speed(self):
        mapper = FeatureMapper(self.feature("LinearCmd", "Linear"), "L0", 0.2, 50)
        for n in range(40):
            now = n * 0.05
            mapper.command(f"L0{9000 if n % 2 else 1000:04d}I20".encode(), now)
            low, high, target, _, duration = mapper._linear_state
            self.assertLessEqual(max(abs(target - low), abs(target - high)) / duration, 0.200001)

    def test_scalar_center_and_stationary_are_zero(self):
        mapper = FeatureMapper(self.feature("ScalarCmd", "Vibrate", 1), "L0", 0.2, 50)
        for now in (0, 0.05, 0.1):
            _, data = mapper.command(b"L05000I20", now)
            self.assertEqual(data["Scalars"][0]["Scalar"], 0)
        _, data = mapper.command(b"L09999I20", 0.15)
        self.assertEqual(data["Scalars"][0], {"Index": 1, "Scalar": 0.2, "ActuatorType": "Vibrate"})

    def test_rotate_direction_and_limit(self):
        mapper = FeatureMapper(self.feature("RotateCmd", "Rotate"), "R0", 0.15, 50)
        mapper.command(b"R05000I20", 0)
        _, data = mapper.command(b"R01000I20", 0.05)
        self.assertEqual(data["Rotations"][0], {"Index": 0, "Speed": 0.15, "Clockwise": False})

    def test_missing_axis_does_not_drive_other_axis(self):
        mapper = FeatureMapper(self.feature("LinearCmd", "Linear"), "L2", 0.2, 50)
        self.assertIsNone(mapper.command(b"L09000I20", 0))

    def test_zero_limit_disables_movement(self):
        for command, actuator in (("LinearCmd", "Linear"),):
            mapper = FeatureMapper(self.feature(command, actuator), "L0", 0, 50)
            self.assertIsNone(mapper.command(b"L09999I20", 0))

    def test_invalid_commands_and_nan_are_rejected(self):
        mapper = FeatureMapper(self.feature("LinearCmd", "Linear"), "L0", 0.2, 50)
        for raw in (b"D2", b"L0-500I20", b"L010000I20", b"L09999S1000"):
            with self.assertRaises(ValueError):
                mapper.command(raw, 0)
        with self.assertRaises(ValueError):
            FeatureMapper(self.feature("LinearCmd", "Linear"), "L0", float("nan"), 50)

    def test_unsupported_features_excluded_without_changing_indexes(self):
        dev = IntifaceDevice.from_message(device_message(messages={"ScalarCmd": [
            {"ActuatorType": "Heater"}, {"ActuatorType": "Vibrate"}, {"ActuatorType": "Spray"}, {"ActuatorType": "Position"}]}))
        self.assertEqual(len(dev.features), 1)
        self.assertEqual(dev.features[0].index, 1)

    def test_url_validation(self):
        self.assertEqual(validate_server_url(" ws://127.0.0.1:12345 "), "ws://127.0.0.1:12345")
        for url in ("https://host", "ws://user:secret@host", "ws://host?token=secret"):
            with self.assertRaises(ValueError):
                validate_server_url(url)


class TransportTests(unittest.TestCase):
    def test_custom_multi_function_limits_timing_missing_axis_and_stop(self):
        msg = device_message(messages={"LinearCmd": [{"ActuatorType": "Linear"}],
                                       "ScalarCmd": [{"ActuatorType": "Vibrate"}]})
        with FakeIntiface([msg]) as server:
            device = IntifaceDevice.from_message(msg)
            sink = IntifaceSink(server.url, device, bindings={"L0": device.features[0].key, "R0": device.features[1].key})
            try:
                sink.open()
                for i in range(8):
                    sink.write(f"L0{5000 + i * 300:04d}I20 R0{5000 + i * 300:04d}I20".encode())
                    time.sleep(0.06)
                calls = [c for c in server.calls if c[0] in {"LinearCmd", "ScalarCmd"}]
                self.assertEqual({c[0] for c in calls}, {"LinearCmd", "ScalarCmd"})
                self.assertTrue(all(b[2] - a[2] >= 0.045 for a, b in zip(calls, calls[1:])))
                self.assertTrue(all(c[1]["Scalars"][0]["Scalar"] <= 0.2 for c in calls if c[0] == "ScalarCmd"))
                sink.write(b"L05000I20")
                wait_until(lambda: any(c[0] == "StopDeviceCmd" for c in server.calls))
                sink.stop_output()
                time.sleep(0.08)
                count = len([c for c in server.calls if c[0] in {"LinearCmd", "ScalarCmd"}])
                sink.write(b"L09999I20 R09999I20")
                time.sleep(0.12)
                self.assertEqual(len([c for c in server.calls if c[0] in {"LinearCmd", "ScalarCmd"}]), count)
            finally:
                sink.close()
    def make_sink(self, server, original=None):
        dev = IntifaceDevice.from_message(original or server.devices[0])
        sink = IntifaceSink(server.url, dev, dev.features[0].key)
        self.addCleanup(sink.close)
        return sink

    def test_scan_handshake_ping_and_no_motion(self):
        with FakeIntiface() as server:
            devices = asyncio.run(discover_devices(server.url, 0.25))
            self.assertEqual(devices[0].name, "Test Device")
            calls = [kind for kind, _, _ in server.calls]
            self.assertIn("Ping", calls)
            self.assertIn("StopScanning", calls)
            self.assertFalse(set(calls) & {"LinearCmd", "ScalarCmd", "RotateCmd"})

    def test_server_version_mismatch_fails(self):
        with FakeIntiface() as server:
            server.version = 4
            with self.assertRaises(RuntimeError):
                asyncio.run(discover_devices(server.url, 0))

    def test_no_automatic_device_selection(self):
        with FakeIntiface([]) as server:
            self.assertEqual(asyncio.run(discover_devices(server.url, 0)), [])

    def test_session_index_rebound_by_unique_identity(self):
        with FakeIntiface([device_message(index=9)]) as server:
            sink = self.make_sink(server, original=device_message(index=4))
            sink.open()
            sink.write(b"L06000I20")
            wait_until(lambda: any(c[0] == "LinearCmd" for c in server.calls))
            self.assertEqual(next(c[1]["DeviceIndex"] for c in server.calls if c[0] == "LinearCmd"), 9)
            sink.close()

    def test_duplicate_identity_rejected(self):
        with FakeIntiface([device_message(1), device_message(2)]) as server:
            sink = self.make_sink(server)
            with self.assertRaises(ValueError):
                sink.open()
            self.assertFalse(any(c[0] == "LinearCmd" for c in server.calls))

    def test_capability_change_rejected(self):
        with FakeIntiface([device_message(messages={"ScalarCmd": [{"ActuatorType": "Vibrate"}]})]) as server:
            sink = self.make_sink(server, original=device_message())
            with self.assertRaises(ValueError):
                sink.open()

    def test_latest_frame_mailbox_and_stop_latch(self):
        with FakeIntiface() as server:
            sink = self.make_sink(server)
            sink.open()
            for value in range(5000, 7001):
                sink.write(f"L0{value:04d}I20".encode())
            wait_until(lambda: any(c[0] == "LinearCmd" and c[1]["Vectors"][0]["Position"] == 7000 / 9999 for c in server.calls))
            self.assertLess(len([c for c in server.calls if c[0] == "LinearCmd"]), 10)
            sink.stop_output()
            wait_until(lambda: any(c[0] == "StopDeviceCmd" for c in server.calls))
            for _ in range(50):
                sink.write(b"L09999I20")
            time.sleep(0.12)
            stop_index = next(i for i, c in enumerate(server.calls) if c[0] == "StopDeviceCmd")
            self.assertFalse(any(c[0] == "LinearCmd" for c in server.calls[stop_index + 1:]))
            sink.close()

    def test_output_rejection_surfaces_and_stops(self):
        with FakeIntiface() as server:
            server.reject = "LinearCmd"
            sink = self.make_sink(server)
            sink.open()
            sink.write(b"L05000I20")
            wait_until(lambda: sink.error is not None)
            with self.assertRaises(RuntimeError):
                sink.write(b"L06000I20")
            self.assertTrue(any(c[0] == "StopDeviceCmd" for c in server.calls))

    def test_stale_input_stops_instead_of_replaying(self):
        with FakeIntiface() as server:
            sink = self.make_sink(server)
            sink.open()
            sink.write(b"L06000I20")
            wait_until(lambda: sink.error is not None)
            self.assertIsInstance(sink.error, TimeoutError)
            self.assertTrue(any(c[0] == "StopDeviceCmd" for c in server.calls))

    def test_hot_unplug_never_retargets_reused_index(self):
        with FakeIntiface() as server:
            sink = self.make_sink(server)
            sink.open()
            server.events([{"DeviceRemoved": {"Id": 0, "DeviceIndex": 4}},
                           {"DeviceAdded": {"Id": 0, **device_message(index=4, name="Different Device")}}])
            wait_until(lambda: sink.error is not None)
            self.assertFalse(any(c[0] == "LinearCmd" for c in server.calls))

    def test_missing_selected_axis_stops_active_output(self):
        with FakeIntiface() as server:
            sink = self.make_sink(server)
            sink.open()
            sink.write(b"L06000I20")
            wait_until(lambda: any(c[0] == "LinearCmd" for c in server.calls))
            sink.write(b"R05000I20")
            wait_until(lambda: any(c[0] == "StopDeviceCmd" for c in server.calls))
            sink.close()

    def test_connection_refused_is_bounded(self):
        dev = IntifaceDevice.from_message(device_message())
        sink = IntifaceSink("ws://127.0.0.1:1", dev, dev.features[0].key)
        started = time.monotonic()
        with self.assertRaises(OSError):
            sink.open()
        sink.close()
        self.assertLess(time.monotonic() - started, 8)


if __name__ == "__main__":
    unittest.main()
