import io
import math
from pathlib import Path
import pytest
from PIL import Image
import zxingcpp
from streamlit.testing.v1 import AppTest
from renal.domain import calculate_tyg
from renal.sharing import public_calculator_url, qr_png

APP = str(Path(__file__).parents[1] / "app.py")

def public_app(monkeypatch):
    # The patient calculator must work even when professional storage is unconfigured.
    monkeypatch.setenv("RENAL_MODE", "clinical")
    monkeypatch.setenv("RENAL_DB_KEY", "")
    return AppTest.from_file(APP, default_timeout=30).run()

def fill(at, glucose=110., triglycerides=180., creatinine=7.2):
    if creatinine is None:
        at.radio[0].set_value("No").run()
    at.number_input[0].set_value(glucose)
    at.number_input[1].set_value(triglycerides)
    if creatinine is not None:
        at.number_input[2].set_value(creatinine)
    at.checkbox[0].check()
    next(b for b in at.button if b.label == "Ver mi semáforo").click().run()

def test_default_entry_is_public_without_identity_or_database(monkeypatch):
    at = public_app(monkeypatch)
    assert not at.exception
    assert len(at.number_input) == 3  # glucosa, triglicéridos y creatinina (hemodiálisis por defecto)
    assert at.radio[0].value == "Sí, estoy en hemodiálisis"
    assert all(w.value is None for w in at.number_input)
    assert not at.text_input
    assert not at.sidebar.radio
    assert "store" not in at.session_state
    assert "user" not in at.session_state
    assert not at.error

def test_public_hemodialysis_result_is_traffic_light_with_guidance(monkeypatch):
    at = public_app(monkeypatch)
    fill(at)
    assert not at.exception
    result = at.session_state["public_result"]
    assert result["tyg"] == pytest.approx(math.log(9900))
    assert result["light"] == "muscular"  # TyG 9.20 >= 8.8 y creatinina 7.2 < 8.5
    assert "store" not in at.session_state
    html = " ".join(m.value for m in at.markdown)
    assert "tl-housing" in html and "lamp on" in html
    assert "Sarcopenia metabólica" in html and "LUZ ROJA" in html
    assert "podría aumentar el riesgo" in html
    assert "kidney.org/es/temas-del-rinon" in html and 'target="_blank"' in html

@pytest.mark.parametrize("glucose,tg,creat,light", [
    (110, 180, 7.2, "muscular"), (85, 90, 7.0, "nutrition"), (110, 180, 10.0, "metabolic"), (85, 90, 10.0, "reference")])
def test_public_four_phenotypes(monkeypatch, glucose, tg, creat, light):
    at = public_app(monkeypatch)
    fill(at, glucose, tg, creat)
    assert at.session_state["public_result"]["light"] == light

@pytest.mark.parametrize("glucose,tg,band", [(85, 90, "green"), (95, 120, "yellow"), (110, 180, "red")])
def test_public_general_tyg_traffic_light(monkeypatch, glucose, tg, band):
    at = public_app(monkeypatch)
    fill(at, glucose, tg, creatinine=None)
    assert not at.exception
    assert len(at.number_input) == 2
    result = at.session_state["public_result"]
    assert result["light"] == band and result["inputs"]["creatinine"] is None
    assert "No existe un punto de corte universal" in " ".join(c.value for c in at.caption)

def test_hemodialysis_requires_creatinine(monkeypatch):
    at = public_app(monkeypatch)
    at.number_input[0].set_value(110.)
    at.number_input[1].set_value(180.)
    at.checkbox[0].check()
    next(b for b in at.button if b.label == "Ver mi semáforo").click().run()
    assert at.error and "public_result" not in at.session_state

def test_public_validation_stale_result_and_clear(monkeypatch):
    at = public_app(monkeypatch)
    next(b for b in at.button if b.label == "Ver mi semáforo").click().run()
    assert at.error
    fill(at)
    assert "public_result" in at.session_state
    at.checkbox[0].uncheck()
    next(b for b in at.button if b.label == "Ver mi semáforo").click().run()
    assert "public_result" not in at.session_state
    assert at.error
    fill(at)
    next(b for b in at.button if b.label == "Borrar mis datos y comenzar de nuevo").click().run()
    assert not at.exception
    assert "public_result" not in at.session_state
    assert all(w.value is None for w in at.number_input)

def test_public_sessions_are_independent(monkeypatch):
    a = public_app(monkeypatch)
    fill(a)
    b = public_app(monkeypatch)
    assert "public_result" not in b.session_state
    assert all(w.value is None for w in b.number_input)

@pytest.mark.parametrize("glucose,tg", [(None,180), (110,None), (0,180), (True,180), (float("nan"),180), (110,float("inf")), (1001,180), (110,3001)])
def test_public_domain_validation(glucose, tg):
    with pytest.raises(ValueError):
        calculate_tyg(glucose, tg)

@pytest.mark.parametrize("url", ["", "http://example.com", "https://localhost", "https://127.0.0.1", "https://192.168.1.2", "https://10.0.0.1", "https://127.1", "https://0x7f.1", "https://example.local", "https://user:password@example.com", "https://wrong host.com", "https://example.com:8501"])
def test_qr_rejects_local_or_invalid_links(url):
    with pytest.raises(ValueError):
        public_calculator_url(url)

def test_qr_link_discards_other_parameters_and_is_readable():
    link = public_calculator_url("https://renal.example.org/calculadora/?vista=profesional&glucose=110&token=secret#history")
    assert link == "https://renal.example.org/calculadora/?vista=publica"
    output = qr_png(link)
    decoded = zxingcpp.read_barcode(Image.open(io.BytesIO(output)))
    assert decoded is not None
    assert decoded.text == link

def test_explicit_public_route_ignores_professional_state(monkeypatch):
    at = public_app(monkeypatch)
    at.query_params["vista"] = "publica"
    at.run()
    assert not at.exception
    assert not at.sidebar.radio
    assert len(at.number_input) == 3
