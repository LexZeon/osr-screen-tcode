"""One sampled frame supplies both the integrated preview and analysis output."""
from dataclasses import dataclass, replace
import time

import cv2
import numpy as np

from .analyzer import AxisAnalysis, RealtimeAnalyzer, SIX_AXES
from .config import HYBRID_MODE, HYBRID_V2_MODE, RTM_POSE_2D_MODE, STROKE_CYCLE_MODE
from .stroke_cycle import StrokeCycle
from .pose_backends import RtmPose3dResult
from .visual_lab.stabilizer import EDGES, Options, Stabilizer
from .visual_lab.observations import ImageObservations, Observation
from .camera_motion import CameraRelativeMotion
from .motion_reference import MotionReference, draw_reference
from .dominant_motion import DominantMotion
from .frame_rotation import FrameRotation
from .secondary_motion import SecondaryMotionFilter
from .pose_l0_fallback import PoseL0Fallback, PoseL0Recovery
from .pose_pattern import PosePattern
from .pose_fast_fallback import PoseFastFallback
from .pose_output import rtm_l0_amplitude, rtm_rotation_amplitudes
from .point_l0 import PointL0
from .reach_target import ReachTarget
from .subject_continuity import SubjectContinuity

RESOLUTIONS = (320, 480, 640, 960, 1280)


@dataclass(frozen=True)
class VisualSettings:
    edge: int = 640
    options: Options = Options(False, False, False, False)
    generation: int = 0
    pose_auto_l0: bool = True
    pose_pattern: bool = False
    pose_fast_v1: bool = True
    v2_l0_reference: str = 'fusion'


@dataclass(frozen=True)
class VisualFrame:
    pair: tuple[np.ndarray, np.ndarray]
    observation: Observation | None
    pose: bool
    generation: int
    reset: bool = False
    inference_ms: float = 0.0
    processing_ms: float = 0.0
    gap_ms: float = 0.0
    resets: int = 0
    skipped: int = 0
    motion_weights: tuple[float, float, float] | None = None
    rotation_source: str = ""
    reference: MotionReference | None = None
    l0_source: str = ""
    pattern_gains: tuple = ()
    l0_recoveries: int = 0


def resize_for_processing(frame, edge):
    height, width = frame.shape[:2]
    ratio = min(1.0, edge / max(height, width))
    if ratio >= 1:
        return frame
    # Keep the entire selected region, including extremely wide multi-monitor
    # strips whose short edge would otherwise round to zero in OpenCV.
    size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
    return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)


def draw_pose(frame, points, color, rejected=None):
    image = frame.copy()
    valid = np.isfinite(points).all(axis=1)
    for a, b in EDGES:
        if valid[a] and valid[b]:
            cv2.line(image, tuple(points[a].astype(int)), tuple(points[b].astype(int)), color, 2, cv2.LINE_AA)
    for i in np.flatnonzero(valid):
        c = (0, 0, 255) if rejected is not None and rejected[i] else color
        cv2.circle(image, tuple(points[i].astype(int)), 4, c, -1, cv2.LINE_AA)
    return image


