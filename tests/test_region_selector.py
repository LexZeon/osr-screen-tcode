"""Picker image/resource and compact-layout tests, without native UI or capture."""
from contextlib import ExitStack
import math
import unittest
from unittest.mock import MagicMock, Mock, patch

import numpy as np
from PIL import Image

from osr_screen_tcode import region_selector as selector
from osr_screen_tcode.capture import ScreenRegion


class CanvasDouble:
    """Enough text geometry to exercise wrapping without starting Tk."""
    def __init__(self, width=320, height=240):
        self.width, self.height, self.items = width, height, {}
        self.next_id = 0
        self.windows = []

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def create_text(self, x, y, **options):
        size = options.get('font', ('', 10))[1]
        text_width = max(1, len(options['text'])*size*.65)
        width = min(text_width, options.get('width', text_width))
        height = math.ceil(text_width/max(1, width))*size*1.4
        self.next_id += 1
        self.items[self.next_id] = [x, y, x+width, y+height]
        return self.next_id

    def bbox(self, item):
        return self.items.get(item)

    def delete(self, item):
        self.items.pop(item, None)

    def move(self, item, x, y):
        box = self.items[item]
        self.items[item] = [box[0]+x, box[1]+y, box[2]+x, box[3]+y]

    def tag_lower(self, *arguments):
        pass

    def create_window(self, x, y, **options):
        self.windows.append((x, y, options))
        return 1


class WidgetDouble:
    def __init__(self, parent=None, **options):
        self.parent, self.options, self.pack_options = parent, options, None

    def pack(self, **options):
        self.pack_options = options

    def update_idletasks(self):
        pass

    def winfo_reqwidth(self):
        # Force naturally oversized content, which the picker must constrain.
        return 450 if 'command' in self.options else 700

    def winfo_reqheight(self):
        return 40 if 'command' in self.options else 450


