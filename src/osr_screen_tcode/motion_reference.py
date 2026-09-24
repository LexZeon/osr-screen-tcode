"""Hybrid measurements and separately labelled display-only subject estimates."""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class MotionReference:
    method: str
    state: str = "calibrating"
    roi: tuple | None = None
    vectors: tuple = ()
    background: tuple = ()
    step: tuple = (0.0, 0.0, 0.0)  # x, up, image scale; image percentage points
    camera_step: tuple = (0.0, 0.0, 0.0)
    weights: tuple = (1.0, 0.0, 0.0)  # up, scale, x
    span: float | None = None
    gain: float = 1.0
    l0: float = 0.5
    reason: str = ""
    counts: tuple = (0, 0, 0, 0)  # detected, tracked, camera, local
    pattern: str = ""
    period: float = 0.
    camera_model: str = ""
    background_diagnostic: tuple = ()  # rejection, candidate size, motion groups
    rescued: int = 0  # current-pair tracks recovered by unique patch matching
    basis: tuple = ()  # L0/L1/L2 unit vectors, each in right/up/image-scale space
    basis_state: str = ''
    basis_confidence: float = 0.
    local_model: str = ""  # rigid region, local patch, or deforming subject box
    motion_dt: float = 0.  # elapsed source time for this measured step
    focus: str = ''  # reciprocal / previously reciprocal / current amplitude
    stroke_center: tuple | None = None
    interaction_point: tuple | None = None
    interaction_state: str = ''
    l0_reference: str = ''
    point_step: float = 0.
    support_groups: tuple = ()
    target_point: tuple | None = None
    target_kind: str = ''
    fusion_weights: tuple = ()
    direction_confirmed: bool = False
    continuation: str = ''
    continuation_elapsed: float = 0.
    reach_state: str = ''
    reach_progress: float | None = None
    reach_active: bool = False
    target_box: tuple | None = None
    target_samples: tuple = ()
    target_offscreen: bool = False
    subject_origin: tuple | None = None
    subject_box: tuple | None = None
    # Display-only subject estimates. Never substitute these for actual ROI,
    # sampled vectors, measured steps or the observation history.
    estimate_state: str = ''  # weak / predicted / held
    estimate_origin: tuple | None = None
    estimate_box: tuple | None = None
    estimate_elapsed: float = 0.
    estimate_basis: tuple = ()
    continuation_kind: str = ''  # rhythm / velocity / weak; output provenance


AXIS_COLORS = ((235, 220, 75), (255, 166, 214), (106, 200, 255))  # BGR


def target_marker(kind):
    if kind.startswith('assumed'):
        return 'V?'
    if kind in ('tracked', 'tracked_held', 'tracked_confirming'):
        return 'T?'
    if kind in ('endpoint', 'unoriented'):
        return 'E?'
    if kind in ('expansion', 'expansion_held'):
        return 'S?'
    return 'P?'


def projected_axes(basis):
    """Oblique drawing of image-proxy coordinates; not a camera calibration."""
    directions = np.asarray(basis, dtype=float)
    if directions.shape != (3, 3) or not np.isfinite(directions).all():
        return None
    return directions @ np.array(((1., 0.), (0., -1.), (-.6, .4)))


def draw_motion_axes(image, reference):
    projected = projected_axes(reference.basis)
    if projected is None or reference.roi is None:
        return
    h, w = image.shape[:2]
    x1, y1, x2, y2 = reference.roi
    center = np.asarray(reference.subject_origin or ((x1+x2)/2, (y1+y2)/2))
    if not ((0 <= center).all() and (center < (w, h)).all()):
        return  # an offscreen subject origin is not located on the screen edge
    length = max(12., min(w, h)*.19)
    origin = tuple(np.round(center).astype(int))
    for i, (direction, color) in enumerate(zip(projected, AXIS_COLORS)):
        end = tuple(np.round(np.clip(center+direction*length, (2, 2), (w-3, h-3))).astype(int))
        back = tuple(np.round(np.clip(center-direction*length*.65, (2, 2), (w-3, h-3))).astype(int))
        cv2.line(image, origin, back, color, 1, cv2.LINE_AA)
        cv2.arrowedLine(image, origin, end, (10, 10, 10), 5, cv2.LINE_AA, tipLength=.15)
        cv2.arrowedLine(image, origin, end, color, 2, cv2.LINE_AA, tipLength=.15)
        label = f'L{i}/R{i}+'
        anchor = (max(2, min(w-91, end[0]+4)), max(16, min(h-5, end[1]-4)))
        cv2.putText(image, label, anchor, cv2.FONT_HERSHEY_SIMPLEX, .48, (10, 10, 10), 3, cv2.LINE_AA)
        cv2.putText(image, label, anchor, cv2.FONT_HERSHEY_SIMPLEX, .48, color, 1, cv2.LINE_AA)
    cv2.circle(image, origin, 4, (250, 250, 250), -1, cv2.LINE_AA)


