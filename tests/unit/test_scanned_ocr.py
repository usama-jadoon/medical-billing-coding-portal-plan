import io
import shutil
from pathlib import Path
import pytest
from PIL import Image, ImageDraw, ImageFont
from services.api.config import settings
from services.ocr.local_ocr import LocalOCRProvider


def synthetic_image():
    image = Image.new('RGB', (1600, 400), 'white')
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 38) if Path('C:/Windows/Fonts/arial.ttf').is_file() else ImageFont.load_default(size=38)
    ImageDraw.Draw(image).text((40, 50), 'Date of Service: 2026-10-14\nEquipment: CPAP\nOrder type: RENTAL', font=font, fill='black')
    return image


@pytest.mark.asyncio
async def test_real_image_and_scanned_pdf_preserve_text_spans(monkeypatch):
    command = shutil.which('tesseract') or ('C:/Program Files/Tesseract-OCR/tesseract.exe' if Path('C:/Program Files/Tesseract-OCR/tesseract.exe').is_file() else None)
    if not command:
        pytest.skip('Real OCR integration requires local Tesseract.')
    monkeypatch.setattr(settings, 'TESSERACT_CMD', command)
    for extension, format in [('png','PNG'), ('pdf','PDF')]:
        buffer = io.BytesIO()
        synthetic_image().save(buffer, format=format)
        result = await LocalOCRProvider().process(buffer.getvalue(), 'synthetic.' + extension)
        page = result.pages[0]
        assert 'CPAP' in page.text and 'RENTAL' in page.text
        assert page.word_spans and page.bounding_boxes
        for word in page.word_spans:
            assert page.text[word['start']:word['end']].strip()
            assert 0 <= word['bbox']['x'] <= 1 and 0 <= word['bbox']['y'] <= 1


@pytest.mark.asyncio
async def test_missing_engine_and_pixel_limits_are_visible(monkeypatch):
    data = io.BytesIO(); synthetic_image().save(data, format='PNG')
    monkeypatch.setattr(settings, 'TESSERACT_CMD', 'not-installed-remitvista-tesseract')
    with pytest.raises(ValueError, match='unavailable'):
        await LocalOCRProvider().process(data.getvalue(), 'test.png')
    monkeypatch.setattr(settings, 'OCR_MAX_PIXELS', 10)
    with pytest.raises(ValueError, match='pixel limit'):
        await LocalOCRProvider().process(data.getvalue(), 'test.png')
