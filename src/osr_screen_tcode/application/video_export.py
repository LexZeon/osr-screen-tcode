"""Offline video analysis and recording/script file actions.

Moved without changing behavior for 2.1.0; application state remains on self.
"""
from __future__ import annotations
import threading
import time
from pathlib import Path
from tkinter import filedialog
import cv2
from ..analyzer import SIX_AXES
from ..output_curve import OutputCurveFilter
from ..visual_pipeline import LabAnalyzer, VisualFrame
from ..recorder import MultiAxisFunscriptRecorder


class VideoExportMixin:
    def pick_video(self) -> None:
        path = filedialog.askopenfilename(
            title=self._t("选择视频文件"),
            filetypes=(
                ("Video", "*.mp4 *.mkv *.avi *.mov *.webm *.m4v"),
                ("All files", "*.*"),
            ),
        )
        if path:
            self.video_path.set(path)
            self.source_mode.set("Video File")

    def analyze_video_file(self) -> None:
        if (self.worker and self.worker.is_alive()) or self._video_analysis_active():
            self.status.set(self._dt("请先停止当前分析，再导出视频脚本。", "Stop the current analysis before exporting a video script."))
            return
        path = self.video_path.get()
        if not path:
            self.pick_video()
            path = self.video_path.get()
        if not path:
            return
        save_path = filedialog.asksaveasfilename(
            title=self._t("选择脚本保存基名"),
            defaultextension=".funscript",
            initialfile=f"{Path(path).stem}.funscript",
            filetypes=(("Funscript", "*.funscript"), ("All files", "*.*")),
        )
        if not save_path:
            return
        self.status.set(self._t("视频分析中..."))
        self._video_cancel.clear()
        self._active_screen_region = None
        self.reset_visual_reference()

        def worker() -> None:
            try:
                written = self._analyze_video_worker(Path(path), Path(save_path))
                if not self._video_cancel.is_set():
                    self._queue_latest({"export_done": True, "status_text": f"{self._t('视频分析完成')}: {len(written)} {self._t('个脚本')}"})
            except Exception as exc:
                if not self._video_cancel.is_set():
                    self._queue_latest({"error": f"{self._t('视频分析失败')}: {exc}"})

        self._video_worker = threading.Thread(target=worker, daemon=True)
        self._video_worker.start()
        self._refresh_region_controls()

    def _video_analysis_active(self) -> bool:
        return bool(self._video_worker and self._video_worker.is_alive())

    def _analyze_video_worker(self, video_path: Path, save_path: Path) -> list[Path]:
        self._six_axis_stable_positions = {axis: 0.5 for axis in SIX_AXES}
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
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            cap.release()
            raise ValueError(f"{self._t('无法打开视频')}: {video_path}")
        recorder = MultiAxisFunscriptRecorder()
        curve = OutputCurveFilter()
        recorder.start()
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        target_fps = max(1, min(60, self.fps.get()))
        frame_step = max(1, round(native_fps / target_fps))
        index = 0
        last_update = 0.0
        try:
            while not self._video_cancel.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                if index % frame_step != 0:
                    index += 1
                    continue
                at = round(index / native_fps * 1000)
                visual = isinstance(analyzer, LabAnalyzer)
                generation = self._visual_settings.generation
                if visual:
                    analyzer.configure(self._visual_settings)
                else:
                    if getattr(analyzer, "_reference_generation", generation) != generation:
                        analyzer.reset()
                    analyzer._reference_generation = generation
                analysis_frame = frame if visual else self._prepare_analysis_frame(frame)
                result = analyzer.process(analysis_frame, timestamp=index / native_fps) if visual else analyzer.process(analysis_frame)
                if self._video_cancel.is_set():
                    break
                positions = self._visual_output_positions(analyzer, result.positions)
                positions = curve.process(positions, enabled=self._output_curve_enabled, timestamp=at / 1000.0,
                                          passthrough=self._generated_l0_axes(analyzer))
                if visual and analyzer.pose and analyzer.settings.pose_fast_v1:
                    analyzer.pose_fast.remember_output(positions.get('L0'))
                if visual and not analyzer.pose:
                    analyzer.remember_l0_output(positions.get('L0'))
                output_positions = self._positions_with_travel_controls(positions)
                recorder.add_at(output_positions, at, *self._endpoint_options)
                now = time.perf_counter()
                if now - last_update > 0.25:
                    progress = f"{index}/{total}" if total else str(index)
                    self._queue_latest(
                        {
                            "visual_frame": analyzer.visual_frame if visual else VisualFrame(
                                (analysis_frame, result.preview_bgr), None, False, generation,
                                reference=getattr(analyzer, "motion_reference", None)),
                            "status_text": f"{self._t('视频分析中...')} {progress}",
                            "record_count": recorder.action_count,
                        }
                    )
                    last_update = now
                index += 1
        finally:
            cap.release()
        recorder.stop()
        if self._video_cancel.is_set():
            return []
        return recorder.save(save_path)

    def start_recording(self) -> None:
        self.recorder.start()
        self.record_status.set(f"{self._t('录制中')}: 0 {self._t('点')}")

    def save_recording(self) -> None:
        if self.recorder.is_recording:
            self.recorder.stop()
        path = filedialog.asksaveasfilename(
            title=self._t("保存 funscript"),
            defaultextension=".funscript",
            filetypes=(("Funscript", "*.funscript"), ("JSON", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        self.recorder.save(Path(path))
        self.record_status.set(f"{self._t('已保存:')} {self.recorder.action_count} {self._t('点')}")
