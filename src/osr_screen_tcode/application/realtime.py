"""Realtime worker lifecycle, screen/video/audio capture and frame processing.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import threading
import time
import cv2
import numpy as np
from ..analyzer import SIX_AXES, RealtimeAnalyzer
from ..audio import AudioAnalyzer, AudioCapture
from ..output_curve import OutputCurveFilter
from ..visual_pipeline import LabAnalyzer, VisualFrame
from ..sinks import OutputWriteError
from ..tcode import MultiAxisSafeOutput


class RealtimeMixin:
    def start(self) -> None:
        if self._video_analysis_active():
            self.status.set(self._dt("请先停止视频导出，再开始实时分析。", "Stop video export before starting live analysis."))
            return
        if self.worker and self.worker.is_alive():
            return
        self.update_idletasks()
        self._startup_window_geometry = self.geometry()
        self.source_mode.set("Screen")
        if not self._confirm_realtime_start():
            self._startup_window_geometry = None
            return
        if not self._validate_start_region():
            self._startup_window_geometry = None
            return
        if not self._ensure_rtm_pose_model_ready():
            self._startup_window_geometry = None
            return
        if not self.connected:
            self._start_after_connect = True
            self.connect_sink()
            if not self.connected:
                if self._connecting:
                    self.status.set(self._t("正在连接，连接成功后会开始实时输出"))
                self._startup_window_geometry = None
                return
            self._start_after_connect = False
        self._begin_realtime_output()

    def _begin_realtime_output(self) -> None:
        if self._video_analysis_active():
            self.status.set(self._dt("请先停止视频导出，再开始实时分析。", "Stop video export before starting live analysis."))
            return
        if self._gpu_installing or (self._gpu_restart_required and self.rtm_pose_gpu_enabled.get()):
            self.status.set(self._dt("GPU 运行库安装后请重启软件；也可关闭 GPU 使用 CPU。", "Restart after GPU installation, or disable GPU to use CPU."))
            return
        if self.worker and self.worker.is_alive():
            return
        if not self.connected:
            return
        self._live_source_mode = self.source_mode.get()
        if self._live_source_mode == "Screen" and not self._validate_start_region():
            return
        self._active_screen_region = self._screen_region_snapshot if self._live_source_mode == "Screen" else None
        self._normalize_limits()
        self._script_history.clear()
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
        self._draw_script_curve()
        self.stop_event.clear()
        self.reset_visual_reference()
        self.capture_rate_text.set("")
        self.worker = threading.Thread(target=self._run_capture, daemon=True)
        self.worker.start()
        self._refresh_region_controls()
        self._set_device_controls_busy(True)
        self._refresh_start_button_text()
        self.status.set(self._t("实时输出中"))
        self._restore_start_geometry_once()
        self.after(180, self._release_start_geometry)

    def stop(self) -> None:
        self._video_cancel.set()
        self.capture_rate_text.set("")
        self._start_after_connect = False
        self.stop_event.set()
        # Let Tk service outstanding variable reads while the worker observes stop_event.
        # A new worker cannot start until this one exits.
        if not self.worker or not self.worker.is_alive():
            self.worker = None
        self._set_device_controls_busy(self._connecting or bool(self.worker))
        self._refresh_region_controls()
        self._startup_window_geometry = None
        self._refresh_start_button_text()
        self.status.set(self._t("已停止") if self.connected else self._t("未连接"))

    def estop(self) -> None:
        self.stop()
        self.send_center(interval_ms=600)
        self.status.set(self._t("已急停并回中"))

    def _run_capture(self) -> None:
        self._output_context.sink = self.sink
        try:
            self._output_context.curve = OutputCurveFilter()
            self._normalize_limits()
            fps = max(1, min(120, self.fps.get()))
            period = 1.0 / fps
            if self._live_source_mode == "Audio Only":
                self._run_audio(period)
                return
            analyzer = self._create_analyzer(
                v2_model_options=dict(self._v2_model_options),
                visual_settings=self._visual_settings, hybrid_source=self.rtm_hybrid_source.get(),
                hybrid_v2_pose_enabled=self.hybrid_v2_pose_enabled.get(),
                tracker_mode=self._tracker_internal(self.tracker_mode.get()),
                output_mode=self.output_mode.get(),
                smoothing=self.smoothing.get(),
                deadzone=self.deadzone.get(),
                motion_gain=self.motion_gain.get(),
                enable_smoothing=self.enable_smoothing.get(),
                enable_deadzone=self.enable_deadzone.get(),
                response_curve=self.response_curve.get(),
                visual_stroke_scale=self.visual_stroke_scale.get(),
                l0_jitter_guard=self.enable_l0_jitter_guard.get(),
                l0_guard_strength=self.l0_guard_strength.get(),
                enable_extreme_reset=self.enable_extreme_reset.get(),
                enable_endpoint_guard=self.enable_endpoint_guard.get(),
                endpoint_margin=self.endpoint_margin_pct.get() / 200.0,
                pose_dance_l0=False,
                pose_dance_six_axis=False,
                pose_l0_weight=0.0,
                pose_six_axis_weight=0.0,
                pose_v2_dance_six_axis=False,
                pose_v2_l0_weight=0.0,
                pose_v2_six_axis_weight=0.0,
                rtm_pose_2d_enabled=self._rtm_pose_2d_mode_active(),
                rtm_pose_2d_model_path=self.rtm_pose_2d_model_path.get(),
                rtm_pose_3d_enabled=self._rtm_pose_3d_mode_active(),
                rtm_pose_3d_model_path=self.rtm_pose_3d_model_path.get(),
                rtm_pose_3d_weight=1.0 if self._rtm_pose_mode_active() else 0.0,
                rtm_hybrid_l0_enabled=self._rtm_pose_mode_active() and self.rtm_hybrid_l0_enabled.get(),
                rtm_hybrid_l0_weight=self.rtm_hybrid_l0_weight.get() / 100.0,
                rtm_pose_gpu_enabled=self.rtm_pose_gpu_enabled.get(),
                rtm_pose_gpu_backend=self.rtm_pose_gpu_backend.get(),
                rtm_pose_flow_enabled=self.rtm_pose_flow_enabled.get(),
                rtm_pose_kalman_enabled=self.rtm_pose_kalman_enabled.get(),
                compression_latency=self.compression_latency.get(),
            )
            output = self._new_output(self.interval_ms.get())
            if self._live_source_mode == "Video File":
                self._run_video(analyzer, output, period, 0.0)
            else:
                self._run_screen(analyzer, output, period, 0.0)
        except OutputWriteError as exc:
            pass  # _emit_command already queued one failure for the GUI thread.
        except Exception as exc:
            self._queue_latest({"error": f"{type(exc).__name__}: {exc}"})
        finally:
            self._queue_latest({"capture_stopped": True})

    def _run_screen(
        self,
        analyzer: RealtimeAnalyzer,
        output: MultiAxisSafeOutput,
        period: float,
        last_preview: float,
    ) -> None:
        region = self._screen_region_snapshot
        sequence = 0
        measured_at = time.perf_counter()
        processed = 0
        processing_fps = 0.0
        with self._create_screen_capture(region, lambda: self._capture_target_fps) as capture:
            while not self.stop_event.is_set():
                sample = capture.next_frame(sequence)
                if sample is None or self.stop_event.is_set():
                    continue
                sequence = sample.sequence
                now = time.perf_counter()
                if now - measured_at >= 0.5:
                    processing_fps = processed / (now - measured_at)
                    measured_at, processed = now, 0
                stats = (sample.fps, processing_fps, max(0.0, now - sample.captured_at) * 1000.0)
                last_preview = self._process_frame(analyzer, output, sample.bgr, last_preview, capture_stats=stats, timestamp=sample.captured_at)
                processed += 1

    def _run_video(
        self,
        analyzer: RealtimeAnalyzer,
        output: MultiAxisSafeOutput,
        period: float,
        last_preview: float,
    ) -> None:
        path = self.video_path.get()
        if not path:
            raise ValueError("请选择视频文件")
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {path}")
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps and video_fps > 1:
            period = 1.0 / min(120.0, video_fps)
        visual = isinstance(analyzer, LabAnalyzer)
        native_fps = video_fps if np.isfinite(video_fps) and video_fps > 0 else 30.0
        playback_start = time.perf_counter()
        index = 0
        try:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                if visual:
                    target = int((started - playback_start) * native_fps)
                    while index < target and not self.stop_event.is_set():
                        if not cap.grab():
                            break
                        index += 1
                        analyzer.skipped += 1
                ok, frame = cap.read()
                if not ok:
                    self._queue_latest({"error": "视频分析完成"})
                    break
                last_preview = self._process_frame(analyzer, output, frame, last_preview, timestamp=index / native_fps)
                index += 1
                sleep_for = (playback_start + index / native_fps - time.perf_counter()) if visual else period - (time.perf_counter() - started)
                if sleep_for > 0:
                    self.stop_event.wait(sleep_for)
        finally:
            cap.release()

    def _run_audio(self, period: float) -> None:
        analyzer = AudioAnalyzer(
            self.audio_mode.get(),
            self.audio_gain.get(),
            self.audio_threshold.get(),
            self.audio_smoothing.get(),
        )
        output = self._new_output(self.interval_ms.get())
        self._queue_latest({"status_text": "声音监听中"})
        last_update = 0.0
        with AudioCapture(self.audio_device.get()) as capture:
            while not self.stop_event.is_set():
                samples, duration = capture.read()
                result = analyzer.process(samples, duration or period)
                positions = self._apply_six_axis_tuning(result.positions)
                positions = self._fit_output_curve(positions)
                self._refresh_live_output_mapping(output)
                command = output.next_command(positions, result.activity)
                command_text = self._emit_command(command)
                if self.recorder.is_recording:
                    self.recorder.add(self._positions_with_travel_controls(positions), *self._endpoint_options)
                now = time.perf_counter()
                if now - last_update > 0.08:
                    self._queue_latest(
                        {
                            "command": command_text,
                            "activity": result.activity,
                            "audio_level": result.level,
                            "record_count": self.recorder.action_count,
                        }
                    )
                    last_update = now

    def _process_frame(
        self,
        analyzer: RealtimeAnalyzer,
        output: MultiAxisSafeOutput,
        frame: object,
        last_preview: float,
        capture_stats: tuple[float, float, float] | None = None,
        timestamp: float | None = None,
    ) -> float:
        visual = isinstance(analyzer, LabAnalyzer)
        analysis_frame = frame if visual else self._prepare_analysis_frame(frame)
        self._refresh_live_output_mapping(output)
        if visual:
            analyzer.configure(self._visual_settings)
            if analyzer.pose and analyzer.settings.pose_fast_v1:
                analyzer.pose_fast.remember_output(output.input_position('L0'))
            elif not analyzer.pose:
                analyzer.remember_l0_output(output.input_position('L0'))
            result = analyzer.process(analysis_frame, timestamp=timestamp)
            if analyzer.settings != self._visual_settings or self.stop_event.is_set():
                return last_preview
        else:
            generation = self._visual_settings.generation
            if getattr(analyzer, "_reference_generation", generation) != generation:
                analyzer.reset()
            analyzer._reference_generation = generation
            result = analyzer.process(analysis_frame)
            if generation != self._visual_settings.generation or self.stop_event.is_set():
                return last_preview
        positions = self._visual_output_positions(analyzer, result.positions)
        generated_axes = self._generated_l0_axes(analyzer)
        positions = self._fit_output_curve(positions, passthrough=generated_axes)
        command = output.next_command(positions, 1.0 if generated_axes else result.activity)
        command_text = self._emit_command(command)
        if self.recorder.is_recording:
            self.recorder.add(self._positions_with_travel_controls(positions), *self._endpoint_options)
        now = time.perf_counter()
        if now - last_preview >= 1.0 / min(60, self._capture_target_fps):
            self._queue_latest(
                {
                    "visual_frame": analyzer.visual_frame if visual else VisualFrame(
                        (analysis_frame, result.preview_bgr), None, False, self._visual_settings.generation,
                        reference=getattr(analyzer, "motion_reference", None)),
                    "command": command_text,
                    "activity": result.activity,
                    "record_count": self.recorder.action_count,
                    "capture_stats": capture_stats,
                }
            )
            return now
        return last_preview

    def _prepare_analysis_frame(self, frame: object) -> object:
        scale = self._analysis_frame_scale()
        if scale >= 0.999:
            return frame
        try:
            height, width = frame.shape[:2]
        except AttributeError:
            return frame
        # Preserve the complete ROI and its aspect ratio, including thin strips.
        scale = max(scale, min(1.0, 64.0 / max(1, min(width, height))))
        target_width = max(1, int(round(width * scale)))
        target_height = max(1, int(round(height * scale)))
        if target_width == width and target_height == height:
            return frame
        return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)

    def _capture_preview_for_display(self, capture_frame: object, analysis_frame: object, analysis_preview: object) -> object:
        try:
            capture_height, capture_width = capture_frame.shape[:2]
            analysis_height, analysis_width = analysis_frame.shape[:2]
            preview_height, preview_width = analysis_preview.shape[:2]
        except AttributeError:
            return analysis_preview
        display = analysis_preview
        if self._rtm_pose_mode_active() and preview_height == analysis_height and preview_width > analysis_width:
            overlay = analysis_preview[:, :analysis_width].copy()
            panel = analysis_preview[:, analysis_width:].copy()
            overlay_display = cv2.resize(overlay, (capture_width, capture_height), interpolation=cv2.INTER_NEAREST)
            panel_width = max(1, int(round(panel.shape[1] * capture_height / max(1, analysis_height))))
            panel_display = cv2.resize(panel, (panel_width, capture_height), interpolation=cv2.INTER_NEAREST)
            return np.concatenate((overlay_display, panel_display), axis=1)
        if preview_height == analysis_height and preview_width >= analysis_width:
            display = analysis_preview[:, :analysis_width].copy()
        try:
            display_height, display_width = display.shape[:2]
        except AttributeError:
            return analysis_preview
        if display_width == capture_width and display_height == capture_height:
            return display
        return cv2.resize(display, (capture_width, capture_height), interpolation=cv2.INTER_NEAREST)
