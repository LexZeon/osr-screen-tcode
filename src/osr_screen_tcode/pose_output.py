"""RTM output gains. Image observations and pose points are never modified."""
import math


def rtm_l0_amplitude(positions: dict[str, float]) -> dict[str, float]:
    """Dance L0 base output ×10 about center, before user travel/limits."""
    result = dict(positions)
    value = float(positions.get("L0", .5))
    if "L0" in positions and math.isfinite(value):
        result["L0"] = max(0.0, min(1.0, .5 + (value-.5)*10))
    return result


def l0_translation_gain(l0: float, endpoint_gain: float = 1.0, middle_gain: float = 2.5,
                        peak_position: float = 0.5, lower_knot: tuple | None = None) -> float:
    """Piecewise linear gain, applied only to output; peak within the range."""
    if not math.isfinite(l0):
        return 1.0
    level = max(0.0, min(1.0, l0))
    peak = max(.01, min(.99, peak_position))
    if lower_knot is not None and level <= peak:
        position, gain = lower_knot
        if level <= position:
            return endpoint_gain+(gain-endpoint_gain)*level/position
        return gain+(middle_gain-gain)*(level-position)/(peak-position)
    weight = level/peak if level <= peak else (1.0-level)/(1.0-peak)
    return endpoint_gain + (middle_gain - endpoint_gain) * weight


def rtm_rotation_amplitudes(positions: dict[str, float]) -> dict[str, float]:
    result = dict(positions)
    for axis, gain in (("R0", 3.0), ("R1", 1.5), ("R2", 1.5)):
        if axis in positions and math.isfinite(float(positions[axis])):
            result[axis] = max(0.0, min(1.0, 0.5 + (float(positions[axis]) - 0.5) * gain))
    return result


def l0_rotation_gain(l0: float) -> float:
    """Pose R1/R2: 1× through two-thirds L0, then linearly 0.5× at the top."""
    if not math.isfinite(l0):
        return 1.
    level = max(0., min(1., l0))
    return 1.-.5*max(0., 3*level-2)


def rtm_motion_amplitudes(positions: dict[str, float]) -> dict[str, float]:
    result = dict(positions)
    l0 = float(positions.get("L0", 0.5))
    if not math.isfinite(l0):
        return result
    translation_gain = l0_translation_gain(l0, endpoint_gain=0.5, middle_gain=3.5,
                                           peak_position=2/3, lower_knot=(1/3, 1.0))
    rotation_gain = 1.5*l0_rotation_gain(l0)
    for axis, gain in (("L1", translation_gain), ("L2", translation_gain), ("R0", 3.0), ("R1", rotation_gain), ("R2", rotation_gain)):
        if axis not in positions:
            continue
        value = float(positions[axis])
        if math.isfinite(value):
            result[axis] = max(0.0, min(1.0, 0.5 + (value - 0.5) * gain))
    return result
