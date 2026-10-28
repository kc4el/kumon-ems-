#!/usr/bin/env python3
"""Place the 1080p transparent ERD on one landscape A4 page."""

from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "docs" / "erd.png"
OUTPUT = ROOT / "output" / "pdf" / "kumon-ems-erd-a4.pdf"

with Image.open(IMAGE) as artwork:
    if artwork.size != (1920, 1080) or artwork.mode != "RGBA":
        raise ValueError(f"Expected a transparent 1920x1080 PNG, got {artwork.size} {artwork.mode}")

page_width, page_height = landscape(A4)
margin = 8 * mm
scale = min((page_width - 2 * margin) / 1920, (page_height - 2 * margin) / 1080)
image_width, image_height = 1920 * scale, 1080 * scale
x, y = (page_width - image_width) / 2, (page_height - image_height) / 2

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
pdf = canvas.Canvas(str(OUTPUT), pagesize=(page_width, page_height), pageCompression=1)
pdf.setTitle("Kumon EMS Entity Relationship Diagram — A4 Landscape")
pdf.setAuthor("Kumon EMS documentation")
pdf.setFillColorRGB(1, 1, 1)
pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
pdf.drawImage(ImageReader(str(IMAGE)), x, y, width=image_width, height=image_height,
              preserveAspectRatio=True, mask="auto")
pdf.showPage()
pdf.save()
print(f"Wrote {OUTPUT} ({page_width:.2f} x {page_height:.2f} pt, one page)")
