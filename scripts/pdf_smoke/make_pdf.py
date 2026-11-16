import os
from pathlib import Path
SMOKE_DIR = Path(os.environ.get("PDF_SMOKE_DIR", "/tmp/enterprise-pdf-smoke"))
SMOKE_DIR.mkdir(parents=True, exist_ok=True)
"""Build the E2E demo PDF: prose p1, pricing table + screenshot p2."""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak, Image as RLImage

shot = Image.new('RGB', (640, 220), 'white')
d = ImageDraw.Draw(shot)
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 24)
d.rectangle([0, 0, 639, 219], outline='gray')
d.text((24, 30), 'Support Dashboard', fill='black', font=font)
d.text((24, 90), 'Status: all services operational', fill='darkgreen', font=font)
d.text((24, 150), 'Escalation: press the red button', fill='red', font=font)
shot.save(str(SMOKE_DIR / 'shot.png'))

buf = BytesIO()
doc = SimpleDocTemplate(buf, pagesize=letter)
styles = getSampleStyleSheet()
story = [
    Paragraph('Acme Support Handbook', styles['Title']),
    Spacer(1, 12),
    Paragraph('Refund policy: customers can request a refund within 30 days of purchase by contacting the support team with their order number.', styles['BodyText']),
    Spacer(1, 8),
    Paragraph('Password resets are self-service from the account settings page.', styles['BodyText']),
    PageBreak(),
    Paragraph('Plans and pricing', styles['Heading2']),
    Spacer(1, 6),
]
t = Table([['Plan', 'Monthly price', 'Support channel'], ['Basic', '$10', 'Email'], ['Pro', '$25', 'Priority 24/7']])
t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.black)]))
story.append(t)
story.append(Spacer(1, 12))
story.append(Paragraph('Agent dashboard screenshot:', styles['BodyText']))
story.append(RLImage(str(SMOKE_DIR / 'shot.png'), width=384, height=132))
doc.build(story)
open(str(SMOKE_DIR / 'handbook.pdf'), 'wb').write(buf.getvalue())
print('PDF written', len(buf.getvalue()), 'bytes')
