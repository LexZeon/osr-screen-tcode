"""Saved dance/hybrid analysis preferences, independent of output presets."""
from copy import deepcopy
import math


POSE_OPTIONS = ("rtm_pose_flow_enabled", "rtm_pose_kalman_enabled",
                "rtm_pose_reject_enabled", "rtm_pose_micro_smooth_enabled")


def profile_key(mode):
    return "dance" if mode.startswith("RTM Pose") else "hybrid"


def defaults(key):
    return dict(fps=45, output_curve_fitting=True, rtm_pose_gpu_enabled=False,
                pose_auto_l0_enabled=key == "dance",
                pose_pattern_enabled=False,
                pose_fast_v1_enabled=key == "dance",
                compression_latency=0, rtm_hybrid_l0_enabled=False,
                rtm_hybrid_l0_weight=30, **{name: key == "dance" for name in POSE_OPTIONS})


def normalize(values, key):
    result = defaults(key)
    if not isinstance(values, dict):
        return result
    bounds = {"fps": (1, 120), "compression_latency": (-5, 5), "rtm_hybrid_l0_weight": (1, 100)}
    for name, default in result.items():
        value = values.get(name, default)
        if name in bounds:
            try:
                number = float(value)
                if math.isfinite(number):
                    low, high = bounds[name]
                    result[name] = max(low, min(high, round(number)))
            except (TypeError, ValueError, OverflowError):
                pass
        elif isinstance(value, (bool, int)):
            result[name] = bool(value)
    return result


def load_profiles(extra, mode, fps, legacy_values=None):
    saved = extra.get("analysis_profiles")
    if isinstance(saved, dict):
        return {key: normalize(saved.get(key), key) for key in ("hybrid", "dance")}
    profiles = {key: defaults(key) for key in ("hybrid", "dance")}
    # Keep explicit settings for the previously active mode. Missing fields use
    # the new mode defaults; the other mode gets its own independent defaults.
    old = dict(extra if legacy_values is None else legacy_values)
    old["fps"] = fps
    key = profile_key(mode)
    profiles[key] = normalize(old, key)
    return profiles


class AnalysisPreferences:
    def __init__(self, profiles, mode):
        self.profiles = deepcopy(profiles)
        self.active = profile_key(mode)

    def remember(self, variables):
        self.profiles[self.active] = {name: variable.get() for name, variable in variables.items()}

    def apply(self, variables):
        for name, variable in variables.items():
            variable.set(self.profiles[self.active][name])

    def switch(self, mode, variables):
        key = profile_key(mode)
        if key != self.active:
            self.remember(variables)
            self.active = key
            self.apply(variables)
