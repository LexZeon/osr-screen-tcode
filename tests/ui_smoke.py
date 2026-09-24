"""Visible UI checks using fake device data, without saving settings or opening hardware."""
import argparse
from dataclasses import replace
from pathlib import Path
import tempfile
from PIL import ImageGrab
from unittest.mock import patch

from osr_screen_tcode import __version__
from osr_screen_tcode.app import OsrScreenApp
from osr_screen_tcode.config import AppConfig, RTM_POSE_2D_MODE, HYBRID_V2_MODE, STROKE_CYCLE_MODE


parser = argparse.ArgumentParser()
parser.add_argument("case", choices=("log", "popup", "gpu-progress", "dance", "dance-popup", "pose-output", "references-v1", "references-v2", "cycle", "cycle-popup", "quarter"))
parser.add_argument("--band", action="store_true")
parser.add_argument("--closeup", action="store_true")
parser.add_argument("--fast-window", action="store_true")
parser.add_argument("--diagnostic", action="store_true")
parser.add_argument("--oblique", action="store_true")
parser.add_argument("--deforming", action="store_true")
parser.add_argument("--deformation", type=float, default=12.)
parser.add_argument("--competing", action="store_true")
parser.add_argument("--radial", action="store_true")
parser.add_argument("--distant-target", action="store_true")
parser.add_argument("--reach-target", action="store_true")
parser.add_argument("--offscreen-target", action="store_true")
parser.add_argument("--visible-proxy", action="store_true")
parser.add_argument("--blurred-subject", action="store_true")
parser.add_argument("--reference-loss", action="store_true")
parser.add_argument("--point-reference", choices=("fusion", "motion", "center", "interaction"), default="fusion")
parser.add_argument("--repeat", action="store_true")
parser.add_argument("--seconds", type=int, default=5)
parser.add_argument("--screenshot", action="store_true")
parser.add_argument("--language", default="zh")
parser.add_argument("--v2", action="store_true")
parser.add_argument("--pose-assist", action="store_true")
parser.add_argument("--pose-loss", action="store_true")
parser.add_argument("--backend", choices=("cuda", "directml"), default="cuda")
args = parser.parse_args()
with patch.object(AppConfig, "load", return_value=AppConfig(last_sink="Log only")), patch.object(AppConfig, "save"):
    app = OsrScreenApp(enforce_age_gate=False, ui_language=args.language)
    app.title("UI Check - " + app.title())
    app.geometry("1160x850+50+50")
    app.v2_l0_reference.set(args.point_reference)
    if args.v2:
        app._set_tracker_mode(HYBRID_V2_MODE)
        app.output_mode.set("Six Axis")
        app.hybrid_v2_pose_enabled.set(args.pose_assist)
    # Settle initial geometry before synchronous frame preparation delays Tk.
    app.update_idletasks()
    if args.screenshot:
        app.attributes("-topmost", True)
        def capture():
            import tkinter as tk
            target = next((w for w in app.winfo_children() if isinstance(w, tk.Toplevel)), app)
            target.update()
            x, y = target.winfo_rootx(), target.winfo_rooty()
            path = Path(tempfile.gettempdir()) / f"simulation-{__version__}-{args.case}-{args.language}.png"
            try:
                # Capture this test window even if another window covers it.
                shot = ImageGrab.grab(window=int(target.wm_frame(), 0))
            except TypeError:  # Older Pillow versions lack window capture.
                shot = ImageGrab.grab(bbox=(x, y, x + target.winfo_width(), y + target.winfo_height()))
            shot.save(path)
            print(path)
    if args.case.startswith("references-") or args.case in ("cycle", "quarter"):
        import cv2
        import numpy as np
        from motion_scenes import MotionScene, ReachScene, CompetingScene, difficult_scene, closeup_scene, window_scene, deforming_frame, distant_target_frame
        from osr_screen_tcode.config import HYBRID_MODE
        from osr_screen_tcode.visual_pipeline import make_analyzer, VisualFrame
        mode = STROKE_CYCLE_MODE if args.case in ("cycle", "quarter") else HYBRID_MODE if args.case.endswith("v1") else HYBRID_V2_MODE
        engine = make_analyzer(tracker_mode=mode, output_mode=app.output_mode.get(),
                               hybrid_v2_pose_enabled=args.pose_assist, visual_settings=app._visual_settings)
        if args.pose_assist:
            from test_visual_pipeline import FakePose
            engine.backend = FakePose()
        scene = window_scene() if args.fast_window else closeup_scene() if args.closeup else difficult_scene("band") if args.band else MotionScene()
        snapshots = []
        competing = CompetingScene() if args.competing else None
        reach_scene = ReachScene(target=not args.visible_proxy) if (args.reach_target or args.offscreen_target or args.visible_proxy) else None
        for i in range(173 if args.reference_loss else 151):
            t = i/30
            if mode == HYBRID_MODE:
                frame = np.zeros((240, 320, 3), np.uint8)
                y = round(45+25*np.sin(t*5))
                cv2.rectangle(frame, (70, y), (210, y+70), (190, 210, 180), -1)
                result = engine.process(frame)
                shown = VisualFrame((frame, result.preview_bgr), None, False,
                                    app._visual_settings.generation, reference=engine.motion_reference)
            else:
                frame = (reach_scene.frame(t, camera_x=max(0, i-120)*6 if args.offscreen_target else 0)[0] if reach_scene is not None else
                    distant_target_frame(scene, t)[0] if args.distant_target else
                    competing.frame(t) if competing is not None else
                    scene.frame(scale=np.exp(.1*np.sin(t*5)), camera_x=3*np.sin(t*3)) if args.radial else
                    deforming_frame(scene, t, deformation=args.deformation, y=20*np.sin(t*5), camera_x=3*np.sin(t*3)) if args.deforming else
                    scene.frame(x=-10*np.sin(t*5), y=14*np.sin(t*5), scale=np.exp(.035*np.sin(t*5)), camera_x=4*np.sin(t*3)) if args.oblique else
                    scene.frame(y=75*np.sin(i*2*np.pi/12)) if args.fast_window else
                    scene.frame(y=(2 if args.case == "quarter" else 6)*np.sin(t*5),
                    camera_x=(4 if args.closeup else 12)*np.sin(t*3), camera_y=(2 if args.closeup else 8)*np.sin(t*2)))
                if args.reference_loss and i >= 151:
                    with patch.object(engine.motion, '_camera', return_value=(None, None)):
                        engine.process(frame, t)
                else:
                    if args.blurred_subject and i > 25 and i%3 == 0:
                        frame[120:244] = cv2.GaussianBlur(frame[120:244], (31, 31), 8)
                    engine.process(frame, t)
                if args.repeat:
                    for j in (1, 2):
                        engine.process(frame, t+j/90)
                shown = engine.visual_frame
            snapshots.append(shown)
        def display_references():
            # Switch after the window has mapped, as a user opening the tab
            # would. Precomputing frames before mainloop delays initial paint.
            app._set_tracker_mode(mode)
            app.preview_tabs.select(app.analysis_tab)
            app.update_idletasks()
            for shown in snapshots:
                if shown.observation is not None:
                    app.integrated_preview.history.append(shown.observation)
            selected = snapshots[1 if args.diagnostic else -1]
            if args.offscreen_target:
                selected = next(s for s in reversed(snapshots) if s.reference.target_offscreen)
            elif args.reach_target:
                selected = next(s for s in reversed(snapshots) if s.reference.reach_progress is not None)
            app.integrated_preview.display(replace(selected, generation=app._visual_settings.generation))
        app.after(1000, display_references)
    if args.case == "cycle-popup":
        app._set_tracker_mode(STROKE_CYCLE_MODE)
        app.output_mode.set("Six Axis")
        app.after(100, app._confirm_realtime_start)
    if args.case == 'pose-output':
        import numpy as np
        from osr_screen_tcode.visual_pipeline import make_analyzer
        from test_visual_pipeline import FakePose
        app._set_tracker_mode(RTM_POSE_2D_MODE)
        app.output_mode.set('Six Axis')
        app.pose_pattern_enabled.set(True)
        engine = make_analyzer(tracker_mode=RTM_POSE_2D_MODE, output_mode='Six Axis', visual_settings=app._visual_settings)
        engine.backend = FakePose()
        engine.geometry._positions_from_rtm_pose_2d = lambda sample, shape, timestamp: (
            {'R0': .5+.02*np.sin(timestamp*2*np.pi), 'R1': .5, 'R2': .5}, None)
        frame = np.zeros((400, 400, 3), np.uint8)
        for i in range(50 if args.pose_loss else 301):
            if args.pose_loss:
                import cv2
                frame = np.zeros((400, 400, 3), np.uint8)
                y = 120 if i < 20 else 120+(i-20)*5
                cv2.rectangle(frame, (95, y), (245, y+80), (200, 210, 180), -1)
                engine.backend.missing = i >= 20
            engine.process(frame, i/30)
        def display_pose():
            app.preview_tabs.select(app.analysis_tab)
            app.integrated_preview.display(engine.visual_frame)
        app.after(100, display_pose)
    if args.case in {"dance", "dance-popup"}:
        app._set_tracker_mode(RTM_POSE_2D_MODE)
        app.show_rtm_pose_3d_settings.set(True)
        if args.case == "dance-popup":
            app.after(100, app._confirm_realtime_start)
    if args.case in {"popup", "gpu-progress"}:
        app._set_tracker_mode(RTM_POSE_2D_MODE)
        app.rtm_pose_gpu_backend.set(args.backend)
        app._gpu_result = {"nvidia": args.backend == "cuda", "cuda": False, "reason": "cpu_ort" if args.backend == "cuda" else "dml_missing"}
        app.rtm_pose_gpu_enabled.set(True)
        if args.case == "gpu-progress":
            app._gpu_installing = True
            app._gpu_stage = "downloading"
            app._gpu_progress = {"stage": "downloading", "component": "nvidia-cudnn-cu12", "index": 3,
                "count": 9, "downloaded": 256 * 1024 ** 2, "total": 1024 * 1024 ** 2}
        app.after(800, app._confirm_realtime_start)
    if args.screenshot:
        app.after(4000, capture)
    app.after(max(args.seconds, 5 if args.screenshot else 0) * 1000, app.on_close)
    app.mainloop()
    print("Visible UI check closed cleanly:", args.case, args.language)
