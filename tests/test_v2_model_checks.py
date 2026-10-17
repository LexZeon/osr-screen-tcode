"""Background validation must not freeze Tk or apply an obsolete UI choice."""
import threading
import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_app_layout as layout_tests
from osr_screen_tcode.application.model_options import ModelOptionsMixin
from osr_screen_tcode.config import HYBRID_V2_MODE


class _MemoryVariable:
    """Minimal traced value for completion checks; no Tcl interpreter."""
    def __init__(self, name, value):
        self.name, self.value, self.changed = name, value, None

    def __str__(self):
        return self.name

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        if self.changed is not None:
            self.changed()


class _CompletionApp(ModelOptionsMixin):
    def __init__(self, *, live, offline):
        self._build_v2_model_check_state()
        self.worker = SimpleNamespace(is_alive=lambda: True) if live else None
        self._video_analysis_active = lambda: offline
        self.stop, self.after = Mock(), Mock()
        self._dt = lambda zh, en: en
        self._tracker_internal = lambda value: value
        self.tracker_mode = _MemoryVariable('tracker', HYBRID_V2_MODE)
        self.rtm_pose_gpu_enabled = _MemoryVariable('gpu_enabled', False)
        self.rtm_pose_gpu_backend = _MemoryVariable('gpu_backend', 'cuda')
        self.status = _MemoryVariable('status', '')
        self._v2_model_revision = _MemoryVariable('revision', 0)
        self._v2_model_notices = {}
        for name, value in (('vittrack_enabled', True), ('neuflow_enabled', False),
                            ('vittrack_model_path', ''), ('neuflow_model_path', '')):
            setattr(self, f'v2_{name}', _MemoryVariable(name, value))
        self._v2_model_options = {name: variable.get()
                                 for name, variable in self._v2_model_variables().items()}
        self._v2_model_options.update(gpu_enabled=False, gpu_backend='cuda')
        self.v2_vittrack_model_path.changed = self._v2_model_options_changed


class LateDefaultModelCompletionTests(unittest.TestCase):
    def complete(self, *, live=False, offline=False, automatic=True):
        app = _CompletionApp(live=live, offline=offline)
        variable = app.v2_vittrack_model_path
        owner = SimpleNamespace(winfo_exists=lambda: True)
        key = str(variable)
        app._v2_model_checks[key] = {'token': 7, 'model': 'vittrack', 'variable': variable,
            'owner': owner, 'cancel': threading.Event(), 'original': '',
            'automatic': automatic, 'selection': False}
        event = {'key': key, 'token': 7, 'model': 'vittrack',
                 'path': 'private-models/default.onnx', 'reason': 'Model verified.'}
        app._finish_v2_model_check(event)
        return app, variable, owner, event

    def assert_automatic_completion_keeps_active_snapshot(self, app, variable, owner, event):
        self.assertEqual(variable.get(), '')
        self.assertEqual(app._v2_model_options['vittrack_model_path'], '')
        app.stop.assert_not_called()
        result = app._v2_model_check_results[str(variable)]
        self.assertEqual(result['path'], '')
        self.assertEqual(result['detected_path'], event['path'])
        self.assertTrue(result['valid'])
        self.assertIn('default.onnx', app._v2_model_check_text(variable))
        # The cached result still matches the empty configuration choice, so
        # displaying it must not schedule an endless automatic recheck.
        app._schedule_v2_model_check('vittrack', variable, owner, app.v2_vittrack_enabled)
        app.after.assert_not_called()

    def test_late_automatic_default_detection_does_not_stop_realtime(self):
        app, variable, owner, event = self.complete(live=True)
        self.assert_automatic_completion_keeps_active_snapshot(app, variable, owner, event)

    def test_late_automatic_default_detection_does_not_stop_offline_export(self):
        app, variable, owner, event = self.complete(offline=True)
        self.assert_automatic_completion_keeps_active_snapshot(app, variable, owner, event)

    def test_explicit_detect_still_changes_the_selected_path_and_stops_active_analysis(self):
        for activity in ({'live': True}, {'offline': True}):
            with self.subTest(activity=activity):
                app, variable, _owner, event = self.complete(automatic=False, **activity)
                self.assertEqual(variable.get(), event['path'])
                self.assertEqual(app._v2_model_options['vittrack_model_path'], event['path'])
                app.stop.assert_called_once_with()


