import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from osr_screen_tcode import config
from osr_screen_tcode.analysis_preferences import defaults, load_profiles, POSE_OPTIONS
from osr_screen_tcode.preview import PreviewBridge


class PreferenceTests(unittest.TestCase):
    def test_fresh_dance_defaults_and_legacy_active_settings_survive_roundtrip(self):
        fresh = load_profiles({}, config.RTM_POSE_2D_MODE, 45)
        self.assertEqual(fresh["dance"], defaults("dance"))
        self.assertTrue(fresh['dance']['pose_auto_l0_enabled'])
        self.assertFalse(fresh['dance']['pose_pattern_enabled'])
        self.assertTrue(fresh['dance']['pose_fast_v1_enabled'])
        with tempfile.TemporaryDirectory() as temp, patch.object(config, "APP_DIR", Path(temp)), patch.object(config, "CONFIG_PATH", Path(temp)/"settings.json"):
            path = config.CONFIG_PATH
            path.write_text(json.dumps({"tracker_mode": config.RTM_POSE_2D_MODE, "fps": 60,
                "extra": {"rtm_pose_flow_enabled": False, "rtm_hybrid_source": config.HYBRID_MODE}}), encoding="utf-8")
            loaded = config.AppConfig.load()
            self.assertEqual(loaded.extra["analysis_profiles"]["dance"]["fps"], 60)
            self.assertFalse(loaded.extra["analysis_profiles"]["dance"]["rtm_pose_flow_enabled"])
            self.assertTrue(loaded.extra["analysis_profiles"]["dance"]["rtm_pose_micro_smooth_enabled"])
            self.assertTrue(loaded.extra['analysis_profiles']['dance']['pose_auto_l0_enabled'])
            self.assertFalse(loaded.extra['analysis_profiles']['dance']['pose_pattern_enabled'])
            self.assertTrue(loaded.extra['analysis_profiles']['dance']['pose_fast_v1_enabled'])
            self.assertEqual(loaded.extra["rtm_hybrid_source"], config.HYBRID_V2_MODE)
            loaded.save()
            self.assertEqual(config.AppConfig.load().extra["analysis_profiles"], loaded.extra["analysis_profiles"])

    def test_invalid_nested_profile_values_are_sanitized(self):
        profiles = load_profiles({"analysis_profiles": {"dance": {"fps": "nan", "compression_latency": 99, "rtm_hybrid_l0_weight": -2}, "hybrid": []}}, config.HYBRID_V2_MODE, 45)
        self.assertEqual(profiles["dance"]["fps"], 45)
        self.assertEqual(profiles["dance"]["compression_latency"], 5)
        self.assertEqual(profiles["dance"]["rtm_hybrid_l0_weight"], 1)
        self.assertEqual(profiles["hybrid"], defaults("hybrid"))


class SimulatorBridgeTests(unittest.TestCase):
    def test_late_client_receives_last_final_command_and_live_updates(self):
        import websockets
        bridge = PreviewBridge()
        first = "L05000I24 L16300I24 L23700I24"
        second = "L04000I24 L16000I24 L24000I24"
        bridge.broadcast_tcode(first)
        bridge.start()
        async def check():
            async with websockets.connect(bridge.url, open_timeout=2) as client:
                context = json.loads(await asyncio.wait_for(client.recv(), 2))
                self.assertEqual(context["name"], "device_context")
                self.assertEqual(json.loads(await asyncio.wait_for(client.recv(), 2))["data"]["cmd"], first)
                bridge.broadcast_tcode(second)
                self.assertEqual(json.loads(await asyncio.wait_for(client.recv(), 2))["data"]["cmd"], second)
                await client.send(json.dumps({"type": "ping"}))
                self.assertEqual(json.loads(await asyncio.wait_for(client.recv(), 2)), {"type": "pong"})
        try:
            asyncio.run(check())
        finally:
            bridge.stop()
        self.assertFalse(bridge.is_running)