class LabAnalyzer:
    """Synchronous RTM 2D or image-motion v2, with per-run tracking state.

    Translation measurements are relative to a calibrated image reference.
    Existing RTM 2D rotation heuristics are retained; they are not 3D IK.
    Hybrid 1 remains independent; optional RTM blending uses v2 for L0 only.
    """
    def __init__(self, *, settings=VisualSettings(), hybrid_source=HYBRID_V2_MODE, **kwargs):
        self.tracker_mode = kwargs.get("tracker_mode", RTM_POSE_2D_MODE)
        self.output_mode = kwargs.get("output_mode", "L0 Only")
        self.pose = self.tracker_mode == RTM_POSE_2D_MODE
        v2_pose = kwargs.pop("hybrid_v2_pose_enabled", False)
        self.pose_rotations = self.pose or (self.output_mode == "Six Axis" and v2_pose)
        self.settings = settings
        self.visual_frame = None
        self.last_timestamp = None
        self.resets = 0
        self.skipped = 0
        self.positions = {axis: 0.5 for axis in SIX_AXES}
        self.hybrid_source = HYBRID_V2_MODE
        self.hybrid_weight = kwargs.get("rtm_hybrid_l0_weight", 0.3)
        self.hybrid_enabled = self.pose and kwargs.get("rtm_hybrid_l0_enabled", False)
        # The existing 2D geometry helpers remain separate from the old async
        # inference path. Only this run's worker calls the model and the helpers.
        rotation_kwargs = dict(kwargs, tracker_mode=RTM_POSE_2D_MODE, rtm_pose_2d_enabled=self.pose_rotations,
                               rtm_pose_3d_enabled=False, rtm_hybrid_l0_enabled=False,
                               output_mode="Six Axis" if self.pose else self.output_mode)
        self.geometry = RealtimeAnalyzer(**rotation_kwargs)
        self.backend = self.geometry._rtm_pose_2d_backend if self.pose_rotations else None
        v1_keys = ('smoothing', 'deadzone', 'motion_gain', 'enable_smoothing', 'enable_deadzone',
                   'response_curve', 'visual_stroke_scale', 'l0_jitter_guard', 'l0_guard_strength',
                   'enable_extreme_reset', 'enable_endpoint_guard', 'endpoint_margin', 'compression_latency')
        v1_kwargs = {key: kwargs[key] for key in v1_keys if key in kwargs}
        self._v1_factory = lambda: RealtimeAnalyzer(tracker_mode=HYBRID_MODE, output_mode='L0 Only', **v1_kwargs)
        self._reset_tracking()

    @property
    def axes(self):
        return SIX_AXES.copy() if self.output_mode == "Six Axis" else ["L0"]

    def _rtm_pose_enabled(self):
        return self.pose_rotations

    def remember_l0_output(self, value):
        # Only a handoff anchor; never used as a motion/rhythm observation.
        if value is not None and np.isfinite(value) and not self.pose:
            if self.tracker_mode == STROKE_CYCLE_MODE:
                self.cycle.applied = float(value)
            else:
                self.point_l0.fusion.applied = float(value)

    def _reset_tracking(self):
        self.stabilizer = Stabilizer(self.settings.options)
        self.observations = ImageObservations()
        self.motion = CameraRelativeMotion()
        self.dominant = DominantMotion(adaptive_l0=True)
        self.frame_rotation = FrameRotation()
        self.secondary = SecondaryMotionFilter(self.positions)
        self.geometry.reset()
        self.pose_fallback = PoseL0Fallback()
        self.generated_l0 = None
        self.pose_pattern = PosePattern()
        self.pose_recovery = PoseL0Recovery()
        self.pose_l0_output = None
        self.pose_fast = PoseFastFallback(self._v1_factory)
        self.point_l0 = PointL0()
        self.reach_target = ReachTarget()
        self.subject_continuity = SubjectContinuity()
        self._subject_basis = ()

    def configure(self, settings):
        if settings != self.settings:
            output_only = (settings.edge == self.settings.edge and settings.options == self.settings.options
                           and settings.generation == self.settings.generation)
            previous = self.settings
            self.settings = settings
            if output_only:
                if settings.pose_auto_l0 != previous.pose_auto_l0:
                    self.pose_fallback = PoseL0Fallback()
                    self.generated_l0 = None
                if settings.pose_pattern != previous.pose_pattern:
                    self.pose_pattern = PosePattern()
                if settings.pose_fast_v1 != previous.pose_fast_v1:
                    self.pose_fast = PoseFastFallback(self._v1_factory)
                if settings.v2_l0_reference != previous.v2_l0_reference:
                    self.reach_target = ReachTarget()
                return
            self._reset_tracking()
            self.last_timestamp = None
            self.resets += 1

    def process(self, frame_bgr, timestamp=None):
        started = time.perf_counter()
        stamp = started if timestamp is None else timestamp
        if not np.isfinite(stamp) or (self.last_timestamp is not None and stamp <= self.last_timestamp):
            if self.visual_frame is None:
                raise ValueError("Invalid initial sample timestamp")
            held = {a: self.positions[a] for a in self.axes}
            if not self.pose_rotations and self.output_mode == "Six Axis":
                held.update(self.secondary.output)
            return AxisAnalysis(held, 0.0, 0.0, self.visual_frame.pair[1])
        gap = 0 if self.last_timestamp is None else stamp - self.last_timestamp
        frame = resize_for_processing(frame_bgr, self.settings.edge)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        inference_ms = 0.0
        reset = False
        confidence = 0.0
        rotations = {}
        hip_y = None
        if not self.pose_rotations:
            observation, vectors = self.motion.update(gray, stamp)
            marked = frame.copy()
            pair = (frame, marked)
            if observation.values is not None:
                self.positions.update(self.dominant.update(observation.values, stamp) or {})
                if self.output_mode == "Six Axis":
                    self.positions.update(self.dominant.map_rotations(self.frame_rotation.update(vectors, frame.shape)) or {})
                confidence = 1.0
            if observation.state == "holding":
                self.dominant.hold(stamp)
            reset = observation.state not in ("ready", "holding")
            if reset:
                had_reference = self.dominant.timestamp is not None
                self.dominant = DominantMotion(adaptive_l0=True)
                self.frame_rotation = FrameRotation()
                self.resets += int(had_reference)
        else:
            infer_start = time.perf_counter()
            result = self.backend.infer(frame)
            inference_ms = (time.perf_counter() - infer_start) * 1000
            if result is None and (self.backend._load_failed or "failed" in self.backend.status.lower()):
                raise RuntimeError(self.backend.status)
            raw = np.full((17, 2), np.nan, np.float32)
            scores = np.zeros(17)
            if result is not None:
                points = np.asarray(result.keypoints2d)
                if points.ndim != 2 or points.shape[0] < 17 or points.shape[1] != 2:
                    raise ValueError("Requires RTM Pose 2D keypoints / 需要 RTM Pose 2D 关键点")
                raw[:] = points[:17]
                scores[:] = result.scores[:17]
            filtered, rejected = self.stabilizer.update(gray, raw, scores, stamp)
            if (np.isfinite(filtered[[11, 12]]).all() and np.all(scores[[11, 12]] >= .35)
                    and not np.any(rejected[[11, 12]])):
                hip_y = float(np.mean(filtered[[11, 12], 1])/frame.shape[0])
            reset = bool(self.stabilizer.reset_reason)
            if reset:
                self.observations = ImageObservations()
                self.geometry.reset()
                if self.pose:
                    self.motion = CameraRelativeMotion()
                    self.dominant = DominantMotion(adaptive_l0=True)
                self.resets += 1
                if self.stabilizer.reset_reason != "gap" or gap > .5:
                    self.pose_fallback = PoseL0Fallback()
                self.pose_pattern = PosePattern()
                self.pose_recovery = PoseL0Recovery()
                self.pose_fast = PoseFastFallback(self._v1_factory)
                self.dominant.rotation_previous = None
            observation = self.observations.update(filtered, scores, rejected, frame.shape, stamp)
            if observation.values is not None:
                x, y, scale = observation.values
                if self.pose:
                    self.positions.update(L0=float(np.clip(0.5 + y / 100, 0, 1)),
                                          L1=float(np.clip(0.5 + scale / 100, 0, 1)),
                                          L2=float(np.clip(0.5 + x / 100, 0, 1)))
                confidence = float(np.clip(np.mean(scores[[5, 6, 11, 12]]), 0, 1))
                valid_scores = scores.copy()
                valid_scores[rejected | ~np.isfinite(filtered).all(axis=1)] = 0
                points3d = np.zeros((17, 3), np.float32)
                points3d[:, :2] = filtered
                sample = RtmPose3dResult(points3d, filtered, valid_scores)
                rotations, _ = self.geometry._positions_from_rtm_pose_2d(sample, frame.shape[:2], timestamp=stamp)
                if rotations and self.pose:
                    self.positions.update({a: rotations[a] for a in ("R0", "R1", "R2") if a in rotations})
            if self.hybrid_enabled:
                hybrid_observation, _ = self.motion.update(gray, stamp)
                hybrid_confidence = 1.0 if hybrid_observation.values is not None else 0.0
                hybrid_positions = self.dominant.update(hybrid_observation.values, stamp) if hybrid_confidence else None
                hybrid_l0 = hybrid_positions["L0"] if hybrid_positions else 0.5
                if hybrid_observation.state == "holding":
                    self.dominant.hold(stamp)
                elif not hybrid_confidence:
                    self.dominant = DominantMotion(adaptive_l0=True)
                if confidence > 0 and hybrid_confidence > 0:
                    self.positions["L0"] = self.positions["L0"] * (1 - self.hybrid_weight) + hybrid_l0 * self.hybrid_weight
            shown = raw.copy()
            shown[(scores < 0.35) | ~np.isfinite(scores)] = np.nan
            pair = (draw_pose(frame, shown, (40, 180, 255), rejected), draw_pose(frame, filtered, (255, 220, 40)))
            if observation.center is not None:
                cv2.drawMarker(pair[1], tuple(int(v) for v in observation.center), (240, 240, 240), cv2.MARKER_CROSS, 16, 2)
            if not self.pose:
                observation, vectors = self.motion.update(gray, stamp)
                confidence = 1.0 if observation.values is not None else 0.0
                if confidence:
                    self.positions.update(self.dominant.update(observation.values, stamp) or {})
                    self.positions.update(self.dominant.map_rotations(rotations) or {})
                elif observation.state == "holding":
                    self.dominant.hold(stamp)
                else:
                    self.dominant = DominantMotion(adaptive_l0=True)
                reset = not confidence and observation.state != "holding"
        self.generated_l0 = None
        l0_source = ""
        if self.pose:
            previous_count = self.pose_recovery.count
            self.pose_l0_output = self.pose_recovery.update(self.positions['L0'], stamp, hip_y)
            if self.pose_recovery.count != previous_count:
                self.pose_fallback = PoseL0Fallback()
        if self.pose and self.settings.pose_auto_l0:
            activity_axes = {}
            if observation.values is not None:
                activity_axes = dict(rotations or {})
                activity_axes.update({axis: self.positions[axis] for axis in ('L1', 'L2')})
            self.generated_l0 = self.pose_fallback.update(
                self.positions['L0'] if observation.values is not None else None,
                activity_axes, stamp, held_l0=self.positions['L0'], base_l0=self.pose_l0_output)
            l0_source = self.pose_fallback.source
        if self.pose and self.settings.pose_fast_v1:
            target = self.generated_l0 if self.generated_l0 is not None else self.pose_l0_output
            fallback = self.pose_fast.update(frame, stamp, observation.values is not None, target)
            if fallback is not None:
                self.generated_l0 = fallback
                l0_source = self.pose_fast.source
                # If v1 releases into auto generation, the next cosine entry
                # starts from the visible handoff target instead of a hidden wave.
                self.pose_fallback.output = fallback
                self.pose_fallback.source = 'v1'
                self.pose_fallback.holding_generated = True
        if self.pose and self.settings.pose_pattern:
            observed = {}
            if observation.values is not None:
                observed = {axis: self.positions[axis] for axis in ('L0', 'L1', 'L2')}
                observed.update({axis: value for axis, value in (rotations or {}).items() if axis.startswith('R')})
            # Fixed Pose base gains define comparable stroke units, independent
            # of user presets, travel, generated L0 and hardware coupling.
            observed = rtm_rotation_amplitudes(rtm_l0_amplitude(observed))
            if 'L0' in observed:
                observed['L0'] = self.pose_l0_output
            exclude_l0 = self.generated_l0 is not None or self.pose_recovery.transition_at is not None
            self.pose_pattern.update(observed, stamp, excluded=('L0',) if exclude_l0 else ())
        self.last_timestamp = stamp
        arrival = None
        estimate = None
        if not self.pose:
            # Display/output estimates never become camera observations or
            # train the dominant axes, reach target or motion history.
            estimate = self.subject_continuity.update(gray, stamp, self.motion.reference)
            if (self.motion.reference.state in ('ready', 'tracking')
                    and not self.subject_continuity.episode):
                self._subject_basis = self.dominant.axes_xyz
            elif self.motion.reference.reason == 'jump' or gap > .5:
                self._subject_basis = ()
            if estimate is not None:
                reset = False  # retain the observed chart through a bounded gap
            if self.settings.v2_l0_reference == 'fusion':
                arrival = self.reach_target.update(frame, self.dominant, self.motion.reference,
                    getattr(self.motion, 'target_data', None), stamp)
            self.positions['L0'] = self.point_l0.update(self.settings.v2_l0_reference,
                self.dominant, self.motion.reference, self.motion.interaction, stamp,
                frame.shape[:2], self.positions['L0'], arrival, estimate)
            if self.settings.v2_l0_reference == 'fusion' and self.point_l0.fusion.predicting:
                self.generated_l0 = self.positions['L0']
                l0_source = self.point_l0.fusion.continuation_kind or 'rhythm'
        output_positions = {a: self.positions[a] for a in self.axes}
        if not self.pose_rotations and self.output_mode == "Six Axis":
            # Process only valid image observations. Never feed the filtered
            # positions back into motion measurements or the primary L0.
            if confidence > 0:
                output_positions.update(self.secondary.update(self.positions, stamp))
            else:
                if observation.state != "holding":
                    self.secondary = SecondaryMotionFilter(self.secondary.output)
                output_positions.update(self.secondary.output)
        weights = None if self.pose else tuple(float(w) for w in self.dominant.weights)
        rotation_source = "pose" if self.pose_rotations else "image" if self.output_mode == "Six Axis" else ""
        reference = None
        if not self.pose or self.hybrid_enabled:
            reference = replace(self.motion.reference, weights=tuple(float(w) for w in self.dominant.weights),
                                span=self.dominant.stroke_span, gain=self.dominant.stroke_gain,
                                basis=self.dominant.axes_xyz, basis_state=self.dominant.basis_state,
                                basis_confidence=self.dominant.basis_confidence,
                                l0=float(self.positions["L0"]))
            if not self.pose:
                point = self.motion.interaction
                reference = replace(reference, stroke_center=self.point_l0.center,
                    interaction_point=tuple(point.point) if point.point is not None and point.state == 'ready' else None,
                    interaction_state=point.state, l0_reference=self.point_l0.source,
                    point_step=point.step if point.state == 'ready' else 0.)
                if self.settings.v2_l0_reference == 'fusion':
                    fused = self.point_l0.fusion
                    reference = replace(reference, target_point=fused.target, target_kind=fused.target_kind,
                        fusion_weights=fused.weights, direction_confirmed=fused.oriented,
                        continuation=fused.rhythm.state if fused.predicting else '',
                        continuation_elapsed=fused.rhythm.elapsed if fused.predicting else 0.,
                        continuation_kind=fused.continuation_kind if fused.predicting else '',
                        reach_state=arrival.state, reach_progress=None if arrival.remaining is None else 1-arrival.remaining,
                        target_box=arrival.box, target_samples=arrival.samples,
                        target_offscreen=(arrival.offscreen or (fused.target is not None and fused.target_kind.startswith('assumed') and
                            not (0 <= fused.target[0] < frame.shape[1] and 0 <= fused.target[1] < frame.shape[0]))),
                        reach_active=fused.arrival_active)
                if estimate is not None:
                    reference = replace(reference, estimate_state=estimate.state,
                        estimate_origin=estimate.origin, estimate_box=estimate.box,
                        estimate_elapsed=estimate.elapsed, estimate_basis=self._subject_basis)
                elif observation.values is None:
                    # The strict tracker has its own short hold grace. After
                    # our estimate expires, that old geometry is not a newly
                    # measured yellow subject. Hide it only in the snapshot.
                    reference = replace(reference, roi=None, subject_origin=None,
                        subject_box=None, basis=(), vectors=(), support_groups=())
            pair = (pair[0], draw_reference(pair[1], reference))
        if self.pose and self.settings.pose_fast_v1 and self.pose_fast.reference is not None:
            reference = self.pose_fast.reference
            pair = (pair[0], draw_reference(pair[1], reference))
        self.visual_frame = VisualFrame(pair, observation, self.pose_rotations, self.settings.generation, reset,
                                        inference_ms, (time.perf_counter() - started) * 1000,
                                        gap * 1000, self.resets, self.skipped, weights, rotation_source, reference, l0_source,
                                        self.pose_pattern.gains if self.pose and self.settings.pose_pattern else (),
                                        self.pose_recovery.count if self.pose else 0)
        return AxisAnalysis(output_positions, confidence, confidence, pair[1])


