"""Deterministic textured foreground/background clips; no local media files."""
import cv2
import numpy as np


class MotionScene:
    def __init__(self, seed=24, size=(240, 320)):
        self.h, self.w = size
        rng = np.random.default_rng(seed)
        self.background = rng.integers(20, 190, (self.h, self.w, 3), np.uint8)
        self.foreground = np.zeros_like(self.background)
        self.mask = np.zeros((self.h, self.w), np.uint8)
        x, y, w, h = int(.35*self.w), int(.32*self.h), int(.3*self.w), int(.36*self.h)
        self.foreground[y:y+h, x:x+w] = rng.integers(60, 255, (h, w, 3), np.uint8)
        self.mask[y:y+h, x:x+w] = 255

    def frame(self, *, x=0, y=0, scale=1, camera_x=0, camera_y=0, camera_scale=1, camera_roll=0, subject=True):
        image = self.background.copy()
        if subject:
            transform = cv2.getRotationMatrix2D((self.w/2, self.h/2), 0, scale)
            transform[:, 2] += (x, -y)
            obj = cv2.warpAffine(self.foreground, transform, (self.w, self.h))
            mask = cv2.warpAffine(self.mask, transform, (self.w, self.h)) > 250
            image[mask] = obj[mask]
        camera = cv2.getRotationMatrix2D((self.w/2, self.h/2), camera_roll, camera_scale)
        camera[:, 2] += (camera_x, -camera_y)
        return cv2.warpAffine(image, camera, (self.w, self.h), borderMode=cv2.BORDER_REFLECT)


def distant_target_frame(scene, timestamp, amplitude=.08):
    """Known off-center radial focus, independent from the moving ROI center."""
    target = np.array((scene.w*.890625, scene.h*55/240))
    scale = np.exp(amplitude*np.sin(timestamp*5))
    offset = (1-scale)*(target-(scene.w/2, scene.h/2))
    camera_x = 3*np.sin(timestamp*3)
    return scene.frame(scale=scale, x=offset[0], y=-offset[1], camera_x=camera_x), target+(camera_x, 0)


def difficult_scene(kind):
    scene = MotionScene()
    if kind == "blur":
        scene.background = cv2.GaussianBlur(scene.background, (25, 25), 5)
        scene.foreground = cv2.GaussianBlur(scene.foreground, (11, 11), 2)
    elif kind == "sparse":
        scene.background[:] = 90
        for x, y in ((45, 45), (260, 45), (45, 195), (260, 195)):
            cv2.rectangle(scene.background, (x, y), (x+6, y+6), (120, 120, 120), -1)
        scene.background = cv2.GaussianBlur(scene.background, (5, 5), 1)
    elif kind == "band":
        scene.background[:] = 90
        for x, y in ((25, 18), (80, 40), (230, 18), (290, 40)):
            cv2.rectangle(scene.background, (x, y), (x+8, y+8), (140, 140, 140), -1)
    return scene


def closeup_scene(kind="corner", seed=52):
    """Large textured subject with independent background in a small patch."""
    scene = MotionScene(seed=seed)
    rng = np.random.default_rng(seed+1)
    scene.background[:] = 85
    scene.foreground[:] = 0
    scene.mask[:] = 0
    if kind == "strip":
        scene.background[4:24, 5:315] = rng.integers(35, 145, (20, 310, 3), np.uint8)
    elif kind != "none":
        scene.background[6:30, 7:81] = rng.integers(35, 145, (24, 74, 3), np.uint8)
    scene.foreground[44:235, 12:315] = rng.integers(60, 235, (191, 303, 3), np.uint8)
    scene.mask[44:235, 12:315] = 255
    return scene


