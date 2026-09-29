import io
import os
import struct
import unittest

from PIL import Image

from bandwagon.imaging import (
    _rgba_to_dibv5,
    pil_to_clipboard_mime,
    render_analysis_overlay,
)
from bandwagon.models import Lane


class ClipboardImageTest(unittest.TestCase):

    def test_overlay_only_renderer_keeps_transparent_background(self):
        source = Image.new("RGB", (100, 100), "white")
        lane = Lane(0, 20, 80)
        lane.peaks = [50]
        lane.peak_bounds = [(45, 55)]
        lane.mw = [10.0]

        overlay = render_analysis_overlay(source, [lane], transparent_bg=True)
        header_height = overlay.height - source.height

        self.assertEqual(overlay.mode, "RGBA")
        self.assertEqual(overlay.getpixel((0, header_height + 80))[3], 0)
        self.assertEqual(overlay.getpixel((50, header_height + 50))[3], 55)
        self.assertEqual(overlay.getpixel((20, header_height + 80))[3], 255)

    def test_clipboard_overlay_can_hide_numbers_without_losing_ladder_or_border(self):
        source = Image.new("RGB", (100, 100), "white")
        lane = Lane(0, 20, 80)
        lane.kind = "marker"
        lane.peaks = [50]
        lane.peak_bounds = [(45, 55)]
        lane.mw = [10.0]
        with_numbers = render_analysis_overlay(source, [lane], transparent_bg=True)
        without_numbers = render_analysis_overlay(
            source, [lane], transparent_bg=True, show_mw=False)
        self.assertNotEqual(with_numbers.tobytes(), without_numbers.tobytes())
        header_height = without_numbers.height - source.height
        self.assertEqual(without_numbers.getpixel((20, header_height + 80))[3], 255)
        self.assertEqual(without_numbers.getpixel((50, header_height + 50))[3], 55)

    def test_marker_and_border_only_keeps_marker_mw_and_all_lane_outlines(self):
        source = Image.new("RGB", (120, 100), "white")
        marker = Lane(0, 10, 50)
        marker.kind = "marker"
        marker.peaks = [40]
        marker.peak_bounds = [(35, 45)]
        marker.mw = [50.0]
        sample = Lane(1, 70, 110)
        sample.peaks = [70]
        sample.peak_bounds = [(65, 75)]

        overlay = render_analysis_overlay(
            source, [marker, sample], transparent_bg=True,
            marker_and_border_only=True)

        self.assertEqual(overlay.size, source.size)
        self.assertEqual(overlay.getpixel((10, 90))[3], 255)
        self.assertEqual(overlay.getpixel((70, 90))[3], 255)
        self.assertEqual(overlay.getpixel((30, 40))[3], 55)
        self.assertEqual(overlay.getpixel((90, 70))[3], 0)
        no_mw = render_analysis_overlay(
            source, [marker, sample], transparent_bg=True,
            marker_and_border_only=True, show_mw=False)
        self.assertNotEqual(overlay.tobytes(), no_mw.tobytes())

    def test_rgba_survives_png_and_qimage_clipboard_formats(self):
        source = Image.new("RGBA", (2, 2))
        source.putdata([
            (255, 0, 0, 0),
            (0, 255, 0, 55),
            (0, 0, 255, 128),
            (255, 255, 255, 255),
        ])

        mime = pil_to_clipboard_mime(source)

        png = Image.open(io.BytesIO(bytes(mime.data("image/png")))).convert("RGBA")
        self.assertEqual(png.tobytes(), source.tobytes())

        qimage = mime.imageData()
        self.assertTrue(qimage.hasAlphaChannel())
        self.assertEqual(
            [qimage.pixelColor(x, y).alpha() for y in range(2) for x in range(2)],
            [0, 55, 128, 255],
        )

        if os.name == "nt":
            native_png = 'application/x-qt-windows-mime;value="PNG"'
            self.assertEqual(bytes(mime.data(native_png)), bytes(mime.data("image/png")))

    def test_dibv5_declares_and_carries_full_alpha_channel(self):
        source = Image.new("RGBA", (2, 2))
        source.putdata([
            (255, 0, 0, 0),
            (0, 255, 0, 55),
            (0, 0, 255, 128),
            (255, 255, 255, 255),
        ])

        dib = _rgba_to_dibv5(source)
        size, width, height, planes, depth, compression = struct.unpack_from(
            "<IiiHHI", dib
        )

        self.assertEqual((size, width, height), (124, 2, -2))
        self.assertEqual((planes, depth, compression), (1, 32, 3))
        self.assertEqual(struct.unpack_from("<IIII", dib, 40), (
            0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
        ))
        self.assertEqual(dib[124:], source.tobytes("raw", "BGRA"))


if __name__ == "__main__":
    unittest.main()
