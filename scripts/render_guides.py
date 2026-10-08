"""Render the English Markdown guide as PDF. No device or tool-bundle access."""
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

ROOT = Path(__file__).resolve().parents[1]
BLUE = colors.HexColor('#164568')
GRAY = colors.HexColor('#54616b')
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle('GuideBody', fontName='Helvetica', fontSize=10,
    leading=14, spaceAfter=7, textColor=colors.HexColor('#17232d')))
STYLES.add(ParagraphStyle('GuideTitle', parent=STYLES['GuideBody'], fontSize=23,
    leading=27, textColor=BLUE, spaceAfter=14, keepWithNext=True))
STYLES.add(ParagraphStyle('GuideH2', parent=STYLES['GuideBody'], fontSize=14,
    leading=18, textColor=BLUE, spaceBefore=12, spaceAfter=8, keepWithNext=True))
STYLES.add(ParagraphStyle('GuideH3', parent=STYLES['GuideBody'], fontSize=11,
    leading=15, textColor=BLUE, spaceBefore=6, keepWithNext=True))
STYLES.add(ParagraphStyle('GuideCode', fontName='Courier', fontSize=8.4,
    leading=12, spaceAfter=3, textColor=colors.HexColor('#22394d'),
    splitLongWords=True))
STYLES.add(ParagraphStyle('GuideCell', parent=STYLES['GuideBody'], fontSize=9,
    leading=12, spaceAfter=0, alignment=TA_LEFT))
STYLES.add(ParagraphStyle('GuideList', parent=STYLES['GuideBody'], leftIndent=15,
    firstLineIndent=-15, spaceAfter=5))


def inline(text):
    """Escape Markdown before converting supported inline markup."""
    text = escape(text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
                  r'<link href="\2" color="#164568">\1</link>', text)
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" size="8.6">\1</font>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    return text


def table(rows):
    cells = [[Paragraph(inline(value.strip()), STYLES['GuideCell'])
              for value in row.strip().strip('|').split('|')] for row in rows]
    cells = [row for row in cells if len(row) == 2]
    result = Table(cells, colWidths=[54 * mm, 119 * mm], repeatRows=1, hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e7eff5')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7f9')]),
        ('LINEBELOW', (0, 0), (-1, 0), 0.7, BLUE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    return result


def parse(source):
    lines = source.splitlines()
    flow, paragraph = [], []

    def flush():
        if paragraph:
            flow.append(Paragraph(inline(' '.join(paragraph)), STYLES['GuideBody']))
            paragraph.clear()

    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            flush()
        elif line.startswith('```'):
            flush()
            block = []
            index += 1
            while index < len(lines) and not lines[index].startswith('```'):
                block.append(Paragraph(escape(lines[index]).replace(' ', '&nbsp;'), STYLES['GuideCode']))
                index += 1
            box = Table([[block]], colWidths=[173 * mm], hAlign='LEFT')
            box.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f4f7')),
                ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#c5d1db')),
                ('LEFTPADDING', (0, 0), (-1, -1), 9),
                ('RIGHTPADDING', (0, 0), (-1, -1), 9),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            flow.extend([KeepTogether([box]), Spacer(1, 8)])
        elif line.startswith('|'):
            flush()
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                if not re.fullmatch(r'[| :\-]+', lines[index].strip()):
                    rows.append(lines[index])
                index += 1
            flow.extend([table(rows), Spacer(1, 9)])
            continue
        elif line.startswith('#'):
            flush()
            level = len(line) - len(line.lstrip('#'))
            style = 'GuideTitle' if level == 1 else 'GuideH2' if level == 2 else 'GuideH3'
            flow.append(Paragraph(inline(line.lstrip('#').strip()), STYLES[style]))
        elif re.match(r'\d+\. ', line):
            flush()
            flow.append(Paragraph(inline(line), STYLES['GuideList']))
        else:
            paragraph.append(line)
        index += 1
    flush()
    return flow


def render():
    source = ROOT / 'docs/guide-en.md'
    target = ROOT / 'docs/pdf/guide-en.pdf'
    target.parent.mkdir(exist_ok=True)
    title = 'SUNMI V2s | USB debugging'

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(GRAY)
        canvas.drawString(18 * mm, 284 * mm, title)
        canvas.setStrokeColor(colors.HexColor('#d1dae1'))
        canvas.line(18 * mm, 280 * mm, 192 * mm, 280 * mm)
        canvas.drawString(18 * mm, 12 * mm, 'SUNMI V2s USB Debugging Toolkit')
        canvas.drawRightString(192 * mm, 12 * mm, 'Page ' + str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(target), pagesize=(210 * mm, 297 * mm),
        leftMargin=18 * mm, rightMargin=19 * mm, topMargin=22 * mm,
        bottomMargin=22 * mm, title=title, author='SUNMI V2s USB Debugging Toolkit',
        subject='Setup, authenticated ADB access, APK installation and boot restoration')
    doc.build(parse(source.read_text(encoding='utf-8')), onFirstPage=page, onLaterPages=page)
    print('Generated: ' + str(target.relative_to(ROOT)))


if __name__ == '__main__':
    render()
