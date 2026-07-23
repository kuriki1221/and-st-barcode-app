"""
JANバーコードラベルPDF生成

用紙: A-one L24AM500N (A4 / 24面 / 3列x8段 / 1片70mm x 33.9mm)
1SKU = 1ページ（24面すべてに同じラベルをrepeat）
"""
import io
import os
import re
import zipfile
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.graphics.barcode.eanbc import Ean13BarcodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

FONT_NAME = "HeiseiKakuGo-W5"
_font_registered = False


def _ensure_font():
    global _font_registered
    if not _font_registered:
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
        _font_registered = True


PAGE_W, PAGE_H = A4
LABEL_W = 70 * mm
LABEL_H = 33.9 * mm
COLS = 3
ROWS = 8
MARGIN_Y = (PAGE_H - ROWS * LABEL_H) / 2

TEXT_AREA_W = 30 * mm
PADDING = 1.5 * mm
TEXT_LEFT_PADDING = 3.5 * mm
WRAP_SAFETY_MARGIN = 1.0 * mm
FONT_SIZE = 7
LINE_HEIGHT = FONT_SIZE * 1.2


def _wrap_text(text, max_width):
    tokens = re.split(r"(-)", text)
    lines = []
    current = ""
    for tok in tokens:
        candidate = current + tok
        if not current or stringWidth(candidate, FONT_NAME, FONT_SIZE) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = tok
    if current:
        lines.append(current)

    final_lines = []
    for line in lines:
        if stringWidth(line, FONT_NAME, FONT_SIZE) <= max_width:
            final_lines.append(line)
            continue
        buf = ""
        for ch in line:
            if not buf or stringWidth(buf + ch, FONT_NAME, FONT_SIZE) <= max_width:
                buf += ch
            else:
                final_lines.append(buf)
                buf = ch
        if buf:
            final_lines.append(buf)
    return final_lines


def _draw_label_cell(c, x, y, text, jan):
    """x, y はセル左下座標"""
    text_x = x + TEXT_LEFT_PADDING
    text_max_w = TEXT_AREA_W - TEXT_LEFT_PADDING - PADDING - WRAP_SAFETY_MARGIN
    lines = _wrap_text(text, text_max_w)
    total_h = LINE_HEIGHT * len(lines)
    start_y = y + LABEL_H / 2 + total_h / 2 - FONT_SIZE * 0.85

    c.setFont(FONT_NAME, FONT_SIZE)
    for i, line in enumerate(lines):
        c.drawString(text_x, start_y - i * LINE_HEIGHT, line)

    jan_digits = re.sub(r"\D", "", str(jan))
    if len(jan_digits) < 12:
        return  # JANが不正な場合はバーコードを描画しない
    barcode = Ean13BarcodeWidget(value=jan_digits[:13])
    bx0, by0, bx1, by1 = barcode.getBounds()
    bw, bh = bx1 - bx0, by1 - by0

    right_area_w = LABEL_W - TEXT_AREA_W - PADDING
    right_area_h = LABEL_H - 2 * PADDING
    scale = min(right_area_w / bw, right_area_h / bh)

    d = Drawing(bw * scale, bh * scale, transform=[scale, 0, 0, scale, -bx0 * scale, -by0 * scale])
    d.add(barcode)
    bx = x + TEXT_AREA_W
    by = y + (LABEL_H - bh * scale) / 2
    renderPDF.draw(d, c, bx, by)


_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def sku_filename(row):
    """SKU1件分のPDFファイル名を生成する（品番の"/"は"-"に置換、その他不正文字は除去）"""
    hinban = str(row["hinban"]).replace("/", "-")
    color_name = _INVALID_FILENAME_CHARS.sub("", str(row["color_name"]))
    size_name = _INVALID_FILENAME_CHARS.sub("", str(row["size_name"]))
    return f"{hinban}_{color_name}_{size_name}.pdf"


def _render_sku_page(c, row):
    text = f"{row['hinban']}-{row['color_name']}-{row['size_name']}"
    jan = row["jan"]
    for r in range(ROWS):
        for col in range(COLS):
            x = col * LABEL_W
            y = PAGE_H - MARGIN_Y - (r + 1) * LABEL_H
            _draw_label_cell(c, x, y, text, jan)
    c.showPage()


def generate_labels_pdf(sku_rows, output_path):
    """
    sku_rows: [{"hinban":..., "color_name":..., "size_name":..., "jan":...}, ...]
    1件 = 1ページ（24面すべてに同一内容）
    """
    _ensure_font()
    if isinstance(output_path, (str, os.PathLike)):
        output_path = str(output_path)
    c = canvas.Canvas(output_path, pagesize=A4)

    for row in sku_rows:
        _render_sku_page(c, row)

    c.save()


def generate_labels_zip(sku_rows, output_path):
    """
    sku_rows: [{"hinban":..., "color_name":..., "size_name":..., "jan":...}, ...]
    SKUごとに個別PDF（24面すべてに同一内容の1ページ）を作り、ZIPにまとめる。
    """
    _ensure_font()
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in sku_rows:
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=A4)
            _render_sku_page(c, row)
            c.save()
            zf.writestr(sku_filename(row), buf.getvalue())
