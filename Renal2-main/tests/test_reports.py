import csv
from datetime import date
import io
from pypdf import PdfReader
from renal.demo import make_demo
from renal.domain import Inputs
from renal.reports import csv_bytes, pdf_bytes, CSV_FIELDS

def test_complete_csv_and_formula_injection():
    store, user = make_demo()
    patient = store.create_patient(user["id"], "=HYPERLINK(\"example\")")
    eid = store.save_evaluation(user["id"], patient, Inputs(50,110.,180.,7.2,68.,160.,date.today().isoformat()))
    record = store.evaluation(user["id"], eid)
    rows = list(csv.reader(io.StringIO(csv_bytes([record]).decode("utf-8-sig"))))
    assert rows[0] == CSV_FIELDS
    assert rows[1][2].startswith("'=")
    assert "110" in rows[1][6]
    assert "68" in rows[1][9]
    assert record["result"]["method_version"] in rows[1]
    store.close()

def test_pdf_handles_markup_long_names_and_keeps_method():
    store, user = make_demo()
    name = "<b>José & María</b> " + "Apellido " * 8
    patient = store.create_patient(user["id"], name[:100])
    eid = store.save_evaluation(user["id"], patient, Inputs(50,110.,180.,7.2,68.,160.,date.today().isoformat()))
    record = store.evaluation(user["id"], eid)
    output = pdf_bytes(record)
    assert output.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(output))
    text = " ".join(p.extract_text() for p in reader.pages)
    assert "<b>José & María</b>" in text
    assert "cohorte-1.0" in text
    assert "7.2 mg/dL" in text
    assert "pendiente" in text
    assert all(p.mediabox.width == 595.2756 for p in reader.pages)
    store.close()
