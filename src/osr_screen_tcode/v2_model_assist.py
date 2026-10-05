"""Optional image evidence for v2; model boxes never become motion samples.

The ordinary camera/subject validators retain ownership of all measurements.
Inference runs only on the analysis worker, at most once per distinct pair.
"""
from dataclasses import dataclass
import time

import cv2
import numpy as np

from .regional_flow import validated_flow_points


@dataclass(frozen=True)
class ModelDiagnostic:
    name: str
    state: str
    milliseconds: float = 0.
    samples: int = 0


def _box(xywh, shape):
    value = np.asarray(xywh, dtype=float)
    if value.shape != (4,) or not np.isfinite(value).all():
        return None
    x, y, width, height = value
    h, w = shape[:2]
    if min(width, height) < 8 or width > w or height > h:
        return None
    result = np.array((max(0., x), max(0., y), min(w-1., x+width), min(h-1., y+height)))
    return tuple(result) if min(result[2:]-result[:2]) >= 8 else None


def _inside(points, box, padding=0.):
    low, high = np.asarray(box[:2]), np.asarray(box[2:])
    pad = (high-low)*padding
    return np.all((points >= low-pad) & (points <= high+pad), axis=1)


class V2ModelAssist:
    def __init__(self, options, *, tracker_factory=None, flow_factory=None):
        self.options = dict(options or {})
        self.tracker_factory, self.flow_factory = tracker_factory, flow_factory
        self.tracker = self.flow = None
        self.failed = set()
        self.diagnostics = {}
        for name in ('vittrack', 'neuflow'):
            if self.options.get(name+'_enabled') is True:
                self.diagnostics[name] = ModelDiagnostic(name, 'waiting')
        self.reset()

    def reset(self):
        # Keep an already loaded flow session; discard target identity on cuts.
        self.reset_tracker()
        self.previous_bgr = self.current_bgr = None
        self.flow_cache = None
        self.flow_evaluated = False
        self.stamp = None
        for name in self.diagnostics:
            if name not in self.failed:
                self.diagnostics[name] = ModelDiagnostic(name, 'waiting')

    def reset_tracker(self):
        self.tracker = None
        self.previous_box = self.current_box = None
        if 'vittrack' in self.diagnostics and 'vittrack' not in self.failed:
            self.diagnostics['vittrack'] = ModelDiagnostic('vittrack', 'waiting')

    def _backend(self, name):
        if name in self.failed or name not in self.diagnostics:
            return None
        factory = self.tracker_factory if name == 'vittrack' else self.flow_factory
        if factory is None:
            from .v2_models import ViTTrackBackend, NeuFlowBackend
            factory = ViTTrackBackend if name == 'vittrack' else NeuFlowBackend
        path = self.options.get(name+'_model_path', '')
        if not path:
            from .v2_model_assets import find_existing_model
            path = str(find_existing_model(name) or '')
        if name == 'neuflow':
            device = self.options.get('gpu_backend', 'cuda')
            return factory(path, device=device, require_gpu=True)
        return factory(path, device='cpu')

    def _failure(self, name, reason, elapsed=0.):
        # Backend details can contain personal paths. Public preview uses codes.
        reason = str(reason).lower().replace('_', ' ')
        state = 'missing' if ('missing' in reason or 'not found' in reason or 'no model' in reason) else 'failed'
        if 'gpu required' in reason or 'gpu unavailable' in reason:
            state = 'gpu_required'
        self.failed.add(name)
        self.diagnostics[name] = ModelDiagnostic(name, state, elapsed)

    def begin(self, previous, current, stamp, prior_box):
        self.previous_bgr, self.current_bgr = previous, current
        self.flow_cache, self.flow_evaluated = None, False
        self.stamp = stamp
        if 'neuflow' in self.diagnostics and 'neuflow' not in self.failed:
            self.diagnostics['neuflow'] = ModelDiagnostic('neuflow', 'standby')
        self.previous_box = self.current_box
        self.current_box = None
        if 'vittrack' not in self.diagnostics or 'vittrack' in self.failed:
            return
        started = time.perf_counter()
        try:
            if prior_box is None:
                self.tracker = None
                self.previous_box = None
                self.diagnostics['vittrack'] = ModelDiagnostic('vittrack', 'waiting')
                return
            if self.tracker is None:
                self.tracker = self._backend('vittrack')
                x1, y1, x2, y2 = prior_box
                initialized = self.tracker.initialize(previous, (x1, y1, x2-x1, y2-y1))
                if initialized is False or (hasattr(initialized, 'valid') and not initialized.valid):
                    self._failure('vittrack', getattr(initialized, 'reason', 'initialize failed'))
                    self.tracker = None
                    return
                self.previous_box = tuple(prior_box)
            result = self.tracker.update(current)
            elapsed = (time.perf_counter()-started)*1000
            if not result.valid:
                reason = str(result.reason).lower()
                if any(word in reason for word in ('missing', 'failed', 'error', 'unavailable', 'invalid model')):
                    self._failure('vittrack', reason, elapsed)
                else:
                    self.diagnostics['vittrack'] = ModelDiagnostic('vittrack', 'rejected', elapsed)
                self.tracker = None
                self.previous_box = None
                return
            box = _box(result.bbox_xywh, current.shape)
            if box is None or not np.isfinite(result.confidence) or result.confidence < .5:
                self.tracker = None
                self.previous_box = None
                self.diagnostics['vittrack'] = ModelDiagnostic('vittrack', 'rejected', elapsed)
                return
            self.current_box = box
            self.diagnostics['vittrack'] = ModelDiagnostic('vittrack', 'candidate', elapsed)
        except Exception as exc:
            self._failure('vittrack', str(exc), (time.perf_counter()-started)*1000)
            self.tracker = None
            self.previous_box = None

    def subject_mask(self, a, b):
        if self.previous_box is None or self.current_box is None:
            return None
        # Only actual matched points from the same old AND new region qualify.
        # No synthetic displacement is derived from bounding-box centers.
        return _inside(a, self.previous_box, .08) & _inside(b, self.current_box, .08)

    def flow_points(self, previous_gray, current_gray):
        if self.flow_evaluated:
            return self.flow_cache
        self.flow_evaluated = True
        if 'neuflow' not in self.diagnostics or 'neuflow' in self.failed:
            return None
        if self.options.get('gpu_enabled') is not True:
            self._failure('neuflow', 'GPU required')
            return None
        if self.options.get('gpu_backend', 'cuda') != 'cuda':
            self.failed.add('neuflow')
            self.diagnostics['neuflow'] = ModelDiagnostic('neuflow', 'cuda_required')
            return None
        if self.previous_bgr is None or self.current_bgr is None:
            return None
        started = time.perf_counter()
        try:
            if self.flow is None:
                self.flow = self._backend('neuflow')
            result = self.flow.infer(self.previous_bgr, self.current_bgr, backward=True)
            elapsed = (time.perf_counter()-started)*1000
            if not result.valid:
                self._failure('neuflow', result.reason, elapsed)
                return None
            a, b = validated_flow_points(previous_gray, current_gray, result.forward, result.backward)
            self.diagnostics['neuflow'] = ModelDiagnostic('neuflow', 'verified' if len(a) >= 8 else 'rejected',
                                                         elapsed, len(a))
            self.flow_cache = (a, b) if len(a) >= 8 else None
            return self.flow_cache
        except Exception as exc:
            self._failure('neuflow', str(exc), (time.perf_counter()-started)*1000)
            return None

    def snapshot(self):
        return tuple(self.diagnostics.values())
