# generate_pdf.py
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import os

def create_pdf(crop_name, disease, confidence, disease_info, image_path):
    reports_dir = os.path.join("static", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    pdf_path = os.path.join(reports_dir, f"report_{disease}.pdf")

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()

    # Custom style definitions
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        alignment=1,  # center
        fontSize=20,
        textColor=colors.HexColor("#075e2b"),
        spaceAfter=20
    )
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        textColor=colors.HexColor("#0b572d"),
        spaceAfter=10
    )
    normal_style = styles['Normal']

    story = []

    # Title
    story.append(Paragraph("🌿 Smart Disease Diagnosis of Pearl Millet Plant using KNN & Artificial Intelligence", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("<b>Uploaded Leaf Report</b>", heading_style))
    story.append(Spacer(1, 15))

    # Info Table
    data = [
        ["<b>Crop Name:</b>", crop_name],
        ["<b>Detected Disease:</b>", disease],
        ["<b>Confidence:</b>", confidence],
        ["<b>Disease Info:</b>", disease_info],
    ]
    table = Table(data, colWidths=[150, 350])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#d9ead3")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#0b572d")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.gray),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
    ]))
    story.append(table)
    story.append(Spacer(1, 25))

    # Image Section
    if os.path.exists(image_path):
        story.append(Paragraph("<b>Detected Image:</b>", heading_style))
        story.append(Spacer(1, 10))
        try:
            story.append(Image(image_path, width=300, height=300))
        except Exception as e:
            story.append(Paragraph(f"(Image could not be loaded: {e})", normal_style))
    else:
        story.append(Paragraph("(No image found for this record)", normal_style))

    # Footer
    story.append(Spacer(1, 25))
    story.append(Paragraph(
        "<i>Generated automatically using Smart Pearl Millet Disease Diagnosis System</i>",
        ParagraphStyle('Footer', parent=normal_style, fontSize=9, textColor=colors.gray, alignment=1)
    ))

    doc.build(story)
    return pdf_path
