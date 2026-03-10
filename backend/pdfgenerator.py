from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import time

def generate_invoice(text, items=None, shop_info=None):
    # simple invoice with basic styling
    name = f"invoice_{int(time.time())}.pdf"
    doc = SimpleDocTemplate(name, pagesize=A4)
    styles = getSampleStyleSheet()

    # title
    title = Paragraph("Invoice", styles['Title'])
    content = [title, Spacer(1, 0.2*inch)]

    # parse fields from text
    data = {}
    for line in text.split('\n'):
        if ': ' in line:
            key, value = line.split(': ', 1)
            data[key.strip().lower().replace(' ', '_')] = value.strip()

    # basic company/shop info
    if shop_info:
        shop_lines = []
        if shop_info.get('name'): shop_lines.append(f"<b>{shop_info['name']}</b>")
        if shop_info.get('address'): shop_lines.append(shop_info['address'])
        if shop_info.get('phone'): shop_lines.append(f"Phone: {shop_info['phone']}")
        if shop_info.get('email'): shop_lines.append(f"Email: {shop_info['email']}")
        company_str = '<br/>'.join(shop_lines)
    else:
        company_str = "<b>Company Name</b><br/>Address Line 1<br/>Phone: 1234567890"
    company = Paragraph(company_str, styles['Normal'])
    content.append(company)
    content.append(Spacer(1, 0.2*inch))

    # invoice details
    inv_no = data.get('invoice_number', f"INV-{int(time.time())}")
    inv_date = data.get('date', time.strftime("%Y-%m-%d"))
    inv_info = Paragraph(f"Invoice #: {inv_no}<br/>Date: {inv_date}", styles['Normal'])
    content.append(inv_info)
    content.append(Spacer(1, 0.2*inch))

    # bill to
    content.append(Paragraph("<b>Bill To:</b><br/>" + data.get('customer', 'Customer'), styles['Normal']))
    content.append(Spacer(1, 0.2*inch))

    # items table
    if items:
        table_data = [['Description', 'Qty', 'Unit Price', 'Total']]
        subtotal = 0
        for item in items:
            desc = item.get('product', '')
            qty = item.get('quantity', 1)
            price = item.get('unit_price', 0)
            total = qty * price
            subtotal += total
            table_data.append([desc, str(qty), f"{price}", f"{total}"])
        table = Table(table_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.2*inch])
        table.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),1,colors.black),
            ('BACKGROUND',(0,0),(-1,0),colors.gray),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke)
        ]))
        content.append(table)
    else:
        content.append(Paragraph("No items", styles['Normal']))

    doc.build(content)
    return name
