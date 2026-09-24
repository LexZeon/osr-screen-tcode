"""Opt-in, read-only numerical audit against the local v1.1.2 Git tag.

Run from a checkout containing that tag: python tests/compare_released_hybrid.py
No network, GUI, device, model, preference writes, or checkout modifications.
"""
import ast
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]

import cv2
import numpy as np
from motion_scenes import closeup_scene, deforming_frame
from osr_screen_tcode.analyzer import RealtimeAnalyzer
from osr_screen_tcode.camera_motion import CameraRelativeMotion
from osr_screen_tcode.config import AppConfig, HYBRID_MODE
from osr_screen_tcode import pose_backends


def released_class():
    source = subprocess.check_output(['git', 'show', 'v1.1.2:src/osr_screen_tcode/analyzer.py'], cwd=ROOT).decode('utf-8')
    # The audit never enables Pose. Isolate its removed import in a private
    # namespace instead of changing production pose_backends or the old source.
    package = types.ModuleType('_osr_hybrid_audit')
    package.__path__ = []
    backend = types.ModuleType(package.__name__+'.pose_backends')
    def unavailable(*args, **kwargs):
        raise RuntimeError('This audit must not load any Pose backend.')
    backend.OptionalRtmPose2dBackend = unavailable
    backend.OptionalRtmPose3dBackend = unavailable
    backend.RtmPose3dResult = pose_backends.RtmPose3dResult
    module = types.ModuleType(package.__name__+'.analyzer')
    for item in (package, backend, module):
        sys.modules[item.__name__] = item
    exec(compile(source, 'v1.1.2/analyzer.py', 'exec'), module.__dict__)
    return module.RealtimeAnalyzer


def main():
    # Reproducible algorithm comparison; this is not a realtime throughput claim.
    cv2.setNumThreads(1)
    released = released_class()
    cases = []
    for deformation in (0, 12, 24, 36):
        old = released(tracker_mode=HYBRID_MODE, output_mode='L0 Only')
        current = RealtimeAnalyzer(tracker_mode=HYBRID_MODE, output_mode='L0 Only')
        motion, scene = CameraRelativeMotion(), closeup_scene()
        differences, positions, states = [], [], Counter()
        for i in range(95):
            t = i/30
            frame = deforming_frame(scene, t, deformation=deformation,
                                    y=20*np.sin(t*5), camera_x=3*np.sin(t*3))
            first, second = old.process(frame), current.process(frame)
            differences.append(abs(first.positions['L0']-second.positions['L0']))
            positions.append(second.positions['L0'])
            observed, _ = motion.update(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), t)
            states[observed.state] += 1
        cases.append(dict(deformation=deformation, frames=95, v1_max_difference=max(differences),
                          v1_analysis_span=float(np.ptp(positions)), v2_states=dict(states)))
    old_config = ast.parse(subprocess.check_output(
        ['git', 'show', 'v1.1.2:src/osr_screen_tcode/config.py'], cwd=ROOT).decode('utf-8'))
    fields = ('smoothing', 'deadzone', 'motion_gain', 'visual_stroke_scale', 'output_interval_ms')
    old_defaults = {node.target.id: ast.literal_eval(node.value) for node in ast.walk(old_config)
                    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                    and node.target.id in fields}
    report = dict(ref='v1.1.2', commit=subprocess.check_output(['git', 'rev-parse', 'v1.1.2'], cwd=ROOT).decode().strip(),
                  opencv=cv2.__version__, same_parameters=True, cases=cases,
                  released_app_defaults=old_defaults,
                  current_app_defaults={key: getattr(AppConfig(), key) for key in fields},
                  scope='Analysis values only; defaults and final output processing are separate.')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(case['v1_max_difference'] < 1e-10 for case in cases) else 1


if __name__ == '__main__':
    raise SystemExit(main())
