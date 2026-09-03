from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from .analyzer import RealtimeAnalyzer
from .recorder import MultiAxisFunscriptRecorder


def analyze_video(
    video_path: Path,
    output_path: Path,
    output_mode: str = "L0 Only",
    tracker_mode: str = "混合分析（推荐-非舞蹈）",
    fps: int = 30,
    smoothing: float = 0.35,
    deadzone: float = 0.015,
    motion_gain: float = 1.0,
    visual_stroke_scale: float = 0.72,
    enable_extreme_reset: bool = True,
    enable_endpoint_guard: bool = True,
    endpoint_margin: float = 0.10,
    pose_dance_mode: bool = False,
    pose_dance_l0: bool | None = None,
    pose_dance_six_axis: bool | None = None,
    pose_l0_weight: float = 0.60,
    pose_six_axis_weight: float = 0.60,
) -> list[Path]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {video_path}")

    analyzer = RealtimeAnalyzer(
        tracker_mode,
        output_mode,
        smoothing,
        deadzone,
        motion_gain,
        visual_stroke_scale=visual_stroke_scale,
        enable_extreme_reset=enable_extreme_reset,
        enable_endpoint_guard=enable_endpoint_guard,
        endpoint_margin=endpoint_margin,
        pose_dance_mode=pose_dance_mode,
        pose_dance_l0=pose_dance_l0,
        pose_dance_six_axis=pose_dance_six_axis,
        pose_l0_weight=pose_l0_weight,
        pose_six_axis_weight=pose_six_axis_weight,
    )
    recorder = MultiAxisFunscriptRecorder()
    recorder.start()
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    target_fps = max(1, min(60, fps))
    frame_step = max(1, round(native_fps / target_fps))
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % frame_step == 0:
                result = analyzer.process(frame)
                at = int(cap.get(cv2.CAP_PROP_POS_MSEC))
                if at <= 0:
                    at = round(index / native_fps * 1000)
                recorder.add_at(result.positions, at)
            index += 1
    finally:
        cap.release()
    recorder.stop()
    return recorder.save(output_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a video into funscript files.")
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--output-mode", choices=["L0 Only", "Six Axis"], default="L0 Only")
    parser.add_argument(
        "--tracker-mode",
        choices=[
            "混合分析（推荐-非舞蹈）",
            "混合分析",
            "Stroke Phase（内测用）",
            "Stroke Phase",
            "Motion Center（内测用）",
            "Motion Center",
            "Optical Flow（内测用）",
            "Optical Flow",
            "Hybrid Motion（内测用）",
            "Hybrid Motion",
            "Activity Pulse（内测用）",
            "Activity Pulse",
        ],
        default="混合分析（推荐-非舞蹈）",
    )
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--smoothing", type=float, default=0.35)
    parser.add_argument("--deadzone", type=float, default=0.015)
    parser.add_argument("--motion-gain", type=float, default=1.0)
    parser.add_argument("--visual-stroke-scale", type=float, default=0.72)
    parser.add_argument("--disable-extreme-reset", action="store_true")
    parser.add_argument("--disable-endpoint-guard", action="store_true")
    parser.add_argument("--endpoint-margin", type=float, default=0.10)
    parser.add_argument("--pose-dance", action="store_true")
    parser.add_argument("--pose-l0", action="store_true")
    parser.add_argument("--pose-six-axis", action="store_true")
    parser.add_argument("--pose-l0-weight", type=float, default=0.60)
    parser.add_argument("--pose-six-axis-weight", type=float, default=0.60)
    args = parser.parse_args(argv)

    written = analyze_video(
        args.video,
        args.output,
        args.output_mode,
        args.tracker_mode,
        args.fps,
        args.smoothing,
        args.deadzone,
        args.motion_gain,
        args.visual_stroke_scale,
        not args.disable_extreme_reset,
        not args.disable_endpoint_guard,
        args.endpoint_margin,
        args.pose_dance,
        args.pose_l0 or None,
        args.pose_six_axis or None,
        args.pose_l0_weight,
        args.pose_six_axis_weight,
    )
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
