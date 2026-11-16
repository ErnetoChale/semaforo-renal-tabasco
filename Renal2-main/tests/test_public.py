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

def fill(at, glucose=110., triglycerides=180.):
    at.number_input[0].set_value(glucose)
    at.number_input[1].set_value(triglycerides)
    at.checkbox[0].check()
    next(b for b in at.button if b.label == "Calcular mi índice TyG").click().run()

def test_default_entry_is_public_without_identity_or_database(monkeypatch):
    at = public_app(monkeypatch)
    assert not at.exception
    assert len(at.number_input) == 2
    assert all(w.value is None for w in at.number_input)
    assert not at.text_input
    assert not at.sidebar.radio
    assert "store" not in at.session_state
    assert "user" not in at.session_state
    assert not at.error

def test_public_calculation_does_not_store_or_classify(monkeypatch):
    at = public_app(monkeypatch)
    fill(at)
    assert not at.exception
    result = at.session_state["public_result"]
    assert result["tyg"] == pytest.approx(math.log(9900))
    assert "stratum" not in result
    assert "store" not in at.session_state
    assert "8.8" not in " ".join(m.value for m in at.markdown)

def test_public_validation_stale_result_and_clear(monkeypatch):
    at = public_app(monkeypatch)
    next(b for b in at.button if b.label == "Calcular mi índice TyG").click().run()
    assert at.error
    fill(at)
    assert "public_result" in at.session_state
    at.checkbox[0].uncheck()
    next(b for b in at.button if b.label == "Calcular mi índice TyG").click().run()
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
    assert len(at.number_input) == 2
