"""Bounded local Tesseract OCR. PHI never leaves the host."""
import csv
import io
import shutil
import subprocess
from PIL import Image, ImageSequence
from services.api.config import settings
from services.ocr.base import OCRPage, BoundingBox


def available():
    return bool(shutil.which(settings.TESSERACT_CMD))


def read_image(image, page_number):
    if image.width * image.height > settings.OCR_MAX_PIXELS:
        raise ValueError('OCR page exceeds the configured pixel limit.')
    command = shutil.which(settings.TESSERACT_CMD)
    if not command:
        raise ValueError('Local Tesseract is unavailable. Install it or set TESSERACT_CMD.')
    buffer = io.BytesIO()
    image.convert('RGB').save(buffer, format='PNG')
    try:
        process = subprocess.run([command, 'stdin', 'stdout', '-l', 'eng', 'tsv'],
            input=buffer.getvalue(), capture_output=True, timeout=settings.OCR_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ValueError('Local OCR timed out or could not start.') from exc
    if process.returncode:
        # Do not expose engine output: it may contain document data.
        raise ValueError('Local OCR failed; verify Tesseract and English language data.')
    text, boxes, spans, previous = '', [], [], None
    try:
        for row in csv.DictReader(io.StringIO(process.stdout.decode('utf-8')), delimiter='\t'):
            word = row['text'].strip()
            if row['level'] != '5' or not word:
                continue
            line = (row['block_num'], row['par_num'], row['line_num'])
            separator = '\n' if previous is not None and line != previous else ' ' if text else ''
            start = len(text) + len(separator)
            text += separator + word
            previous = line
            boxes.append(BoundingBox(x=int(row['left']) / image.width, y=int(row['top']) / image.height,
                width=int(row['width']) / image.width, height=int(row['height']) / image.height))
            spans.append({'start': start, 'end': len(text), 'bbox': boxes[-1].model_dump()})
    except (KeyError, ValueError, UnicodeError) as exc:
        raise ValueError('Local OCR returned malformed word coordinates.') from exc
    return OCRPage(page_number=page_number, text=text, bounding_boxes=boxes, word_spans=spans)


def image_pages(data):
    try:
        with Image.open(io.BytesIO(data)) as image:
            pages = []
            for i, frame in enumerate(ImageSequence.Iterator(image), start=1):
                if i > settings.OCR_MAX_PAGES:
                    raise ValueError('Document exceeds OCR page limit.')
                pages.append(read_image(frame, i))
            return pages
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError('Image is corrupt or exceeds safe image limits.') from exc


def pdf_page(data, index):
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(data) as document:
        page = document[index]
        width, height = page.get_size()
        scale = 200 / 72
        if width * height * scale ** 2 > settings.OCR_MAX_PIXELS:
            raise ValueError('Rendered PDF page exceeds OCR pixel limit.')
        bitmap = page.render(scale=scale)
        try:
            with bitmap.to_pil() as image:
                return read_image(image, index + 1)
        finally:
            bitmap.close()
            page.close()
