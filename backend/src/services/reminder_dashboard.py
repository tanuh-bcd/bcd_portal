"""Email-safe presentation of the Stats.js / Stats.css dashboard theme.

Raster charts use the dashboard's Poppins font and risk colours so email clients
need no JavaScript, SVG support, external assets, or web-font loading.
"""
import base64
from datetime import datetime, timedelta
from functools import lru_cache
from html import escape
from io import BytesIO
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..core.config import settings

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'reminders'
TEAL = '#14868C'
INK = '#34495e'
BACKGROUND = '#FDFCFC'
# Same order, labels, and colours as Stats.js.
RISK_SERIES = (
    ('Baseline Risk', '#6ee7b7'), ('Evident Risk', '#fde047'),
    ('Significant Risk', '#fb923c'), ('High Risk', '#fb7185'),
)


def data_image(data):
    return 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')


@lru_cache(maxsize=None)
def logo(name):
    return data_image((ASSETS / name).read_bytes())


def month_data(report):
    months = dict(report.month_counts)
    if report.collection_start_date:
        cursor = report.collection_start_date.replace(day=1)
        while cursor <= report.report_date:
            months.setdefault(cursor.strftime('%Y-%m'), 0)
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return sorted(months.items())


def monthly_chart(report):
    """Return one PNG with vertical stacked bars, axes and the dashboard legend."""
    months = month_data(report)
    # Wrap long histories into panels rather than omit early contributions.
    panels = [months[i:i + 12] for i in range(0, len(months), 12)] or [[]]
    scale, width, panel_height = 2, 620, 280
    image = Image.new('RGB', (width * scale, (len(panels) * panel_height + 64) * scale), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(ASSETS / 'Poppins-Regular.ttf'), 11 * scale)
    bold = ImageFont.truetype(str(ASSETS / 'Poppins-SemiBold.ttf'), 11 * scale)
    def label(x, y, value, color=TEAL, anchor='mm', weight=False):
        draw.text((x * scale, y * scale), str(value), fill=color,
                  font=bold if weight else font, anchor=anchor)
    maximum = max((n for _, n in months), default=0)
    step = max(1, ceil(maximum / 4))
    top_value = step * 4
    for panel_index, panel in enumerate(panels):
        top = panel_index * panel_height + 24
        bottom, left, right = top + 190, 42, width - 18
        for tick in range(5):
            value = tick * step
            y = bottom - tick * 190 / 4
            draw.line((left * scale, y * scale, right * scale, y * scale), fill='#e2eeee', width=scale)
            label(left - 12, y, value, anchor='rm')
        if not panel:
            label(width / 2, top + 95, 'Data collection has not started', color='#7f8c8d')
        for index, (month, total) in enumerate(panel):
            slot = (right - left) / len(panel)
            center = left + slot * (index + .5)
            bar_width = min(58, slot * .66)
            values = report.month_risk_counts.get(month)
            if values is None:
                # Older stored/test reports lack risk bins; show an honest total,
                # never assign a risk category to those subjects.
                segments = [(total, TEAL)]
            else:
                segments = [(value, RISK_SERIES[i][1]) for i, value in enumerate(values)]
            y = bottom
            for value, color in segments:
                height = value / top_value * 190
                if height:
                    draw.rectangle(((center - bar_width / 2) * scale, (y - height) * scale,
                                    (center + bar_width / 2) * scale, y * scale), fill=color)
                    y -= height
            label(center, y - 10, total, weight=True)
            dt = datetime.strptime(month, '%Y-%m')
            label(center, bottom + 17, dt.strftime('%b'))
            label(center, bottom + 33, dt.strftime('%Y'))
    legend_y = len(panels) * panel_height + 8
    series = RISK_SERIES if report.month_risk_counts else (('Total subjects', TEAL),)
    # Two columns preserve readable labels at mobile email widths.
    for index, (name, color) in enumerate(series):
        x = 100 + (index % 2) * 260
        y = legend_y + (index // 2) * 25
        draw.rounded_rectangle((x * scale, y * scale, (x + 11) * scale, (y + 11) * scale),
                               radius=2 * scale, fill=color)
        label(x + 18, y + 6, name, anchor='lm', weight=True)
    output = BytesIO()
    image.save(output, format='PNG', optimize=True)
    return data_image(output.getvalue())


def dashboard_fragment(report):
    cards = (('Total subjects', report.data_points), ('Reports uploaded', report.reports_uploaded),
             ('Image records', report.image_records), ('Image studies', report.image_studies))
    cells = []
    for title, count in cards:
        cells.append(
            '<td width="50%" style="padding:8px;vertical-align:top">'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            'style="background:#ebedee;background:linear-gradient(135deg,#fdfbfb 0%,#ebedee 100%);'
            'border:1px solid #e8e8e8;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,.05)">'
            '<tr><td align="center" style="padding:22px 8px">'
            f'<div style="font-size:12px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'
            f'color:{INK}">{title}</div>'
            f'<div style="font-size:46px;line-height:1.4;font-weight:800;color:{TEAL}">{count:,}</div>'
            '</td></tr></table></td>')
    start = report.collection_start_date.strftime('%d %B %Y') if report.collection_start_date else 'Not started'
    monthly_totals = '; '.join(f'{month}: {count}' for month, count in month_data(report))
    return (
        '<section style="margin-top:24px">'
        f'<h2 style="margin:0;text-align:center;color:{TEAL};font-size:20px">Your contribution at a glance</h2>'
        f'<p style="text-align:center;color:{INK};font-size:13px;margin:8px 0 0">{escape(report.hospital_name)}</p>'
        f'<p style="text-align:center;color:#7f8c8d;font-size:12px;margin:8px 0 18px">'
        f'Collection start: {start}<br>All contributions through {report.report_date.strftime("%d %B %Y")}</p>'
        f'<table role="presentation" width="100%" cellspacing="0"><tr>{"".join(cells[:2])}</tr>'
        f'<tr>{"".join(cells[2:])}</tr></table>'
        '<table role="presentation" width="100%" cellspacing="0" style="margin-top:20px;'
        f'background:{BACKGROUND};border:1px solid #f0f0f0;border-radius:12px">'
        f'<tr><td style="padding:20px 12px"><h3 style="color:{INK};text-align:center;'
        'font-size:16px;margin:0 0 12px">Month-wise Distribution</h3>'
        f'<img src="{monthly_chart(report)}" width="620" style="width:100%;height:auto;display:block" '
        f'alt="Monthly subjects — {escape(monthly_totals, quote=True)}"></td></tr></table>'
        '<p style="font-size:10px;color:#7f8c8d;line-height:1.6;margin:14px 8px">'
        'Reports: uploaded mammogram reports. Image records: uploaded mammogram files. '
        'Image studies: subjects with mammogram images.</p></section>')


def email_document(content, heading="PinkShieldAI update", subtitle="Hospital data collection programme"):
    """A compact letter layout that retains the dashboard brand palette."""
    logos = ''.join(f'<td align="center" style="padding:0 12px"><img src="{logo(file)}" '
                    f'height="{height}" alt="{alt}" style="height:{height}px;width:auto"></td>'
                    for file, height, alt in [('tanuh.png', 34, 'TANUH'), ('moe.png', 34, 'Ministry of Education'),
                                              ('IISc_logo.png', 44, 'IISc')])
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#f3f5f6;font-family:Poppins,Arial,sans-serif;'
        f'color:{INK}"><table role="presentation" width="100%" cellspacing="0" cellpadding="0">'
        '<tr><td align="center" style="padding:24px 10px">'
        f'<table role="presentation" width="700" cellspacing="0" style="width:100%;max-width:700px;background:{BACKGROUND};'
        f'border:1px solid #e7eded;border-top:5px solid {TEAL};border-radius:16px">'
        '<tr><td style="padding:26px 26px 18px;text-align:left">'
        '<table role="presentation" width="100%" cellspacing="0"><tr>'
        '<td style="color:#e91e8c;font-size:27px;font-weight:800;letter-spacing:.3px">PinkShieldAI</td>'
        f'<td align="right" style="color:{TEAL};font-size:10px;font-weight:600;letter-spacing:1px;'
        'text-transform:uppercase">Hospital partnerships</td></tr></table>'
        f'<p style="font-size:11px;color:#7f8c8d;margin:6px 0 22px">{escape(subtitle)}</p>'
        f'<h1 style="margin:0 0 20px;font-size:12px;letter-spacing:1.5px;text-transform:uppercase;'
        f'color:{TEAL}">{escape(heading)}</h1>' + content +
        '<table role="presentation" width="100%" cellspacing="0" style="margin-top:24px;'
        'border-top:1px solid #e5eeee"><tr><td align="center" style="padding-top:24px">'
        f'<table role="presentation" cellspacing="0"><tr>{logos}</tr></table></td></tr></table>'
        '<p style="text-align:center;font-size:10px;color:#7f8c8d;line-height:1.7;margin-top:18px">'
        'Questions or assistance? Reply to this email or contact<br>'
        f'<a style="color:{TEAL}" href="mailto:breastcancerscreening@tanuh.ai">breastcancerscreening@tanuh.ai</a></p>'
        '<p style="text-align:center;font-size:9px;color:#8b969b">This update contains aggregate hospital statistics only.</p>'
        '</td></tr></table></td></tr></table></body></html>')


