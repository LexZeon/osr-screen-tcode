"""Background optional-model discovery; only Tk applies current results.

Workers receive plain paths and cancellation events. Stale selections, closed
dialogs and reset/close cannot apply their result to a later UI choice.
"""
from __future__ import annotations

import threading
import tkinter as tk


class ModelChecksMixin:
    def _build_v2_model_check_state(self):
        self._v2_model_checks = {}
        self._v2_model_check_after = {}
        self._v2_model_check_results = {}
        self._v2_model_check_token = 0
        self._v2_model_check_slots = threading.Semaphore(2)
        self._v2_model_checks_closed = False

    def _schedule_v2_model_check(self, model, variable, owner, enabled):
        key = str(variable)
        if not enabled.get():
            record = self._v2_model_checks.get(key)
            if record and record['automatic']:
                record['cancel'].set()
                self._v2_model_checks.pop(key)
            scheduled = self._v2_model_check_after.pop(key, None)
            if scheduled:
                self.after_cancel(scheduled['id'])
            return
        if self._v2_model_checks_closed:
            return
        original = variable.get()
        scheduled = self._v2_model_check_after.get(key)
        if scheduled:
            if scheduled['original'] == original:
                return
            self.after_cancel(scheduled['id'])
            self._v2_model_check_after.pop(key)
        cached = self._v2_model_check_results.get(key)
        current = self._v2_model_checks.get(key)
        if ((cached and cached['path'] == original)
                or (current and current['original'] == original)):
            return

        def begin():
            self._v2_model_check_after.pop(key, None)
            if owner.winfo_exists() and enabled.get() and variable.get() == original:
                self._start_v2_model_check(model, variable, owner, automatic=True)

        token = self.after(40, begin)
        self._v2_model_check_after[key] = {'id': token, 'owner': owner, 'original': original}

    def _start_v2_model_check(self, model, variable, owner, *, path=None, automatic=False):
        if self._v2_model_checks_closed or not owner.winfo_exists():
            return
        key = str(variable)
        scheduled = self._v2_model_check_after.pop(key, None)
        if scheduled:
            self.after_cancel(scheduled['id'])
        previous = self._v2_model_checks.pop(key, None)
        if previous:
            previous['cancel'].set()
        self._v2_model_check_token += 1
        token = self._v2_model_check_token
        original = variable.get()
        selected = original if path is None else path
        cancel = threading.Event()
        self._v2_model_checks[key] = {'token': token, 'model': model, 'variable': variable,
            'owner': owner, 'cancel': cancel, 'original': original, 'automatic': automatic,
            'selection': path is not None}
        self._v2_model_revision.set(self._v2_model_revision.get() + 1)

        def worker():
            from ..v2_model_assets import detect_model, ModelDownloadCancelled
            acquired = False
            try:
                while not acquired:
                    if cancel.is_set():
                        return
                    acquired = self._v2_model_check_slots.acquire(timeout=.1)
                result, reason = detect_model(model, selected, cancel=cancel)
            except ModelDownloadCancelled:
                return
            except Exception:
                result, reason = '', 'Model file cannot be read.'
            finally:
                if acquired:
                    self._v2_model_check_slots.release()
            if not cancel.is_set():
                self._queue_latest({'v2_model_event': {'kind': 'checked', 'model': model,
                    'key': key, 'token': token, 'path': result, 'reason': reason}})

        threading.Thread(target=worker, daemon=True, name=f'v2-model-check-{model}').start()

    def _finish_v2_model_check(self, event):
        key = event['key']
        record = self._v2_model_checks.get(key)
        if record is None or record['token'] != event['token']:
            return
        self._v2_model_checks.pop(key)
        variable = record['variable']
        if (record['cancel'].is_set() or not record['owner'].winfo_exists()
                or variable.get() != record['original']):
            self._v2_model_revision.set(self._v2_model_revision.get() + 1)
            return
        # Empty already means the private default to the analysis worker. Do
        # not turn a late automatic lookup into a live option change/stop.
        keep_default_choice = (bool(event['path']) and record['automatic']
            and record['original'] == ''
            and ((self.worker and self.worker.is_alive()) or self._video_analysis_active()))
        path = record['original'] if keep_default_choice else event['path'] or record['original']
        self._v2_model_check_results[key] = {'path': path, 'valid': bool(event['path']),
            'detected_path': event['path'], 'reason': event['reason'],
            'owner': record['owner'], 'selection': record['selection']}
        if event['path']:
            self._v2_model_notices.pop(event['model'], None)
            if not keep_default_choice:
                variable.set(event['path'])
        self._v2_model_revision.set(self._v2_model_revision.get() + 1)

    def _v2_model_check_text(self, variable):
        key = str(variable)
        if key in self._v2_model_checks or key in self._v2_model_check_after:
            return self._dt('后台检测／校验中；界面仍可操作。', 'Checking in background; controls remain available.')
        result = self._v2_model_check_results.get(key)
        if not result or result['path'] != variable.get():
            return ''
        if result['valid']:
            from pathlib import Path
            return self._dt('已检测并校验：', 'Detected and verified: ') + Path(result.get('detected_path') or result['path']).name
        prefix = self._dt('选择被拒绝，保留原模型：', 'Selection rejected; previous model unchanged: ') if result['selection'] else ''
        return prefix + self._v2_model_error_text(result['reason'])

    def _cancel_v2_model_checks(self, owner=None):
        for key, scheduled in tuple(self._v2_model_check_after.items()):
            if owner is None or scheduled['owner'] is owner:
                try:
                    self.after_cancel(scheduled['id'])
                except tk.TclError:
                    pass
                self._v2_model_check_after.pop(key)
        for key, record in tuple(self._v2_model_checks.items()):
            if owner is None or record['owner'] is owner:
                record['cancel'].set()
                self._v2_model_checks.pop(key)
        for key, result in tuple(self._v2_model_check_results.items()):
            if owner is None or result['owner'] is owner:
                self._v2_model_check_results.pop(key)
