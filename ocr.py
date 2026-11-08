"""Text recognition using the OCR engine built into Windows 10 and 11."""
import asyncio
import cv2
import numpy as np


class Line:
    def __init__(self, text, x, y, w, h):
        self.text, self.x, self.y, self.w, self.h = text, x, y, w, h

    def __repr__(self):
        return "Line(%r, %d,%d %dx%d)" % (self.text, self.x, self.y, self.w, self.h)


def join_lines(lines):
    """Join OCR lines; a wide gap on the same row (label ... value) becomes a comma."""
    out = ""
    prev = None
    for l in lines:
        if prev is not None:
            same_row = abs((l.y + l.h / 2) - (prev.y + prev.h / 2)) < 15
            gap = l.x - (prev.x + prev.w)
            out += ", " if same_row and gap > 60 else " "
        out += l.text
        prev = l
    return out


class WindowsOcr:
    name = "Windows OCR"

    def __init__(self):
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import SoftwareBitmap, BitmapPixelFormat
        from winrt.windows.storage.streams import DataWriter
        self._SoftwareBitmap = SoftwareBitmap
        self._BGRA8 = BitmapPixelFormat.BGRA8
        self._DataWriter = DataWriter
        engine = None
        try:
            engine = OcrEngine.try_create_from_language(Language("en-US"))
        except Exception:
            engine = None
        if engine is None:
            engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("Windows has no OCR language installed. Add English in Settings, Time and language.")
        self.engine = engine
        self.loop = asyncio.new_event_loop()

    def _bitmap(self, img):
        if img.ndim == 2:
            bgra = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        else:
            bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        bgra = np.ascontiguousarray(bgra)
        h, w = bgra.shape[:2]
        writer = self._DataWriter()
        data = bgra.tobytes()
        try:
            writer.write_bytes(data)
        except TypeError:
            writer.write_bytes(list(data))
        buf = writer.detach_buffer()
        return self._SoftwareBitmap.create_copy_from_buffer(buf, self._BGRA8, w, h)

    async def _recognize(self, bmp):
        return await self.engine.recognize_async(bmp)

    def lines(self, img, scale=1.0):
        """Recognize text. Returned coordinates are divided by `scale`."""
        result = self.loop.run_until_complete(self._recognize(self._bitmap(img)))
        out = []
        for line in result.lines:
            rects = [w.bounding_rect for w in line.words]
            if not rects:
                continue
            x1 = min(r.x for r in rects)
            y1 = min(r.y for r in rects)
            x2 = max(r.x + r.width for r in rects)
            y2 = max(r.y + r.height for r in rects)
            out.append(Line(line.text, x1 / scale, y1 / scale, (x2 - x1) / scale, (y2 - y1) / scale))
        return out

    def text(self, img, scale=1.0):
        # Left to right within a row, so "P1 Life ... 100" keeps its order.
        lines = sorted(self.lines(img, scale), key=lambda l: (round((l.y + l.h / 2) / 25), l.x))
        return join_lines(lines)


class TesseractOcr:
    """Used only for testing away from Windows."""
    name = "Tesseract"

    def __init__(self):
        import pytesseract
        self.t = pytesseract

    def lines(self, img, scale=1.0):
        d = self.t.image_to_data(img, output_type=self.t.Output.DICT, config="--psm 11")
        rows = {}
        for i, word in enumerate(d["text"]):
            if not word.strip():
                continue
            key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
            rows.setdefault(key, []).append(i)
        out = []
        for idx in rows.values():
            x1 = min(d["left"][i] for i in idx); y1 = min(d["top"][i] for i in idx)
            x2 = max(d["left"][i] + d["width"][i] for i in idx); y2 = max(d["top"][i] + d["height"][i] for i in idx)
            out.append(Line(" ".join(d["text"][i] for i in idx), x1 / scale, y1 / scale, (x2 - x1) / scale, (y2 - y1) / scale))
        out.sort(key=lambda l: (l.y, l.x))
        return out

    def text(self, img, scale=1.0):
        return self.t.image_to_string(img, config="--psm 7").strip()


def make_ocr():
    try:
        return WindowsOcr()
    except ImportError:
        return TesseractOcr()