def sample_vectors(a, b, count=60):
    if not len(a):
        return ()
    stride = max(1, (len(a) + count - 1) // count)
    return tuple((tuple(map(float, p)), tuple(map(float, q))) for p, q in zip(a[::stride], b[::stride]))


def _dashed_line(image, first, last, color):
    """Clip before stepping so an offscreen estimate cannot create long loops."""
    height, width = image.shape[:2]
    points = np.asarray((first, last), dtype=float)
    if points.shape != (2, 2) or not np.isfinite(points).all():
        return
    points = np.rint(np.clip(points, -(2**29), 2**29)).astype(int)
    visible, first, last = cv2.clipLine((0, 0, width, height), tuple(points[0]), tuple(points[1]))
    if not visible:
        return
    first, last = np.asarray(first, dtype=float), np.asarray(last, dtype=float)
    length = float(np.linalg.norm(last-first))
    if length < 1:
        return
    direction = (last-first)/length
    for distance in np.arange(0., length, 14.):
        start = tuple(np.rint(first+direction*distance).astype(int))
        end = tuple(np.rint(first+direction*min(length, distance+5.)).astype(int))
        cv2.line(image, start, end, (10, 10, 10), 4, cv2.LINE_AA)
        cv2.line(image, start, end, color, 2, cv2.LINE_AA)


def draw_subject_estimate(image, reference):
    """Show uncertain subject geometry distinctly, without altering evidence."""
    color = (255, 240, 205)  # bright blue-white; actual subject stays yellow
    if reference.estimate_box is not None:
        box = np.asarray(reference.estimate_box, dtype=float)
        if box.shape == (4,) and np.isfinite(box).all():
            left, top, right, bottom = box
            if right > left and bottom > top:
                corners = ((left, top), (right, top), (right, bottom), (left, bottom))
                for index in range(4):
                    _dashed_line(image, corners[index], corners[(index+1) % 4], color)
    if reference.estimate_origin is None:
        return
    height, width = image.shape[:2]
    origin = np.asarray(reference.estimate_origin, dtype=float)
    if (origin.shape != (2,) or not np.isfinite(origin).all()
            or not ((0 <= origin).all() and (origin < (width, height)).all())):
        return  # never move an offscreen origin onto the screen edge
    try:
        projected = projected_axes(reference.estimate_basis)
    except (ValueError, TypeError):
        projected = None
    if projected is not None:
        length = max(12., min(width, height)*.19)
        for index, direction in enumerate(projected):
            direction_length = float(np.linalg.norm(direction))
            if direction_length < 1e-6:
                continue
            # A malformed non-unit basis cannot produce unbounded geometry.
            direction = direction/max(1., direction_length)
            end = origin+direction*length
            _dashed_line(image, origin-direction*length*.65, end, color)
            if 0 <= end[0] < width and 0 <= end[1] < height:
                anchor = tuple(np.rint(end+(3, -3)).astype(int))
                cv2.putText(image, f'L{index}?', anchor,
                            cv2.FONT_HERSHEY_SIMPLEX, .48, (10, 10, 10), 3, cv2.LINE_AA)
                cv2.putText(image, f'L{index}?', anchor,
                            cv2.FONT_HERSHEY_SIMPLEX, .48, color, 1, cv2.LINE_AA)
    point = tuple(np.rint(origin).astype(int))
    cv2.circle(image, point, 5, (10, 10, 10), 4, cv2.LINE_AA)
    cv2.circle(image, point, 5, color, 2, cv2.LINE_AA)
    anchor = (max(0, min(width-1, point[0]+8)), max(0, min(height-1, point[1]-8)))
    cv2.putText(image, 'A?', anchor, cv2.FONT_HERSHEY_SIMPLEX, .6, (10, 10, 10), 3, cv2.LINE_AA)
    cv2.putText(image, 'A?', anchor, cv2.FONT_HERSHEY_SIMPLEX, .6, color, 1, cv2.LINE_AA)


def draw_reference(frame, reference):
    image = frame.copy()
    for a, b in reference.background:
        cv2.circle(image, tuple(round(v) for v in b), 3, (255, 145, 55), 1, cv2.LINE_AA)
    for a, b in reference.vectors:
        p, q = tuple(round(v) for v in a), tuple(round(v) for v in b)
        cv2.arrowedLine(image, p, q, (80, 245, 100), 1, cv2.LINE_AA, tipLength=.3)
        cv2.circle(image, q, 2, (80, 245, 100), -1, cv2.LINE_AA)
    estimated = bool(reference.estimate_state)
    visible_box = None if estimated else reference.subject_box or reference.roi
    if visible_box:
        x1, y1, x2, y2 = (round(v) for v in visible_box)
        cv2.rectangle(image, (x1, y1), (x2, y2), (30, 215, 255), 2, cv2.LINE_AA)
        if reference.subject_origin is None:
            cv2.drawMarker(image, ((x1+x2)//2, (y1+y2)//2), (30, 215, 255), cv2.MARKER_CROSS, 16, 2)
    if estimated:
        draw_subject_estimate(image, reference)
    else:
        draw_motion_axes(image, reference)
    h, w = image.shape[:2]
    if (not estimated and reference.subject_origin is not None and
            0 <= reference.subject_origin[0] < w and 0 <= reference.subject_origin[1] < h):
        origin = np.round(reference.subject_origin).astype(int)
        cv2.circle(image, tuple(origin), 6, (230, 255, 230), 1, cv2.LINE_AA)
        cv2.putText(image, 'A', tuple(np.clip(origin+(-17, -12), (2, 18), (w-20, h-4))),
                    cv2.FONT_HERSHEY_SIMPLEX, .6, (230, 255, 230), 2, cv2.LINE_AA)
    for _, point in reference.support_groups:
        p = tuple(round(v) for v in point)
        cv2.circle(image, p, 5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.circle(image, p, 4, (120, 255, 120), 1, cv2.LINE_AA)
    for point, label, color in ((reference.stroke_center, 'C', (220, 220, 220)),
                                (reference.interaction_point, 'P?', (160, 160, 160))):
        if point is None or not (0 <= point[0] < w and 0 <= point[1] < h):
            continue
        if (label == 'P?' and reference.target_point is not None
                and np.linalg.norm(np.asarray(point)-reference.target_point) < 6):
            continue  # one point, one label; T?/S? already describes this fit
        p = tuple(round(v) for v in point)
        cv2.drawMarker(image, p, (0, 0, 0), cv2.MARKER_CROSS, 19, 4)
        cv2.drawMarker(image, p, color, cv2.MARKER_CROSS, 17, 2)
        cv2.circle(image, p, 9, color, 1, cv2.LINE_AA)
        cv2.putText(image, label, (min(w-35, p[0]+12), max(17, p[1]-10)),
                    cv2.FONT_HERSHEY_SIMPLEX, .5, color, 2, cv2.LINE_AA)
    if reference.target_point is not None:
        point = np.asarray(reference.target_point)
        if np.isfinite(point).all() and ((0, 0) <= point).all() and (point < (w, h)).all():
            p = tuple(np.round(point).astype(int))
            color = (50, 155, 255) if reference.target_kind.startswith('tracked') else (100, 215, 245) if reference.target_kind.startswith('assumed') else (160, 160, 160)
            cv2.circle(image, p, 13, (0, 0, 0), 5, cv2.LINE_AA)
            cv2.circle(image, p, 13, color, 2, cv2.LINE_AA)
            cv2.putText(image, target_marker(reference.target_kind), (max(0, min(w-35, p[0]+15)), max(18, p[1]-12)),
                        cv2.FONT_HERSHEY_SIMPLEX, .6, color, 2, cv2.LINE_AA)
            if reference.roi and not estimated:
                x1, y1, x2, y2 = reference.roi
                origin = tuple(round(v) for v in (reference.subject_origin or ((x1+x2)/2, (y1+y2)/2)))
                cv2.arrowedLine(image, origin, p, color, 1, cv2.LINE_AA, tipLength=.12)
        elif not estimated and reference.target_offscreen and reference.roi is not None and np.isfinite(point).all():
            x1, y1, x2, y2 = reference.roi
            origin = np.array(reference.subject_origin or ((x1+x2)/2, (y1+y2)/2))
            delta = point-origin
            fractions = [1.]
            for i, limit in enumerate((w-12, h-12)):
                if delta[i] > 0:
                    fractions.append((limit-origin[i])/delta[i])
                elif delta[i] < 0:
                    fractions.append((12-origin[i])/delta[i])
            end = np.clip(origin+max(0., min(fractions))*delta, (12, 12), (w-12, h-12))
            cv2.arrowedLine(image, tuple(np.round(origin).astype(int)), tuple(np.round(end).astype(int)),
                            (50, 155, 255), 2, cv2.LINE_AA, tipLength=.12)
            cv2.putText(image, target_marker(reference.target_kind)+' >', tuple(np.round(np.clip(end+(5, -10), (2, 18), (w-52, h-3))).astype(int)),
                        cv2.FONT_HERSHEY_SIMPLEX, .5, (50, 155, 255), 2, cv2.LINE_AA)
    if reference.target_kind.startswith('tracked'):
        for point in reference.target_samples:
            if 0 <= point[0] < w and 0 <= point[1] < h:
                cv2.circle(image, tuple(round(v) for v in point), 3, (20, 115, 255), 1, cv2.LINE_AA)
        if reference.target_box is not None:
            x1, y1, x2, y2 = reference.target_box
            if x1 < w and y1 < h and x2 >= 0 and y2 >= 0:
                cv2.rectangle(image, (int(max(0, x1)), int(max(0, y1))),
                              (int(min(w-1, x2)), int(min(h-1, y2))), (20, 115, 255), 1, cv2.LINE_AA)
    return image


def reference_lines(reference, translate, *, compact=False):
    t = translate
    states = {
        "calibrating": t("建立参考", "Calibrating"),
        "ready": t("采用区域相对运动", "Using regional relative motion"),
        "tracking": t("跟踪参考区域", "Tracking reference region"),
        "holding": t("短暂丢点；保持参考", "Brief tracking loss; reference held"),
        "camera_only": t("未分离出局部运动；保持", "No separate local motion; hold"),
        "missing": t("参考不足；保持", "Insufficient reference; hold"),
    }
    if reference.method == "v1":
        states["ready"] = t("采用区域光流", "Using ROI optical flow")
    lines = [f'{reference.method} · {states.get(reference.state, reference.state)}',
             t("黄框：实际区域  绿点/箭头：实际采样", "Yellow: actual region  Green: actual samples")]
    brief = [lines[0]]
    estimate_labels = {
        'weak': t('主体弱跟踪（估计）', 'Weak subject tracking (estimated)'),
        'predicted': t('主体位置估算', 'Estimated subject position'),
        'held': t('主体估计保持', 'Subject estimate held'),
    }
    def elapsed_text(value, limit=2.):
        elapsed = float(np.clip(value if np.isfinite(value) else 0., 0., limit))
        return f'{elapsed:.1f}/{limit:.1f} '+t('秒', 's')
    if reference.estimate_state:
        lines[0] = 'v2 · '+estimate_labels.get(reference.estimate_state, t('主体估计', 'Subject estimate'))
        lines[0] += ' · '+elapsed_text(reference.estimate_elapsed)
    if reference.continuation:
        kind = {'rhythm': t('节奏接续（预测）', 'Rhythm continuation (predicted)'),
                'velocity': t('短速度接续（估算）', 'Brief velocity continuation (estimated)'),
                'weak': t('弱跟踪接续（估算）', 'Weak-tracking continuation (estimated)')}
        status = {'continuing': '', 'braking': t(' · 减速中', ' · braking'),
                  'held': t(' · 已停止延续，保持', ' · continuation stopped; held')}
        velocity = reference.continuation_kind == 'velocity'
        if velocity:
            status['held'] = t(' · 速度接续已停止，保持', ' · velocity continuation stopped; held')
        lines[0] = 'v2 · '+kind.get(reference.continuation_kind or 'rhythm', t('估算接续', 'Estimated continuation'))
        lines[0] += status.get(reference.continuation, '')+' · '+elapsed_text(reference.continuation_elapsed, .3 if velocity else 2.)
        if velocity:
            lines[0] += t('（最多）', ' (maximum)')
    if reference.pattern:
        names = {"stopped": t("不动", "Hold"), "quarter": t("1/4 行程", "Quarter travel"), "half": t("半行程", "Half travel"), "full": t("全行程", "Full travel")}
        span_text = "--" if reference.span is None else f"{reference.span:.1f}%"
        lines.insert(1, t(f"{names[reference.pattern]} · 周期 {reference.period:.2f} 秒 · 跨度 {span_text}",
                          f"{names[reference.pattern]} · {reference.period:.2f} s · span {span_text}"))
        brief.append(lines[1])
    if reference.method == "v2":
        if not reference.estimate_state and reference.local_model == "patch":
            lines[0] += t(" · 稳定局部", " · stable local patch")
        elif not reference.estimate_state and reference.local_model == "box":
            lines[0] += t(" · 主体框中心", " · subject-box center")
        if reference.focus:
            focus = {'reciprocal': t('当前往复', 'Current reciprocal motion'),
                     'previous': t('曾往复且仍在跟踪', 'Previously reciprocal, still tracked'),
                     'amplitude': t('当前运动幅度', 'Current motion amplitude')}
            lines.append(t('区域选择：', 'Region priority: ')+focus[reference.focus])
            if reference.subject_origin is None:
                brief.append(lines[-1])
        reasons = {
            "features": t("画面纹理不足", "Too few image features"),
            "tracking": t("特征跟踪失败", "Feature tracking failed"),
            "background": t("背景参考分布不足", "Background reference lacks spatial support"),
            "background_confirm": t("正在确认小块背景", "Confirming a small background patch"),
            "region": t("等待局部运动", "Waiting for local motion"),
            "region_fit": t("局部运动不稳定", "Inconsistent local motion"),
            "jump": t("切镜头或运动突变", "Cut or abrupt motion"),
            "fast_support": t("快速运动有效特征不足；保持", "Fast motion lacks reliable tracks; hold"),
            "stationary": t("区域仍在跟踪；当前变化很小", "Region tracked; little current motion"),
            "repeated": t("画面尚未更新；保持参考", "Frame unchanged; reference held"),
            "subject_recovered": t("主体从可靠画面重新匹配", "Subject re-matched from a verified frame"),
        }
        has_candidate_reason = reference.reason in ("background", "background_confirm") and reference.background_diagnostic
        if reference.reason and not has_candidate_reason:
            lines.append(reasons.get(reference.reason, reference.reason))
            brief.append(lines[-1])
        if has_candidate_reason:
            cause, candidates, groups = reference.background_diagnostic
            causes = {
                "texture": t("小块背景纹理不足", "Small background patch lacks texture"),
                "groups": t("无法分出一致运动", "No coherent motion group"),
                "extent": t("候选点过于集中", "Candidate points too concentrated"),
                "periphery": t("候选不在外围", "No peripheral candidate"),
                "separation": t("前景与背景运动未分开", "Foreground/camera not separated"),
                "foreground_extent": t("局部区域覆盖不足", "Local region too small"),
                "foreground_fit": t("局部运动群不稳定", "Unstable local motion groups"),
                "ownership": t("前景背景归属不明确", "Ambiguous foreground/camera"),
                "uncertainty": t("背景外推误差过大", "Camera extrapolation uncertain"),
                "confirm": t("等待连续确认", "Awaiting confirmation"),
                "accepted": t("背景跟踪中断", "Background tracking interrupted"),
            }
            lines.append(t(f"候选 {candidates} / 运动群 {groups}：{causes.get(cause, cause)}",
                           f"Candidate {candidates} / groups {groups}: {causes.get(cause, cause)}"))
            brief.append(lines[-1])
        detected, tracked, camera, local = reference.counts
        lines.append(t(f"特征 {detected} / 跟踪 {tracked} / 背景 {camera} / 局部 {local}",
                       f"Features {detected} / tracked {tracked} / camera {camera} / local {local}"))
        if reference.rescued:
            lines[0] += t(f" · 补匹配 {reference.rescued}", f" · recovered {reference.rescued}")
        # One legend leaves enough room for diagnostics even in a short pane.
        lines[2 if reference.pattern else 1] = t("黄框：主体运动框  绿：扣除运镜  蓝：背景",
                                                               "Yellow: subject box / green: local / blue: camera")
        if reference.estimate_state:
            lines[2 if reference.pattern else 1] = t('淡色虚框／A?：主体估计，不是可靠观测',
                'Pale dashed box / A?: subject estimate, not a reliable observation')
        x, y, s = reference.camera_step
        source = t("分层背景", "Layered camera") if reference.camera_model == "minority" else t("背景", "Camera")
        lines.append(t(f"{source} Δ 左右 {x:+.2f} 上下 {y:+.2f} 尺度 {s:+.2f}%",
                       f"{source} Δ X {x:+.2f} Y {y:+.2f} scale {s:+.2f}%"))
    x, y, s = reference.step
    lines.append(t(f"采用 Δ 左右 {x:+.2f} 上下 {y:+.2f} 尺度 {s:+.2f}%",
                   f"Used Δ X {x:+.2f} Y {y:+.2f} scale {s:+.2f}%"))
    if reference.method == "v2":
        if reference.estimate_state:
            if reference.estimate_basis:
                lines.append(t('虚线三轴：保留方向参考，未作为新观测',
                               'Dashed axes: retained orientation, not new observations'))
        elif reference.basis:
            x, y, s = reference.basis[0]
            state = {'learning': t('确认中', 'learning'), 'tracking': t('跟随', 'tracking'), 'holding': t('保持', 'held')}.get(reference.basis_state, '')
            lines.append(t(f"3D 主轴 {state}：X {x:+.2f} Y {y:+.2f} S {s:+.2f}",
                           f"3D axis {state}: X {x:+.2f} Y {y:+.2f} S {s:+.2f}"))
        else:
            y, s, x = (round(w*100) for w in reference.weights)
            lines.append(t(f"L0 权重：上下 {y} / 尺度 {s} / 左右 {x}%",
                           f"L0 weights: Y {y} / scale {s} / X {x}%"))
        span = "--" if reference.span is None else f"{reference.span:.2f}%"
        if not reference.pattern and reference.state not in ("missing", "calibrating", "holding", "tracking"):
            lines.append(t(f"往复参考跨度 {span} · 识别校准 ×{reference.gain:.1f}",
                           f"Stroke reference span {span} · calibration ×{reference.gain:.1f}"))
    summary_start = len(lines)
    lines.append(t(f"分析 L0 {reference.l0*100:.1f}%（输出倍率前）",
                   f"Analysis L0 {reference.l0*100:.1f}% (before output gains)"))
    if reference.estimate_state:
        lines.append('A? · '+estimate_labels.get(reference.estimate_state, t('主体估计', 'Subject estimate'))+
                     ' · '+elapsed_text(reference.estimate_elapsed))
        lines.append(t('估计不写入观测图或 RTM 骨架旋转',
                       'Estimates do not enter observation charts or RTM pose rotations'))
    elif reference.subject_origin is not None:
        lines.append(t('A 主体框中心：多组采样跟踪' if reference.local_model == 'box' else 'A 主体：保持同一跟踪点',
                       'A subject-box center: distributed tracking' if reference.local_model == 'box' else 'A subject: persistent tracked anchor')
                     if reference.state in ('ready', 'tracking') else
                     t('A 主体：暂缺测，参考位置保持', 'A subject: measurement lost; reference held'))
    if reference.stroke_center is not None and not compact:
        lines.append(t('C：往复中心（画面估计）', 'C: stroke center (image estimate)'))
    if reference.interaction_point is not None and (not compact or reference.l0_reference == 'interaction'):
        if reference.target_kind not in ('interaction', 'interaction_held', 'expansion', 'expansion_held'):
            lines.append(t('P?：光流会聚候选，未确认接触', 'P?: flow convergence candidate, contact unconfirmed'))
    elif reference.interaction_state and not compact:
        point_states = {'confirming': t('交互点：确认中', 'Interaction point: confirming'),
                        'holding': t('交互点：短暂缺失；保持', 'Interaction point: held (brief loss)'),
                        'unresolved': t('交互点：不可辨', 'Interaction point: unresolved')}
        lines.append(point_states.get(reference.interaction_state, point_states['unresolved']))
    if reference.l0_reference:
        sources = {'motion': t('三维运动轴', '3D motion axis'), 'center': t('往复中心', 'Stroke center'),
                    'interaction': t('交互点候选', 'Interaction candidate'),
                    'fusion': t('融合参考', 'Fused reference')}
        source = sources[reference.l0_reference]
        if compact:
            lines[summary_start] = t(f'L0 {reference.l0*100:.1f}% · {source}（倍率前）',
                                     f'L0 {reference.l0*100:.1f}% · {source} (before gains)')
        else:
            lines.append(t('L0 来源：', 'L0 reference: ')+source)
    if reference.estimate_state and reference.target_kind.startswith('assumed'):
        lines.append(t('V?：假定客体参考暂存；主体估计中，不更新到达比例、不连线',
                       'V?: assumed-object reference retained; subject estimated, reach not updated, no connector'))
    elif reference.target_point is not None:
        target = {'assumed': t('V? 假定客体：由主体往复推定，非实测', 'V? Assumed object from subject strokes; not observed'),
                  'assumed_held': t('V? 假定客体：暂缺测，保持参考', 'V? Assumed object: measurement lost; reference held'),
                  'tracked': t('T? 客体候选：独立跟踪，接触未确认', 'T? Object candidate: independently tracked, contact unconfirmed'),
                  'tracked_confirming': t('T? 独立目标候选：持续确认中', 'T? Independent target candidate: confirming'),
                  'tracked_held': t('T? 客体参考暂不完整；位置待确认', 'T? Object reference incomplete; position unconfirmed'),
                  'interaction': t('P? 区域外会聚参考；独立目标未定位', 'P? External convergence; independent target unresolved'),
                  'interaction_held': t('P? 会聚参考短暂保持；目标未定位', 'P? Convergence held; target unresolved'),
                  'expansion': t('S? 局部缩放中心；交互目标未定位', 'S? Local expansion center; interaction target unresolved'),
                  'expansion_held': t('S? 缩放中心短暂保持；目标未定位', 'S? Expansion center held; target unresolved'),
                  'endpoint': t('E? 往复近端估计；交互目标未定位', 'E? Estimated near stroke end; interaction target unresolved'),
                  'unoriented': t('E? 轨迹端点；目标与远近待确认', 'E? Trajectory end; target and near/far unconfirmed')}
        lines.append(target.get(reference.target_kind, t('目标未定位', 'Target unresolved')))
    if reference.reach_progress is not None:
        progress = reference.reach_progress*100
        lines.append(t(f'估计到达 {progress:.1f}% · 100% 对应 L0 底部（倍率前）',
                       f'Estimated reach {progress:.1f}% · 100% = L0 bottom (before gains)')
                     if reference.reach_active else
                     t(f'候选到达 {progress:.1f}% · 确认期间跟随主体',
                       f'Candidate reach {progress:.1f}% · following subject while confirming'))
    elif reference.reach_state:
        if reference.state not in ('ready', 'tracking'):
            lines.append(t('主体暂缺测；不更新到达比例', 'Subject measurement lost; reach is not updated'))
        else:
            lines.append(t('目标到达比例未确认；按可见物体往复', 'Target reach unresolved; visible-motion proxy')
                         if not reference.reach_active else t('目标丢失：只延续已确认规律，最多 2 秒', 'Target lost: learned rhythm only, up to 2 s'))
    if reference.target_offscreen:
        lines.append(t('目标在画外；主体估计中，暂不连线', 'Target offscreen; subject estimated, connector hidden')
                     if reference.estimate_state else
                     t('假定客体在画外；箭头仅指向', 'Assumed object offscreen; direction arrow only')
                     if reference.target_kind.startswith('assumed') else
                     t('目标在画外；边缘箭头仅指向，不是目标位置', 'Target offscreen; edge arrow is a direction, not its position'))
    if reference.fusion_weights:
        m, c, p = (round(v*100) for v in reference.fusion_weights)
        if not compact and reference.reach_active and reference.reach_progress is not None:
            lines.append(t('L0 按三轴原点到目标的距离比例接续', 'L0 follows axis-origin to target distance ratio'))
        elif not compact:
            lines.append(t(f'融合贡献：主轴 {m}% / 中心 {c}% / 交互 {p}%',
                           f'Contributions: axis {m}% / center {c}% / interaction {p}%'))
        lines.append(t('远离→L0 大，靠近→L0 小', 'Away: larger L0 / toward: smaller L0')
                     if reference.direction_confirmed else t('目标远近待确认；保留稳定方向', 'Near/far unconfirmed; stable polarity retained'))
    if reference.support_groups:
        lines.append(t(f'多点采样：{len(reference.support_groups)} 组有效', f'Multi-point support: {len(reference.support_groups)} groups'))
    brief[0] = lines[0]
    brief.extend(lines[summary_start:])
    return brief if compact else lines