class RegionSelectorTests(unittest.TestCase):
    def picker(self, width=200, height=100):
        picker = selector.ScreenRegionSelector.__new__(selector.ScreenRegionSelector)
        picker.bounds = dict(left=-100, top=-50, width=width, height=height)
        picker.monitors = [picker.bounds]
        picker.closed = False
        picker.window, picker.master, picker.on_done = Mock(), Mock(), Mock()
        picker.canvas = Mock()
        picker.canvas.winfo_width.return_value = width
        picker.canvas.winfo_height.return_value = height
        picker._snapshot = Image.new('RGB', (width, height), (100, 160, 220))
        picker._background_photo = picker._selection_photo = picker._background_size = None
        picker._reveal_after = picker._pending_reveal = None
        picker._last_reveal = 0
        picker.panel = picker.panel_item = None
        return picker

    def test_snapshot_background_is_cached_and_reveal_preserves_actual_pixels(self):
        picker = self.picker()
        picker._snapshot.putpixel((20, 20), (255, 1, 2))
        picker._snapshot.putpixel((59, 49), (3, 4, 255))
        picker._pending_reveal = ScreenRegion(-80, -30, 40, 30)
        with patch.object(selector.ImageTk, 'PhotoImage', side_effect=lambda image, **kwargs: image.copy()) as photo:
            picker._draw_background()
            picker._draw_background()
            self.assertEqual(photo.call_count, 1)
            self.assertEqual(picker._background_photo.getpixel((40, 40)), (29, 46, 64))
            picker._paint_reveal()
        self.assertEqual(picker._selection_photo.size, (40, 30))
        self.assertEqual(picker._selection_photo.getpixel((0, 0)), (255, 1, 2))
        self.assertEqual(picker._selection_photo.getpixel((39, 29)), (3, 4, 255))
        self.assertEqual(picker.canvas.create_image.call_args.args[:2], (20, 20))

    def test_roi_throttle_keeps_latest_and_flushes_on_release(self):
        picker = self.picker()
        picker._last_reveal = 100
        picker.window.after.return_value = 'timer'
        picker._paint_reveal = Mock()
        with patch.object(selector.time, 'perf_counter', return_value=100.01):
            picker._queue_reveal(ScreenRegion(-80, -30, 50, 30))
            picker._queue_reveal(ScreenRegion(-80, -30, 60, 30))
            self.assertEqual(picker.window.after.call_count, 1)
            self.assertEqual(picker._pending_reveal.width, 60)
            picker._queue_reveal(picker._pending_reveal, immediate=True)
        picker.window.after_cancel.assert_called_once_with('timer')
        picker._paint_reveal.assert_called_once()

    def test_cancel_releases_images_timer_and_delivers_one_callback(self):
        picker = self.picker()
        picker._background_photo = object()
        picker._selection_photo = object()
        picker._reveal_after = 'timer'
        picker.finish(None)
        picker.finish(ScreenRegion(0, 0, 100, 100))
        self.assertIsNone(picker._snapshot)
        self.assertIsNone(picker._background_photo)
        self.assertIsNone(picker._selection_photo)
        picker.window.after_cancel.assert_called_once_with('timer')
        picker.window.destroy.assert_called_once()
        self.assertEqual(picker.master.after_idle.call_count, 1)
        picker.master.after_idle.call_args.args[0]()
        picker.on_done.assert_called_once_with(None)

    def test_capture_failure_never_opens_overlay(self):
        callback = Mock()
        monitor = dict(left=0, top=0, width=320, height=240)
        with patch.object(selector, 'screen_monitors', return_value=[monitor]), \
                patch.object(selector, 'ScreenCapture', side_effect=OSError('synthetic capture failure')), \
                patch.object(selector.tk, 'Toplevel') as window:
            with self.assertRaisesRegex(OSError, 'synthetic capture failure'):
                selector.ScreenRegionSelector(Mock(), on_done=callback)
        window.assert_not_called()
        callback.assert_not_called()

    def test_failure_after_window_creation_destroys_overlay_and_image(self):
        picker = selector.ScreenRegionSelector.__new__(selector.ScreenRegionSelector)
        capture = MagicMock()
        capture.__enter__.return_value.grab_bgr.return_value = np.zeros((240, 320, 3), np.uint8)
        window = Mock()
        with patch.object(selector, 'screen_monitors', return_value=[dict(left=0, top=0, width=320, height=240)]), \
                patch.object(selector, 'ScreenCapture', return_value=capture), \
                patch.object(selector.tk, 'Toplevel', return_value=window), patch.object(selector.tk, 'Canvas'), \
                patch.object(selector, 'place_physical_window', side_effect=OSError('synthetic placement failure')):
            with self.assertRaisesRegex(OSError, 'synthetic placement failure'):
                picker.__init__(Mock(), on_done=Mock())
        window.destroy.assert_called_once()
        self.assertIsNone(picker._snapshot)
        capture.__exit__.assert_called_once()

    def test_initial_render_failure_releases_image_even_if_tk_already_closed(self):
        picker = selector.ScreenRegionSelector.__new__(selector.ScreenRegionSelector)
        capture = MagicMock()
        capture.__enter__.return_value.grab_bgr.return_value = np.zeros((240, 320, 3), np.uint8)
        window = Mock()
        window.destroy.side_effect = selector.tk.TclError('already closed')
        with patch.object(selector, 'screen_monitors', return_value=[dict(left=0, top=0, width=320, height=240)]), \
                patch.object(selector, 'ScreenCapture', return_value=capture), \
                patch.object(selector.tk, 'Toplevel', return_value=window), patch.object(selector.tk, 'Canvas'), \
                patch.object(selector, 'place_physical_window'), \
                patch.object(selector.ScreenRegionSelector, 'redraw', side_effect=MemoryError('synthetic image allocation failure')):
            with self.assertRaisesRegex(MemoryError, 'synthetic image allocation failure'):
                picker.__init__(Mock(), on_done=Mock())
        self.assertTrue(picker.closed)
        self.assertIsNone(picker._snapshot)
        window.destroy.assert_called_once()

    def test_topology_change_and_query_failure_refuse_confirmation(self):
        for current in ([dict(left=0, top=0, width=200, height=100)], OSError('display removed')):
            picker = self.picker()
            picker.region = ScreenRegion(-80, -30, 40, 30)
            picker._error, picker.finish = Mock(), Mock()
            argument = {'side_effect': current} if isinstance(current, Exception) else {'return_value': current}
            with patch.object(selector, 'screen_monitors', **argument):
                picker.confirm()
            picker.finish.assert_not_called()
            picker._error.assert_called_once_with('显示器布局已改变，请取消后重新框选。')

    def test_cards_fit_short_narrow_negative_and_portrait_displays(self):
        for box in ((0, 0, 320, 240), (-640, -480, 0, 0), (2560, 0, 4720, 3840), (0, 0, 800, 480)):
            for request, preferred in (((700, 450), (box[2], box[3]+270)), ((200, 100), (box[0]-100, box[1]-100))):
                with self.subTest(box=box, request=request):
                    x, y, width, height = selector.card_geometry(box, request, preferred)
                    self.assertGreaterEqual(x, box[0])
                    self.assertGreaterEqual(y, box[1])
                    self.assertLessEqual(x+width, box[2])
                    self.assertLessEqual(y+height, box[3])

    def test_compact_help_and_error_cards_wrap_inside_real_screen(self):
        picker = self.picker(320, 240)
        picker.canvas = CanvasDouble(320, 240)
        picker._round_rectangle = Mock(return_value=1000)
        rows = [('Drag a region / 拖拽框选 · 支持跨屏', '#fff', 11, 'bold'),
                ('Enter: use   R: retry   Esc: cancel', '#fff', 9, 'normal'),
                ('Screen snapshot · Live capture starts after confirmation', '#fff', 9, 'normal'),
                ('Optional extra coordinates '*8, '#fff', 9, 'normal')]
        x, y, width, height = picker._text_card(picker.bounds, rows, (24, 300))
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x+width, 320)
        self.assertLessEqual(y+height, 240)
        for box in picker.canvas.items.values():
            self.assertGreaterEqual(box[0], 0)
            self.assertGreaterEqual(box[1], 0)
            self.assertLessEqual(box[2], 320)
            self.assertLessEqual(box[3], 240)

    def test_narrow_screen_stacks_buttons_and_clamps_confirmation_panel(self):
        picker = self.picker(320, 240)
        picker.bounds = dict(left=0, top=0, width=320, height=240)
        picker.monitors = [picker.bounds]
        picker.start = (20, 20)
        picker.t = lambda key: key+' / '+selector.TEXT.get(key, key)
        picker._accent = '#52e7ba'
        picker.canvas = CanvasDouble(320, 240)
        picker.redraw = Mock()
        buttons, labels = [], []

        def button(parent, **kwargs):
            widget = WidgetDouble(parent, **kwargs)
            buttons.append(widget)
            return widget

        def label(parent, **kwargs):
            widget = WidgetDouble(parent, **kwargs)
            labels.append(widget)
            return widget

        with ExitStack() as stack:
            stack.enter_context(patch.object(selector, 'physical_cursor_position', return_value=(300, 220)))
            stack.enter_context(patch.object(selector.tk, 'Frame', WidgetDouble))
            stack.enter_context(patch.object(selector.tk, 'Label', side_effect=label))
            stack.enter_context(patch.object(selector.tk, 'Button', side_effect=button))
            picker.up()
        self.assertEqual(len(buttons), 3)
        self.assertTrue(all(button.pack_options['side'] == 'top' for button in buttons))
        self.assertTrue(all(0 < label.options['wraplength'] < 320 for label in labels))
        x, y, options = picker.canvas.windows[0]
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x+options['width'], 320)
        self.assertLessEqual(y+options['height'], 240)


if __name__ == '__main__':
    unittest.main()