def hospital_document(report):
    """Appreciative hospital letter with a cumulative analytics snapshot."""
    name = escape(report.hospital_name)
    hero = (
        f'<table role="presentation" width="100%" cellspacing="0" style="background:{TEAL};'
        'border-radius:14px"><tr><td style="padding:28px 26px;border-left:5px solid #e91e8c;'
        'border-radius:14px">'
        '<p style="margin:0 0 10px;color:#d8f2ee;font-size:10px;font-weight:600;'
        'letter-spacing:1.8px;text-transform:uppercase">With appreciation</p>'
        '<h2 style="margin:0;color:#ffffff;font-size:28px;line-height:1.3;font-weight:700">'
        'Your contribution matters.</h2>'
        '<p style="margin:12px 0 0;color:#e9f7f5;font-size:13px;line-height:1.7">'
        'Thank you for supporting a shared foundation for breast cancer research.</p>'
        '</td></tr></table>')
    introduction = (
        '<div style="font-size:13px;line-height:1.85;margin:26px 4px 20px">'
        f'<p style="margin:0 0 14px;font-weight:600;color:{INK}">Dear {name} Team,</p>'
        '<p style="margin:0 0 14px">Thank you for your continued contribution to the '
        '<strong>PinkShieldAI data collection platform</strong>. We sincerely appreciate the '
        'time and care your team dedicates to sharing subject information, mammogram images, '
        'and reports.</p>'
        '<p style="margin:0">Your participation helps build a valuable resource for breast cancer '
        "research. Below is a summary of your hospital's contributions "
        '<strong>since data collection began</strong>.</p></div>')
    continuation = (
        '<table role="presentation" width="100%" cellspacing="0" style="background:#edf7f6;'
        'border-radius:12px;margin-top:22px"><tr><td style="padding:22px 24px">'
        f'<h3 style="font-size:16px;color:{TEAL};margin:0 0 10px">Continuing our progress together</h3>'
        '<p style="font-size:13px;line-height:1.8;margin:0">We encourage your team to continue '
        'contributing eligible records and to complete any pending assessments, image uploads, '
        'and reports as they become available. Consistent, complete submissions help strengthen '
        'the quality and usefulness of the shared dataset.</p></td></tr></table>'
        '<p style="text-align:center;margin:26px 0">'
        f'<a href="{escape(settings.REMINDER_PORTAL_URL, quote=True)}" style="display:inline-block;'
        f'background:{TEAL};color:#ffffff;padding:14px 26px;border-radius:7px;text-decoration:none;'
        'font-size:13px;font-weight:600">Continue contributing</a></p>'
        '<div style="font-size:13px;line-height:1.85;margin:24px 4px 0">'
        '<p>Thank you once again for your commitment and collaboration. '
        'We look forward to your continued participation.</p>'
        f'<p style="margin-bottom:0">Warm regards,<br><strong style="color:{TEAL}">The PinkShieldAI Team</strong></p>'
        '</div>')
    return email_document(hero + introduction + dashboard_fragment(report) + continuation,
                          heading="Your fortnightly contribution update",
                          subtitle=f"Prepared for {report.hospital_name} · {report.report_date.strftime('%d %B %Y')}")


def summary_document(reports):
    def row(values, header=False):
        tag = 'th' if header else 'td'
        return '<tr>' + ''.join(f'<{tag} style="padding:10px 8px;border-bottom:1px solid #e5eeee;'
                                f'text-align:left;color:{TEAL if header else INK};font-size:11px">'
                                f'{escape(str(value))}</{tag}>' for value in values) + '</tr>'
    rows = row(['Hospital', 'Subjects', 'Reports uploaded', 'Image records', 'Image studies'], True)
    for report in reports:
        rows += row([report.hospital_name, report.data_points, report.reports_uploaded,
                     report.image_records, report.image_studies])
    rows += row(['Total'] + [sum(getattr(r, key) for r in reports) for key in
                            ('data_points', 'reports_uploaded', 'image_records', 'image_studies')], True)
    return email_document(f'<h2 style="color:{TEAL};text-align:center;font-size:20px">All hospitals update</h2>'
                          '<table width="100%" cellspacing="0" style="border:1px solid #eeeeee;'
                          'border-radius:12px;background:#fdfcfc">' + rows + '</table>' +
                          ''.join(dashboard_fragment(r) for r in reports))
