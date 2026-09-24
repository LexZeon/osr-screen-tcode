"""Local synthetic video/UI smoke check, without devices or user settings writes."""
import ctypes
from pathlib import Path
import tempfile
import time
import tkinter as tk

import cv2
import numpy as np
from PIL import ImageGrab

from preview import App, MODES


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass
    with tempfile.TemporaryDirectory(prefix="pose-preview-check-") as directory:
        path = Path(directory) / "sample.avi"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (640, 480))
        assert writer.isOpened()
        for i in range(180):
            rng = np.random.default_rng(10)
            frame = rng.integers(0, 180, (480, 640, 3), np.uint8)
            frame = np.roll(frame, i, axis=1)
            cv2.rectangle(frame, (200 + i, 100), (350 + i, 400), (120, 190, 210), -1)
            writer.write(frame)
        writer.release()
        root = tk.Tk()
        app = App(root)
        root.attributes("-topmost", True)
        model = app.model.get()
        for mode in MODES:
            app.mode.set(mode)
            app.mode_changed()
            app.model.set(model if mode == MODES[0] else "")
            app.last_pair = None
            app.start(str(path))
            deadline = time.perf_counter() + 30
            switched = False
            while app.worker is not None and time.perf_counter() < deadline:
                root.update()
                if not switched and app.last_pair is not None:
                    app.resolution.set("320")
                    app.resolution_changed()
                    switched = True
                time.sleep(0.01)
            app.stop_event.set()
            if app.worker is not None:
                app.worker.join(timeout=5)
            assert app.last_pair is not None, app.status.get()
            assert "Error /" not in app.status.get(), app.status.get()
            assert app.last_pair[0].shape[1] == 320
            if mode != MODES[0]:
                assert any(s.values is not None for s in app.history), app.status.get()
            print("Passed mode:", mode.split("/")[-1].strip())
        for size in ("1120x800", "700x680"):
            root.geometry(size)
            root.update()
            time.sleep(0.1)
            root.update()
            x, y = root.winfo_rootx(), root.winfo_rooty()
            output = Path(tempfile.gettempdir()) / f"pose-preview-{size}.png"
            ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(output)
            print(output)
        root.destroy()
        print("Three modes, live resolution, video playback, paired preview, EOF and two UI sizes passed")


if __name__ == "__main__":
    main()
