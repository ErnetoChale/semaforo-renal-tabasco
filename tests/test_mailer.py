from pathlib import Path
from urllib.parse import unquote
from streamlit.testing.v1 import AppTest
import renal.public_view as public_view
from renal.mailer import SmtpConfig, mailto_link, send_result, valid_email
import pytest

APP = str(Path(__file__).parents[1] / "app.py")

def test_email_validation():
    assert valid_email("nombre@correo.com")
    assert valid_email(" ana.perez+tyg@ujat.mx ")
    for bad in ["", "sin-arroba", "a@b", "a b@c.com", "a@b.com, c@d.com", "x@y.com\nBcc: z@w.com"]:
        assert not valid_email(bad)

def test_mailto_prefills_result_and_only_valid_recipient():
    link = mailto_link("nombre@correo.com", "Resultado: 9.20")
    assert link.startswith("mailto:nombre%40correo.com?subject=")
    assert "Resultado: 9.20" in unquote(link)
    assert mailto_link("no es correo", "x").startswith("mailto:?subject=")

def test_smtp_config_requires_credentials():
    values = {"RENAL_SMTP_HOST": "smtp.gmail.com", "RENAL_SMTP_USER": "a@gmail.com", "RENAL_SMTP_PASSWORD": "clave"}
    cfg = SmtpConfig.from_settings(lambda k: values.get(k, ""))
    assert cfg.port == 587 and cfg.sender == "a@gmail.com"
    assert SmtpConfig.from_settings(lambda k: "") is None

def test_send_rejects_invalid_address():
    with pytest.raises(ValueError):
        send_result(SmtpConfig("h", 587, "u", "p", "u"), "x@y.com\nBcc: z@w.com", "body")

def result_app(monkeypatch, smtp=False):
    monkeypatch.setenv("RENAL_MODE", "demo")
    for key in ("HOST", "USER", "PASSWORD"):
        if smtp:
            monkeypatch.setenv(f"RENAL_SMTP_{key}", "valor@ejemplo.com")
        else:
            monkeypatch.delenv(f"RENAL_SMTP_{key}", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.number_input[0].set_value(110.)
    at.number_input[1].set_value(180.)
    at.checkbox[0].check()
    next(b for b in at.button if b.label == "Calcular mi índice TyG").click().run()
    return at

def test_without_smtp_offers_mail_app_link(monkeypatch):
    at = result_app(monkeypatch)
    assert not at.exception
    assert len(at.text_input) == 1
    assert not any(b.label == "Enviar a mi correo" for b in at.button)

def test_with_smtp_sends_once_and_does_not_store_address(monkeypatch):
    sent = []
    monkeypatch.setattr(public_view, "send_result", lambda cfg, to, body: sent.append((to, body)))
    at = result_app(monkeypatch, smtp=True)
    at.text_input[0].set_value("persona@correo.com").run()
    next(b for b in at.button if b.label == "Enviar a mi correo").click().run()
    assert not at.exception
    assert at.success
    assert sent and sent[0][0] == "persona@correo.com" and "Resultado: 9.2" in sent[0][1]
    assert "store" not in at.session_state

def test_with_smtp_invalid_address_shows_error(monkeypatch):
    monkeypatch.setattr(public_view, "send_result", lambda *a: pytest.fail("no debe enviar"))
    at = result_app(monkeypatch, smtp=True)
    at.text_input[0].set_value("no-es-correo").run()
    next(b for b in at.button if b.label == "Enviar a mi correo").click().run()
    assert at.error
