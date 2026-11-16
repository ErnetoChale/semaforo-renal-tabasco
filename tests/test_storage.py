from dataclasses import replace
from datetime import date
import sqlite3
import pytest
from cryptography.fernet import Fernet
from renal.domain import Inputs
from renal.storage import Store, DuplicateEvaluation

@pytest.fixture
def case(tmp_path):
    key = Fernet.generate_key()
    path = tmp_path / "renal.sqlite"
    store = Store(path, key)
    owner = store.create_user("clinica_a", "A-strong-password-123", role="admin", bootstrap=True)
    other = store.create_user("clinica_b", "B-strong-password-123", actor=owner)
    patient = store.create_patient(owner, "Nombre privado de prueba", "Femenino")
    inputs = Inputs(50, 110.0, 180.0, 7.2, 68.0, 160.0, date.today().isoformat())
    yield store, owner, other, patient, inputs, key, path
    store.close()

def test_persistence_and_encryption(case):
    store, owner, _, patient, inputs, key, path = case
    eid = store.save_evaluation(owner, patient, inputs)
    store.db.execute("PRAGMA wal_checkpoint(FULL)")
    assert b"Nombre privado" not in path.read_bytes()
    raw = store.db.execute("SELECT payload FROM evaluations").fetchone()[0]
    assert b'"glucose"' not in raw
    reopened = Store(path, key)
    assert reopened.evaluation(owner, eid)["inputs"]["glucose"] == 110
    assert reopened.patient(owner, patient)["name"] == "Nombre privado de prueba"
    reopened.close()

def test_wrong_key_is_rejected(case):
    *_, path = case
    with pytest.raises(ValueError, match="clave"):
        Store(path, Fernet.generate_key())

def test_same_names_are_distinct(case):
    store, owner, _, patient, *_ = case
    second = store.create_patient(owner, "Nombre privado de prueba")
    assert patient != second
    assert len(store.patients(owner)) == 2

def test_other_user_cannot_read_edit_archive_or_export(case):
    store, owner, other, patient, inputs, *_ = case
    eid = store.save_evaluation(owner, patient, inputs)
    assert store.evaluations(other) == []
    assert store.patients(other) == []
    operations = [lambda: store.patient(other, patient), lambda: store.evaluation(other, eid), lambda: store.evaluations(other, patient), lambda: store.save_evaluation(other, patient, inputs), lambda: store.archive(other, eid, True, 1), lambda: store.update_patient(other, patient, "Cambio", "Femenino"), lambda: store.backup(other), lambda: store.list_users(other), lambda: store.create_user("intruso", "Another-password-123", role="admin", actor=other)]
    for operation in operations:
        with pytest.raises(PermissionError):
            operation()

def test_duplicates_and_same_day_confirmation(case):
    store, owner, _, patient, inputs, *_ = case
    store.save_evaluation(owner, patient, inputs)
    with pytest.raises(DuplicateEvaluation):
        store.save_evaluation(owner, patient, inputs, allow_same_day=True)
    with pytest.raises(DuplicateEvaluation):
        store.save_evaluation(owner, patient, replace(inputs, glucose=120))
    store.save_evaluation(owner, patient, replace(inputs, glucose=120), allow_same_day=True)
    with pytest.raises(DuplicateEvaluation):
        store.save_evaluation(owner, patient, replace(inputs, glucose=110), allow_same_day=True)

def test_edit_revision_and_restore(case):
    store, owner, _, patient, inputs, *_ = case
    eid = store.save_evaluation(owner, patient, inputs)
    store.save_evaluation(owner, patient, replace(inputs, glucose=120), eid, revision=1)
    assert store.evaluation(owner, eid)["revision"] == 2
    with pytest.raises(ValueError, match="Otra sesión"):
        store.save_evaluation(owner, patient, inputs, eid, revision=1)
    store.archive(owner, eid, True, 2)
    assert store.evaluations(owner) == []
    assert store.evaluations(owner, include_archived=True)[0]["archived"]
    store.archive(owner, eid, False, 3)
    assert len(store.evaluations(owner)) == 1

def test_passwords_locks_and_roles(case):
    store, owner, other, *_ = case
    assert store.authenticate(" CLINICA_A ", "A-strong-password-123")["id"] == owner
    for _ in range(5):
        with pytest.raises(ValueError, match="incorrectos"):
            store.authenticate("clinica_a", "incorrecta")
    with pytest.raises(ValueError, match="bloqueado"):
        store.authenticate("clinica_a", "A-strong-password-123")
    with pytest.raises(PermissionError):
        store.create_user("segundo", "Another-password-123", role="admin", bootstrap=True)
    store.set_user_active(owner, other, False)
    with pytest.raises(PermissionError):
        store.patients(other)
    with pytest.raises(ValueError):
        store.authenticate("clinica_b", "B-strong-password-123")

def test_backup_and_audit(case, tmp_path):
    store, owner, _, patient, inputs, key, _ = case
    eid = store.save_evaluation(owner, patient, inputs)
    backup = tmp_path / "backup.sqlite"
    backup.write_bytes(store.backup(owner))
    restored = Store(backup, key)
    assert restored.evaluation(owner, eid)["patient_id"] == patient
    restored.close()
    assert any(e["action"] == "database.backup" for e in store.audit(owner))
    assert all("Nombre privado" not in str(e) for e in store.audit(owner))

def test_change_password(case):
    store, owner, *_ = case
    store.change_password(owner, "A-strong-password-123", "New-strong-password-456")
    assert store.authenticate("clinica_a", "New-strong-password-456")["id"] == owner
    with pytest.raises(ValueError):
        store.authenticate("clinica_a", "A-strong-password-123")