def window_scene():
    """Synthetic desktop window; small visible background, no private pixels."""
    scene = MotionScene(seed=91, size=(480, 640))
    scene.background[:] = 85
    scene.foreground[:] = 0
    scene.mask[:] = 0
    rng = np.random.default_rng(92)
    scene.background[8:42, 8:180] = rng.integers(20, 190, (34, 172, 3), np.uint8)
    scene.foreground[130:470, 18:628] = (238, 238, 238)
    scene.foreground[130:162, 18:628] = (120, 80, 40)
    cv2.putText(scene.foreground, "Motion test window", (32, 153), cv2.FONT_HERSHEY_SIMPLEX,
                .6, (255, 255, 255), 1, cv2.LINE_AA)
    for row in range(10):
        label = f"Row {row+1:02}: sample {rng.integers(100000, 999999)} / {rng.integers(100, 999)}"
        cv2.putText(scene.foreground, label, (34, 190+row*26), cv2.FONT_HERSHEY_SIMPLEX,
                    .65, (35, 35, 35), 1, cv2.LINE_AA)
        cv2.rectangle(scene.foreground, (440, 175+row*26),
                      (int(rng.integers(465, 605)), 189+row*26), (80, 140, 195), -1)
    scene.mask[130:470, 18:628] = 255
    return scene


def deforming_frame(scene, timestamp, deformation=12., **motion):
    """Large non-rigid foreground, with the independent background unchanged."""
    foreground, mask = scene.foreground, scene.mask
    y, x = np.mgrid[:scene.h, :scene.w].astype(np.float32)
    mx = (x+deformation*np.sin(4*np.pi*y/scene.h)*np.sin(timestamp*5)).astype(np.float32)
    my = (y+deformation*np.sin(4*np.pi*x/scene.w)*np.cos(timestamp*5)).astype(np.float32)
    try:
        scene.foreground = cv2.remap(foreground, mx, my, cv2.INTER_LINEAR)
        scene.mask = cv2.remap(mask, mx, my, cv2.INTER_NEAREST)
        return scene.frame(**motion)
    finally:
        scene.foreground, scene.mask = foreground, mask


class CompetingScene:
    """A large drifting distractor and a smaller reciprocal target."""
    def __init__(self):
        rng = np.random.default_rng(518)
        self.background = rng.integers(25, 160, (480, 640, 3), np.uint8)
        self.parts = []
        for x, y, w, h in ((32, 30, 240, 140), (435, 190, 120, 120)):
            part = np.zeros_like(self.background)
            mask = np.zeros((480, 640), np.uint8)
            part[y:y+h, x:x+w] = rng.integers(40, 250, (h, w, 3), np.uint8)
            mask[y:y+h, x:x+w] = 255
            self.parts.append((part, mask))

    def frame(self, stamp, target=True):
        image = self.background.copy()
        for i, (part, mask) in enumerate(self.parts):
            delta = (0, stamp*45) if i == 0 else (0, -28*np.sin(stamp*5) if target else 0)
            transform = np.float32([[1, 0, delta[0]], [0, 1, delta[1]]])
            moved = cv2.warpAffine(part, transform, (640, 480))
            selected = cv2.warpAffine(mask, transform, (640, 480)) > 250
            image[selected] = moved[selected]
        camera = np.float32([[1, 0, 3*np.sin(stamp*3)], [0, 1, 0]])
        return cv2.warpAffine(image, camera, (640, 480), borderMode=cv2.BORDER_REFLECT)


class ReachScene:
    """A blue mover approaches a different orange textured object."""
    def __init__(self, target=True):
        rng = np.random.default_rng(2121)
        texture = rng.integers(45, 100, (360, 640, 1), np.uint8)
        self.background = np.repeat(texture, 3, axis=2)
        self.target = target
        self.object = np.clip(np.array((35, 130, 225))+rng.integers(-32, 33, (118, 100, 3)), 0, 255).astype(np.uint8)
        self.source = np.clip(np.array((215, 90, 35))+rng.integers(-35, 36, (100, 72, 3)), 0, 255).astype(np.uint8)

    def frame(self, stamp, *, camera_x=0., show_source=True):
        image = self.background.copy()
        if self.target:
            image[122:240, 485:585] = self.object
        x = 305+180*np.sin(stamp*2*np.pi/2.5)
        if show_source:
            left = round(x-36)
            image[132:232, left:left+72] = self.source
        camera = np.float32([[1, 0, camera_x], [0, 1, 0]])
        return cv2.warpAffine(image, camera, (640, 360), borderMode=cv2.BORDER_REFLECT), (x+camera_x, 182.), (485.+camera_x, 182.)
