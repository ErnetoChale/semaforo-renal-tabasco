from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "app.py")

def app(monkeypatch):
    monkeypatch.setenv("RENAL_MODE", "demo")
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["vista"] = "profesional"
    return at.run()

def test_all_demo_pages_render(monkeypatch):
    at = app(monkeypatch)
    assert not at.exception
    for page in ["Nueva evaluación", "Pacientes", "Seguimiento", "Historial", "Compartir calculadora", "Metodología", "Mi cuenta", "Administración", "Inicio"]:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, (page, at.exception)

def test_blank_inputs_and_invalid_submission_clear_preview(monkeypatch):
    at = app(monkeypatch)
    at.sidebar.radio[0].set_value("Nueva evaluación").run()
    assert all(widget.value is None for widget in at.number_input)
    next(b for b in at.button if b.label == "Calcular vista previa").click().run()
    assert not at.exception
    assert at.error
    assert "draft" not in at.session_state

def test_calculate_save_duplicate_and_reset(monkeypatch):
    at = app(monkeypatch)
    at.sidebar.radio[0].set_value("Nueva evaluación").run()
    before = len(at.session_state["store"].evaluations(at.session_state["user"]["id"]))
    values = {"Edad (años) *": 50, "Glucosa en ayunas (mg/dL) *": 110., "Triglicéridos (mg/dL) *": 180., "Creatinina prediálisis (mg/dL) *": 7.2, "Peso postdiálisis (kg) *": 68., "Talla (cm) *": 160.}
    for widget in at.number_input:
        widget.set_value(values[widget.label])
    next(c for c in at.checkbox if c.label.startswith("Verifiqué")).check()
    next(b for b in at.button if b.label == "Calcular vista previa").click().run()
    assert not at.exception
    assert "draft" in at.session_state
    assert len(at.session_state["store"].evaluations(at.session_state["user"]["id"])) == before
    next(c for c in at.checkbox if c.label.startswith("Confirmo que esta")).check().run()
    next(b for b in at.button if b.label == "Confirmar y guardar evaluación").click().run()
    assert not at.exception
    assert len(at.session_state["store"].evaluations(at.session_state["user"]["id"])) == before + 1
    assert all(widget.value is None for widget in at.number_input)
    assert "draft" not in at.session_state

def test_patient_navigation(monkeypatch):
    at = app(monkeypatch)
    at.sidebar.radio[0].set_value("Pacientes").run()
    next(b for b in at.button if b.label == "Registrar evaluación para este paciente").click().run()
    assert at.sidebar.radio[0].value == "Nueva evaluación"
    assert not at.exception

def test_persistent_mode_requires_key(monkeypatch):
    monkeypatch.setenv("RENAL_MODE", "clinical")
    monkeypatch.setenv("RENAL_DB_KEY", "")
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["vista"] = "profesional"
    at.run()
    assert not at.exception
    assert "RENAL_DB_KEY" in at.error[0].value
    assert not at.sidebar.radio

def test_bootstrap_login_logout_and_persistence(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("RENAL_MODE", "clinical")
    monkeypatch.setenv("RENAL_DB_PATH", str(tmp_path / "persistent.sqlite"))
    monkeypatch.setenv("RENAL_DB_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("RENAL_SETUP_TOKEN", "local-test-token-with-sufficient-entropy")
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["vista"] = "profesional"
    at.run()
    assert not at.exception
    values = {"Token de configuración": "local-test-token-with-sufficient-entropy", "Usuario administrador": "admin_pruebas", "Contraseña (mínimo 12 caracteres)": "Test-only-password-123", "Repetir contraseña": "Test-only-password-123"}
    for widget in at.text_input:
        widget.set_value(values[widget.label])
    next(b for b in at.button if b.label == "Crear cuenta administradora").click().run()
    assert not at.exception
    for widget in at.text_input:
        widget.set_value("admin_pruebas" if widget.label == "Usuario" else "Test-only-password-123")
    next(b for b in at.button if b.label == "Entrar a mi espacio").click().run()
    assert not at.exception
    assert at.sidebar.radio[0].value == "Inicio"
    at.sidebar.radio[0].set_value("Pacientes").run()
    next(w for w in at.text_input if w.label == "Nombre o seudónimo *").set_value("Paciente persistente de prueba")
    next(b for b in at.button if b.label == "Crear expediente").click().run()
    assert len(at.session_state["store"].patients(at.session_state["user"]["id"])) == 1
    next(b for b in at.sidebar.button if b.label == "Cerrar sesión").click().run()
    assert not at.exception
    assert "user" not in at.session_state
    assert "Iniciar sesión" in [h.value for h in at.subheader]
    for widget in at.text_input:
        widget.set_value("admin_pruebas" if widget.label == "Usuario" else "Test-only-password-123")
    next(b for b in at.button if b.label == "Entrar a mi espacio").click().run()
    assert not at.exception
    assert len(at.session_state["store"].patients(at.session_state["user"]["id"])) == 1

def test_modified_or_invalid_inputs_remove_old_preview(monkeypatch):
    at = app(monkeypatch)
    at.sidebar.radio[0].set_value("Nueva evaluación").run()
    next(b for b in at.button if b.label == "Cargar valores de ejemplo").click().run()
    next(c for c in at.checkbox if c.label.startswith("Verifiqué")).check()
    next(b for b in at.button if b.label == "Calcular vista previa").click().run()
    assert not at.exception
    assert "draft" in at.session_state
    next(c for c in at.checkbox if c.label.startswith("Verifiqué")).uncheck()
    next(b for b in at.button if b.label == "Calcular vista previa").click().run()
    assert not at.exception
    assert "draft" not in at.session_state
    assert at.error

def test_history_archive_and_restore(monkeypatch):
    at = app(monkeypatch)
    at.sidebar.radio[0].set_value("Historial").run()
    store, user = at.session_state["store"], at.session_state["user"]
    before = len(store.evaluations(user["id"]))
    eid = next(s for s in at.selectbox if s.label == "Abrir una evaluación").value
    next(c for c in at.checkbox if c.label.startswith("Confirmo que quiero archivar")).check().run()
    next(b for b in at.button if b.label == "Archivar evaluación").click().run()
    assert not at.exception
    assert len(store.evaluations(user["id"])) == before - 1
    next(c for c in at.checkbox if c.label == "Incluir archivadas").check().run()
    next(s for s in at.selectbox if s.label == "Abrir una evaluación").set_value(eid).run()
    next(c for c in at.checkbox if c.label.startswith("Confirmo que quiero restaurar")).check().run()
    next(b for b in at.button if b.label == "Restaurar evaluación").click().run()
    assert not at.exception
    assert len(store.evaluations(user["id"])) == before
