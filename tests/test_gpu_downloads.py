import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from osr_screen_tcode import gpu_downloads as downloads


class DownloadTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cancel = threading.Event()
        self.events = []
        self.data = b"test wheel data" * 80000
        self.url = "https://files.pythonhosted.org/packages/test.whl"
        self.hash = hashlib.sha256(self.data).hexdigest()
        self.unknown_size = False
        self.corrupt = False
        self.get_count = 0
        self.truncate_first = False
        self.cancel.wait = lambda _: self.cancel.is_set()

    def resolve(self, args, *_):
        self.assertIn("--dry-run", args)
        self.assertIn("--ignore-installed", args)
        self.assertIn("https://pypi.org/simple", args)
        report = {"version": "1", "install": [{"download_info": {"url": self.url,
            "archive_info": {"hashes": {"sha256": self.hash}}}, "metadata": {"name": "test-runtime"}}]}
        Path(args[args.index("--report") + 1]).write_text(json.dumps(report), encoding="utf-8")

    def response(self, request, **_):
        data = self.data + b"bad" if self.corrupt else self.data
        if isinstance(request, str):
            self.get_count += 1
            if self.truncate_first and self.get_count == 1:
                data = data[:100]
        result = io.BytesIO(data)
        result.url = self.url
        result.headers = {} if self.unknown_size else {"Content-Length": str(len(data))}
        return result

    def run_download(self):
        with patch.object(downloads, "urlopen", side_effect=self.response), patch.object(downloads.shutil, "disk_usage", return_value=SimpleNamespace(free=20 * 1024 ** 3)):
            return downloads.download_runtime_wheels(self.root, "test-runtime", self.cancel, self.events.append, self.resolve)

    def test_real_byte_counts_and_verified_local_wheel(self):
        wheels = self.run_download()
        self.assertEqual((wheels / "test.whl").read_bytes(), self.data)
        data = [event for event in self.events if event["stage"] == "downloading"]
        self.assertEqual(data[0]["downloaded"], 0)
        self.assertEqual(data[-1]["downloaded"], len(self.data))
        self.assertEqual(data[-1]["total"], len(self.data))
        self.assertEqual(data[-1]["component"], "test-runtime")
        self.assertEqual([e["downloaded"] for e in data], sorted(e["downloaded"] for e in data))

    def test_missing_content_length_never_invents_percentage(self):
        self.unknown_size = True
        self.run_download()
        self.assertTrue(all(event["total"] is None for event in self.events if event["stage"] == "downloading"))

    def test_hash_mismatch_not_published_as_installable_wheel(self):
        self.corrupt = True
        with self.assertRaisesRegex(RuntimeError, "download_verification_failed"):
            self.run_download()
        self.assertFalse((self.root / "wheels" / "test.whl").exists())
        self.assertFalse((self.root / "wheels" / "test.whl.part").exists())
        self.assertEqual(self.get_count, 3)

    def test_truncated_download_retries_and_revalidates(self):
        self.truncate_first = True
        wheels = self.run_download()
        self.assertEqual(self.get_count, 2)
        self.assertEqual((wheels / "test.whl").read_bytes(), self.data)

    def test_cancel_before_network(self):
        self.cancel.set()
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            self.run_download()

    def test_disallowed_source_or_path_rejected(self):
        for url in ("http://files.pythonhosted.org/x.whl", "https://example.com/x.whl", "https://files.pythonhosted.org/%2E%2E%5Cbad.whl"):
            with self.assertRaisesRegex(RuntimeError, "invalid_wheel_source"):
                downloads._wheel_source(url)