class StrokeCycleAnalyzer(LabAnalyzer):
    """A final L0 pattern on the actual v2 pipeline, not a fork of its analysis."""
    def _reset_tracking(self):
        super()._reset_tracking()
        self.cycle = StrokeCycle(self.positions["L0"])

    def process(self, frame_bgr, timestamp=None):
        result = super().process(frame_bgr, timestamp)
        stamp = self.last_timestamp
        reference = self.visual_frame.reference
        fusion = self.settings.v2_l0_reference == 'fusion'
        predicted = fusion and self.point_l0.fusion.predicting
        previous_value = self.cycle.value
        previous_state = self.cycle.state
        if predicted:
            value = (self.cycle.follow_phase(self.point_l0.fusion.output, stamp,
                held=self.point_l0.fusion.rhythm.state == 'held', predicted=True)
                if self.cycle.reference_peak is not None else self.cycle.hold(stamp))
        elif (fusion and reference is not None and reference.state in ('ready', 'tracking')
              and not np.any(reference.step) and reference.reach_progress is not None
              and self.cycle.reference_peak is not None):
            # Finish a confirmed arrival from the current output even when the
            # image pauses at contact. Keep the last measured travel class;
            # this is not new reciprocal evidence or a restarted oscillator.
            self.cycle.hold(stamp)
            if abs(self.cycle.reference_offset) < 1e-6:
                self.cycle.reference_offset = 0.
            value = self.cycle.follow_phase(self.point_l0.fusion.output, stamp)
            if self.point_l0.fusion.paused_since is not None and stamp-self.point_l0.fusion.paused_since >= .2:
                self.cycle.state = 'stopped'
        elif fusion and reference is not None and reference.state in ('ready', 'tracking') and not np.any(reference.step):
            value = self.cycle.hold(stamp)
            self.cycle.reference_time = stamp
            if self.point_l0.fusion.paused_since is not None and stamp-self.point_l0.fusion.paused_since >= .2:
                self.cycle.state = 'stopped'
        elif reference is not None and reference.state == "holding":
            value = self.cycle.hold(stamp)
        else:
            driver = self.point_l0.driver or self.dominant
            cycle_reference = replace(reference, step=(0., reference.point_step, 0.)) if self.point_l0.driver is not None else reference
            value = self.cycle.update(driver, cycle_reference, stamp,
                                      reference is not None and reference.state in ("ready", "tracking"))
            if fusion and self.cycle.state != 'stopped' and np.any(reference.step):
                self.cycle.value = previous_value
                value = self.cycle.follow_phase(self.point_l0.fusion.output, stamp,
                                               entering=previous_state == 'stopped')
        if predicted:
            self.generated_l0 = value
        elif fusion:
            self.generated_l0 = None
        positions = {a: .5 for a in self.axes}
        positions["L0"] = value
        if self.pose_rotations:
            positions.update({a: v for a, v in result.positions.items() if a.startswith("R")})
        self.positions.update(positions)
        if reference is not None:
            reference = replace(reference, l0=value, pattern=self.cycle.state, period=self.cycle.period,
                                span=self.point_l0.driver.stroke_evidence.span if self.point_l0.driver is not None else reference.span)
        self.visual_frame = replace(self.visual_frame, reference=reference,
                                    rotation_source="pose" if self.pose_rotations else "")
        return AxisAnalysis(positions, result.confidence, result.activity, result.preview_bgr)


def make_analyzer(*, visual_settings=VisualSettings(), hybrid_source=HYBRID_V2_MODE, **kwargs):
    mode = kwargs.get("tracker_mode", HYBRID_MODE)
    if mode == STROKE_CYCLE_MODE:
        return StrokeCycleAnalyzer(settings=visual_settings, hybrid_source=hybrid_source, **kwargs)
    if mode in (HYBRID_V2_MODE, RTM_POSE_2D_MODE):
        return LabAnalyzer(settings=visual_settings, hybrid_source=hybrid_source, **kwargs)
    kwargs.pop("hybrid_v2_pose_enabled", None)
    # Leave the original hybrid L0 implementation and its processing untouched.
    if mode == HYBRID_MODE:
        kwargs["output_mode"] = "L0 Only"
    return RealtimeAnalyzer(**kwargs)
