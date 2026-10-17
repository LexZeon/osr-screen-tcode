from dataclasses import replace
import hashlib
import io
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request

from osr_screen_tcode import v2_model_assets as assets


class Response(io.BytesIO):
    def __init__(self, data, declared=True, status=200):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))} if declared else {}
        self.status = status

    def getcode(self):
        return self.status


class OptionalModelAssetsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="osr-model-assets-test-")
        self.addCleanup(self.folder.cleanup)
        self.patcher = patch.object(assets.config, "APP_DIR", Path(self.folder.name))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.data = b"synthetic model data for integrity tests" * 7000
        self.asset = replace(assets.model_info("vittrack"), size=len(self.data),
                             sha256=hashlib.sha256(self.data).hexdigest())
        self.registry = patch.dict(assets._ASSETS, vittrack=self.asset)
        self.registry.start()
        self.addCleanup(self.registry.stop)

    def files(self):
        return list(Path(self.folder.name).rglob("*.*"))

    def put(self, data):
        path = assets.default_path("vittrack")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_known_ids_and_private_paths(self):
        path = assets.default_path("vittrack")
        self.assertEqual(path.parent, Path(self.folder.name) / "models" / "v2_models")
        self.assertEqual(assets.model_info("neuflow"), assets.model_info("neuflow_v2"))
        for value in ("../other", "https://example.com/model", None):
            with self.assertRaises(ValueError):
                assets.default_path(value)

    def test_availability_has_no_download_or_directory_write(self):
        with patch.object(assets, "_open_download") as network:
            self.assertFalse(assets.model_available("vittrack"))
            self.assertIsNone(assets.find_existing_model("vittrack"))
            network.assert_not_called()
        self.assertEqual(self.files(), [])

    def test_exact_supported_file_required_for_manual_selection(self):
        path = self.put(self.data)
        self.assertTrue(assets.validate_model_path("vittrack", path)[0])
        # Same-size corruption must invalidate the stat-based checksum cache.
        path.write_bytes(b"x" + self.data[1:])
        self.assertFalse(assets.validate_model_path("vittrack", path)[0])
        path.write_bytes(self.data[:-1])
        self.assertFalse(assets.validate_model_path("vittrack", path)[0])
        disguised = path.with_suffix(".pt")
        disguised.write_bytes(self.data)
        self.assertFalse(assets.validate_model_path("vittrack", disguised)[0])

    def test_download_verified_atomically_and_reports_progress(self):
        events = []
        target = assets.default_path("vittrack")

        def observe(count, total):
            self.assertFalse(target.exists())
            events.append((count, total))

        with patch.object(assets, "_open_download", return_value=Response(self.data)):
            result = assets.download_model("vittrack", progress=observe)
        self.assertEqual(result, target)
        self.assertEqual(result.read_bytes(), self.data)
        self.assertEqual(events[0], (0, len(self.data)))
        self.assertEqual(events[-1], (len(self.data), len(self.data)))
        self.assertEqual(self.files(), [target])

    def test_verified_existing_model_skips_network(self):
        target = self.put(self.data)
        with patch.object(assets, "_open_download") as network:
            self.assertEqual(assets.download_model("vittrack"), target)
            network.assert_not_called()

    def test_cancellation_preserves_existing_file_and_cleans_partial(self):
        target = self.put(b"previous file")
        cancel = threading.Event()

        def progress(count, total):
            if count:
                cancel.set()

        with patch.object(assets, "_open_download", return_value=Response(self.data)):
            with self.assertRaises(assets.ModelDownloadCancelled):
                assets.download_model("vittrack", cancel, progress)
        self.assertEqual(target.read_bytes(), b"previous file")
        self.assertEqual(self.files(), [target])
        # Cancellation must also release the model lock so a retry can succeed.
        with patch.object(assets, "_open_download", return_value=Response(self.data)):
            self.assertEqual(assets.download_model("vittrack").read_bytes(), self.data)

    def test_cancelled_before_start_has_no_side_effects(self):
        cancel = threading.Event()
        cancel.set()
        with patch.object(assets, "_open_download") as network:
            with self.assertRaises(assets.ModelDownloadCancelled):
                assets.download_model("vittrack", cancel)
            network.assert_not_called()
        self.assertEqual(self.files(), [])

    def test_wrong_hash_truncated_and_oversized_downloads_preserve_old_file(self):
        target = self.put(b"old model")
        for data in (b"x" + self.data[1:], self.data[:-1], self.data + b"x"):
            with self.subTest(length=len(data)):
                with patch.object(assets, "_open_download", return_value=Response(data, declared=False)):
                    with self.assertRaises(assets.ModelDownloadError):
                        assets.download_model("vittrack")
                self.assertEqual(target.read_bytes(), b"old model")
                self.assertEqual(self.files(), [target])

    def test_server_errors_and_content_length_rejected_before_staging(self):
        for response in (Response(self.data, status=206), Response(b"not a model")):
            with patch.object(assets, "_open_download", return_value=response):
                with self.assertRaises(assets.ModelDownloadError):
                    assets.download_model("vittrack")
            self.assertEqual(self.files(), [])

    def test_network_failure_hides_signed_url_and_removes_partial(self):
        class BrokenResponse(Response):
            def read(self, count=-1):
                if self.tell():
                    raise TimeoutError("private-token=https://host/signed?Secret=123")
                return super().read(count)

        with patch.object(assets, "_open_download", return_value=BrokenResponse(self.data)):
            with self.assertRaises(assets.ModelDownloadError) as caught:
                assets.download_model("vittrack")
        self.assertNotIn("Secret", str(caught.exception))
        self.assertEqual(self.files(), [])

    def test_total_deadline_bounds_a_slow_response(self):
        with patch.object(assets, "_open_download", return_value=Response(self.data)):
            with patch.object(assets.time, "monotonic", side_effect=(0., 601.)):
                with self.assertRaisesRegex(assets.ModelDownloadError, "timed out"):
                    assets.download_model("vittrack")
        self.assertEqual(self.files(), [])

    def test_atomic_replace_failure_preserves_old_file(self):
        target = self.put(b"old model")
        with patch.object(assets, "_open_download", return_value=Response(self.data)):
            with patch.object(assets.os, "replace", side_effect=PermissionError("locked file")):
                with self.assertRaises(assets.ModelDownloadError):
                    assets.download_model("vittrack")
        self.assertEqual(target.read_bytes(), b"old model")
        self.assertEqual(self.files(), [target])

    def test_waiting_download_can_be_cancelled(self):
        cancel = threading.Event()
        outcomes = []
        lock = assets._LOCKS["vittrack"]
        lock.acquire()
        try:
            def run():
                try:
                    assets.download_model("vittrack", cancel)
                except assets.ModelDownloadCancelled:
                    outcomes.append("cancelled")
            thread = threading.Thread(target=run)
            thread.start()
            cancel.set()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(outcomes, ["cancelled"])
        finally:
            lock.release()

    def test_only_supported_https_redirects(self):
        handler = assets._SecureRedirect()
        request = Request("https://huggingface.co/model")
        for url in ("http://huggingface.co/file", "https://evil.test/file",
                    "https://huggingface.co.evil.test/file", "https://user:pass@hf.co/file"):
            with self.subTest(url=url):
                with self.assertRaises(assets.ModelDownloadError):
                    handler.redirect_request(request, None, 302, "Found", {}, url)
        good = handler.redirect_request(request, None, 302, "Found", {},
                                        "https://cas-bridge.xethub.hf.co/file?signature=value")
        self.assertEqual(good.type, "https")

    def test_detect_finds_default_before_supplied_directory_without_network(self):
        target = self.put(self.data)
        with patch.object(assets, "_open_download") as network, \
                patch.object(assets, "validate_model_path", wraps=assets.validate_model_path) as validate:
            self.assertEqual(assets.detect_model("vittrack", model_dirs=(Path(self.folder.name),)),
                             (str(target), "Model verified."))
        self.assertEqual(validate.call_count, 1)
        network.assert_not_called()

    def test_detect_only_checks_registered_filename_in_direct_directories(self):
        supplied = Path(self.folder.name) / "supplied"
        nested = supplied / "nested" / self.asset.filename
        nested.parent.mkdir(parents=True)
        nested.write_bytes(self.data)
        (supplied / "arbitrary.onnx").write_bytes(self.data)
        with patch.object(assets, "validate_model_path", wraps=assets.validate_model_path) as validate:
            result = assets.detect_model("vittrack", model_dirs=(supplied, supplied / "."))
        self.assertEqual(result, ("", "Model file is missing."))
        self.assertEqual([call.args[1] for call in validate.call_args_list],
                         [assets.default_path("vittrack"), supplied / self.asset.filename])
        direct = supplied / self.asset.filename
        direct.write_bytes(self.data)
        self.assertEqual(assets.detect_model("vittrack", model_dirs=(supplied,)),
                         (str(direct), "Model verified."))

    def test_detect_deduplicates_default_and_supplied_candidates(self):
        target = assets.default_path("vittrack")
        with patch.object(assets, "validate_model_path", wraps=assets.validate_model_path) as validate:
            self.assertEqual(assets.detect_model("vittrack", model_dirs=(target.parent, target.parent / ".")),
                             ("", "Model file is missing."))
        self.assertEqual(validate.call_count, 1)
        self.assertEqual(self.files(), [])

    def test_detect_explicit_path_never_falls_back_to_verified_default(self):
        target = self.put(self.data)
        explicit = Path(self.folder.name) / "chosen.onnx"
        explicit.write_bytes(b"incorrect model")
        with patch.object(assets, "validate_model_path", wraps=assets.validate_model_path) as validate:
            result = assets.detect_model("vittrack", explicit, model_dirs=(target.parent,))
        self.assertEqual(result, ("", "Model file size does not match. Download the supported model."))
        self.assertEqual(validate.call_count, 1)
        self.assertEqual(validate.call_args.args[1], explicit)
        self.assertEqual(assets.detect_model("vittrack", target), (str(target), "Model verified."))

    def test_detect_revalidates_modified_cached_file(self):
        target = self.put(self.data)
        self.assertEqual(assets.detect_model("vittrack"), (str(target), "Model verified."))
        stamp = target.stat()
        target.write_bytes(b"x" + self.data[1:])
        os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
        self.assertEqual(assets.detect_model("vittrack"),
                         ("", "Model checksum does not match. Download the supported model."))

    def test_detect_cancelled_before_start_never_validates_or_writes(self):
        cancel = threading.Event()
        cancel.set()
        with patch.object(assets, "validate_model_path") as validate:
            with self.assertRaises(assets.ModelDownloadCancelled):
                assets.detect_model("vittrack", cancel=cancel)
        validate.assert_not_called()
        self.assertEqual(self.files(), [])

    def test_detect_cancelled_between_candidates_stops_before_next_validation(self):
        cancel = threading.Event()
        def missing(*_args, **_kwargs):
            cancel.set()
            return False, "Model file is missing."
        with patch.object(assets, "validate_model_path", side_effect=missing) as validate:
            with self.assertRaises(assets.ModelDownloadCancelled):
                assets.detect_model("vittrack", model_dirs=(Path(self.folder.name),), cancel=cancel)
        self.assertEqual(validate.call_count, 1)

    def test_validation_can_cancel_between_hash_chunks_without_caching_success(self):
        target = self.put(self.data)
        cancel = threading.Event()
        counts = []
        original_open = Path.open
        class CancelDuringRead(io.BytesIO):
            def read(self, count=-1):
                counts.append(count)
                data = super().read(count)
                cancel.set()
                return data
        def opening(path, *args, **kwargs):
            return CancelDuringRead(self.data) if path == target else original_open(path, *args, **kwargs)
        with patch.object(Path, "open", opening):
            with self.assertRaises(assets.ModelDownloadCancelled):
                assets.validate_model_path("vittrack", target, cancel=cancel)
        self.assertEqual(counts, [assets._CHUNK])
        self.assertNotIn(assets._file_key(target, self.asset), assets._CACHE)
        self.assertTrue(assets.validate_model_path("vittrack", target)[0])

    def test_validation_cancelled_cached_file_still_honors_cancellation(self):
        target = self.put(self.data)
        self.assertTrue(assets.validate_model_path("vittrack", target)[0])
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(assets.ModelDownloadCancelled):
            assets.validate_model_path("vittrack", target, cancel=cancel)


if __name__ == "__main__":
    unittest.main()
