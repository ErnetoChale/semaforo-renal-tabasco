"""Complete, safely escaped exports built from stored evaluation snapshots."""
import csv
import io
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from renal.domain import METHOD_NOTE, STRATA, light_name

CSV_FIELDS = ["Evaluación ID", "Paciente ID", "Paciente", "Sexo", "Fecha", "Edad", "Glucosa (mg/dL)", "Triglicéridos (mg/dL)", "Creatinina prediálisis (mg/dL)", "Peso postdiálisis (kg)", "Talla (cm)", "TyG", "IMC (kg/m²)", "Patrón", "Corte TyG", "Corte creatinina (mg/dL)", "Versión del método", "Revisión", "Archivada", "Creada UTC", "Actualizada UTC"]

def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value

def csv_bytes(evaluations):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(CSV_FIELDS)
    for e in evaluations:
        i, r, p = e["inputs"], e["result"], e["patient_snapshot"]
        values = [e["id"], e["patient_id"], p["name"], p["sex"], e["evaluated_on"], i["age"], i["glucose"], i["triglycerides"], i["creatinine"], i["weight"], i["height"], r["tyg"], r["bmi"], STRATA[r["stratum"]]["title"], r["tyg_cutoff"], r["creatinine_cutoff"], r["method_version"], e["revision"], "Sí" if e["archived"] else "No", e["created_at"], e["updated_at"]]
        writer.writerow([safe_cell(v) for v in values])
    return stream.getvalue().encode("utf-8-sig")

def pdf_bytes(evaluation):
    e = evaluation
    i, r, p = e["inputs"], e["result"], e["patient_snapshot"]
    stratum = STRATA[r["stratum"]]
    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Brand", fontName="Helvetica-Bold", fontSize=21, leading=26, textColor=colors.HexColor("#12314B")))
    styles.add(ParagraphStyle("SmallRenal", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#526174")))
    styles.add(ParagraphStyle("Stratum", parent=styles["Heading2"], textColor=colors.HexColor(stratum["color"])))
    para = lambda value, style="BodyText": Paragraph(escape(str(value)), styles[style])
    story = [para("SEMÁFORO RENAL", "Brand"), para("TABASCO · REPORTE ACADÉMICO DE EVALUACIÓN", "SmallRenal"), Spacer(1, 16), para(f'Luz {light_name(stratum)} · {stratum["title"]}', "Stratum"), para(stratum["detail"]), para(f'Acción sugerida: {stratum["clinical_action"]}'), Spacer(1, 6), para(stratum.get("risks_title", "Si continúa así, podría aumentar el riesgo de") + ":"), *[para(f"• {x}") for x in stratum["risks"]], Spacer(1, 12)]
    rows = [
        ["Paciente", p["name"]], ["Identificador del paciente", e["patient_id"]],
        ["Evaluación", e["id"]], ["Fecha de evaluación", e["evaluated_on"]],
        ["Edad / sexo", f'{i["age"]} años / {p["sex"]}'],
        ["Glucosa en ayunas", f'{i["glucose"]:g} mg/dL'],
        ["Triglicéridos", f'{i["triglycerides"]:g} mg/dL'],
        ["Creatinina prediálisis", f'{i["creatinine"]:g} mg/dL'],
        ["Peso postdiálisis", f'{i["weight"]:g} kg'], ["Talla", f'{i["height"]:g} cm'],
        ["Índice TyG", f'{r["tyg"]:.6f}'], ["IMC", f'{r["bmi"]:.3f} kg/m²'],
        ["Cortes de la cohorte", f'TyG: {r["tyg_cutoff"]} / Creatinina: {r["creatinine_cutoff"]} mg/dL'],
        ["Método / revisión del registro", f'{r["method_version"]} / {e["revision"]}'],
        ["Estado del registro", "Archivada" if e["archived"] else "Activa"],
    ]
    table = Table([[para(a, "SmallRenal"), para(b)] for a, b in rows], colWidths=[5.4*cm, 12*cm], hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF5F5")), ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [table, Spacer(1, 14), para("Método y alcance", "Heading3"), para("TyG = ln(triglicéridos × glucosa / 2), con ambas concentraciones en mg/dL. IMC = peso (kg) / talla (m)². La clasificación utiliza el valor sin redondear."), Spacer(1, 8), para(METHOD_NOTE, "SmallRenal"), Spacer(1, 8), para("Fuente bibliográfica: pendiente de documentar y validar por el equipo responsable de la cohorte.", "SmallRenal")]
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#526174"))
        canvas.drawString(1.8*cm, 1*cm, "Semáforo Renal Tabasco · Uso académico · Contiene información de paciente")
        canvas.drawRightString(A4[0]-1.8*cm, 1*cm, f"Página {doc.page}")
    SimpleDocTemplate(out, pagesize=A4, rightMargin=1.8*cm, leftMargin=1.8*cm, topMargin=1.5*cm, bottomMargin=1.7*cm, title="Evaluación · Semáforo Renal", author="Semáforo Renal Tabasco").build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()