class BackgroundModelCheckTests(unittest.TestCase):
    window = layout_tests.AppLayoutTests.window

    def pump_until(self, app, condition, timeout=2):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            app.update()
            time.sleep(.005)
        self.assertTrue(condition(), 'Background/UI completion timed out')

    def test_file_selection_validation_keeps_ui_live_and_preserves_previous_until_verified(self):
        entered, release = threading.Event(), threading.Event()
        def check(model, path, **kwargs):
            entered.set()
            release.wait(2)
            return path, 'Model verified.'
        with self.window() as app, patch('osr_screen_tcode.v2_model_assets.detect_model', side_effect=check), \
                patch('osr_screen_tcode.application.model_options.filedialog.askopenfilename', return_value='new.onnx'):
            try:
                variable = app.v2_vittrack_model_path
                variable.set('previous.onnx')
                app._pick_v2_model('vittrack', variable, app.sidebar_v2_model_controls)
                self.pump_until(app, entered.is_set)
                self.assertEqual(variable.get(), 'previous.onnx')
                heartbeat = []
                app.after(40, lambda: heartbeat.append(True))
                self.pump_until(app, lambda: heartbeat)
                self.assertEqual(variable.get(), 'previous.onnx')
                release.set()
                self.pump_until(app, lambda: variable.get() == 'new.onnx')
            finally:
                release.set()

    def test_automatic_detection_never_opts_in_and_requires_no_download(self):
        with self.window() as app, patch('osr_screen_tcode.v2_model_assets.detect_model', return_value=('found.onnx', 'Model verified.')) as detect, \
                patch('osr_screen_tcode.v2_model_assets.download_model') as download:
            app.sidebar_v2_model_controls.detect_button.invoke()
            self.pump_until(app, lambda: app.v2_vittrack_model_path.get() == 'found.onnx' and app.v2_neuflow_model_path.get() == 'found.onnx')
            self.assertFalse(app.v2_vittrack_enabled.get())
            self.assertFalse(app.v2_neuflow_enabled.get())
            self.assertFalse(app.rtm_pose_gpu_enabled.get())
            self.assertEqual(detect.call_count, 2)
            download.assert_not_called()

    def test_path_changed_during_debounce_checks_the_latest_choice(self):
        seen = []
        def check(model, path, **kwargs):
            seen.append(path)
            return path, 'Model verified.'
        with self.window() as app, patch('osr_screen_tcode.v2_model_assets.detect_model', side_effect=check):
            variable = app.v2_vittrack_model_path
            variable.set('before.onnx')
            app.v2_vittrack_enabled.set(True)
            app.update_idletasks()
            variable.set('after.onnx')
            self.pump_until(app, lambda: seen)
            self.assertEqual(seen, ['after.onnx'])

    def test_later_choice_and_destroyed_owner_ignore_a_slow_result(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        def check(*args, **kwargs):
            entered.set()
            release.wait(2)
            finished.set()
            return 'obsolete.onnx', 'Model verified.'
        with self.window() as app, patch('osr_screen_tcode.v2_model_assets.detect_model', side_effect=check):
            try:
                owner = ttk.Frame(app)
                variable = tk.StringVar(app, value='original.onnx')
                app._start_v2_model_check('vittrack', variable, owner)
                self.pump_until(app, entered.is_set)
                variable.set('later-choice.onnx')
                owner.destroy()
                release.set()
                self.pump_until(app, finished.is_set)
                self.pump_until(app, lambda: not app._v2_model_checks)
                self.assertEqual(variable.get(), 'later-choice.onnx')
            finally:
                release.set()

    def test_reset_cancels_inflight_detection_and_cannot_restore_old_paths(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        def check(*args, **kwargs):
            entered.set()
            release.wait(2)
            finished.set()
            return 'obsolete.onnx', 'Model verified.'
        with self.window() as app, patch('osr_screen_tcode.v2_model_assets.detect_model', side_effect=check):
            try:
                app.v2_vittrack_enabled.set(True)
                self.pump_until(app, entered.is_set)
                with patch('osr_screen_tcode.app.messagebox.askyesno', return_value=True):
                    app.reset_all_settings()
                release.set()
                self.pump_until(app, finished.is_set)
                app.update()
                self.assertFalse(app.v2_vittrack_enabled.get())
                self.assertEqual(app.v2_vittrack_model_path.get(), '')
                self.assertFalse(app._v2_model_checks)
            finally:
                release.set()

    def test_cuda_shortcut_uses_existing_private_setup_without_enabling_models(self):
        with self.window() as app, patch.object(app, '_show_v2_gpu_settings') as setup, \
                patch('osr_screen_tcode.gpu_controls.install_runtime') as install:
            app.rtm_pose_gpu_backend.set('directml')
            panel = app.sidebar_v2_model_controls
            panel.cuda_button.invoke()
            self.assertEqual(app.rtm_pose_gpu_backend.get(), 'cuda')
            self.assertTrue(app.rtm_pose_gpu_enabled.get())
            self.assertFalse(app.v2_neuflow_enabled.get())
            self.assertFalse(app.v2_vittrack_enabled.get())
            setup.assert_called_once_with(panel, app.rtm_pose_gpu_enabled)
            install.assert_not_called()


if __name__ == '__main__':
    unittest.main()
