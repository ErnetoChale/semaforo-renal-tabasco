"""SQLite persistence with encrypted patient payloads and owner-scoped access."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import uuid

from cryptography.fernet import Fernet, InvalidToken
from renal.auth import hash_password, normalize_username, verify_password
from renal.domain import Inputs, calculate

class DuplicateEvaluation(ValueError):
    pass

class Store:
    def __init__(self, path, encryption_key):
        self.cipher = Fernet(encryption_key)
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=15, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(
            id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','clinician')), active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS patients(
            id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), payload BLOB NOT NULL,
            created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evaluations(
            id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id),
            evaluated_on TEXT NOT NULL, payload BLOB NOT NULL, fingerprint TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1, archived INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS active_fingerprint ON evaluations(patient_id,fingerprint) WHERE archived=0;
        CREATE INDEX IF NOT EXISTS patient_owner ON patients(owner_id);
        CREATE INDEX IF NOT EXISTS evaluation_patient ON evaluations(patient_id,evaluated_on);
        CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY, actor_id TEXT NOT NULL, action TEXT NOT NULL,
            resource_id TEXT NOT NULL, occurred_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(
            username TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until REAL NOT NULL);
        """)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            marker = self.db.execute("SELECT value FROM metadata WHERE key='key_check'").fetchone()
            if marker:
                try:
                    if self.cipher.decrypt(marker[0].encode()) != b"renal-key-v1":
                        raise ValueError("La clave de cifrado no corresponde a esta base de datos.")
                except InvalidToken:
                    raise ValueError("La clave de cifrado no corresponde a esta base de datos.") from None
            else:
                self.db.execute("INSERT INTO metadata VALUES('key_check',?)", (self.cipher.encrypt(b"renal-key-v1").decode(),))
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES('schema_version','1')")

    def close(self):
        self.db.close()

    def _encrypt(self, payload):
        return self.cipher.encrypt(json.dumps(payload, ensure_ascii=False).encode())

    def _decrypt(self, payload):
        return json.loads(self.cipher.decrypt(payload))

    def _now(self):
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    def _audit(self, actor, action, resource):
        self.db.execute("INSERT INTO audit(actor_id,action,resource_id,occurred_at) VALUES(?,?,?,?)", (actor, action, resource, self._now()))

    def user_count(self):
        return self.db.execute("SELECT count(*) FROM users").fetchone()[0]

    def user(self, user_id):
        row = self.db.execute("SELECT id,username,role FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
        if not row:
            raise PermissionError("La sesión ha caducado o la cuenta no está activa.")
        return dict(row)

    def _admin(self, actor):
        if self.user(actor)["role"] != "admin":
            raise PermissionError("Se requiere una cuenta administradora.")

    def create_user(self, username, password, role="clinician", actor=None, bootstrap=False):
        username = normalize_username(username)
        if role not in ("admin", "clinician"):
            raise ValueError("Rol no válido.")
        encoded = hash_password(password)
        user_id = uuid.uuid4().hex
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if bootstrap:
                if self.user_count() or role != "admin":
                    raise PermissionError("La configuración inicial ya fue completada.")
            else:
                self._admin(actor)
            try:
                self.db.execute("INSERT INTO users(id,username,password_hash,role) VALUES(?,?,?,?)", (user_id, username, encoded, role))
            except sqlite3.IntegrityError:
                raise ValueError("Ese nombre de usuario ya está registrado.") from None
            self._audit(actor or user_id, "user.create", user_id)
        return user_id

    def authenticate(self, username, password):
        username = username.strip().lower()[:100]
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            attempt = self.db.execute("SELECT * FROM login_attempts WHERE username=?", (username,)).fetchone()
            if attempt and attempt["locked_until"] > time.time():
                raise ValueError("Acceso temporalmente bloqueado. Intenta de nuevo en 10 minutos.")
            row = self.db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            # Do equivalent hashing work for unknown accounts to avoid a fast username oracle.
            fallback = "pbkdf2_sha256$600000$" + "00" * 16 + "$" + "00" * 32
            valid = verify_password(password, row["password_hash"] if row else fallback)
            if row and row["active"] and valid:
                self.db.execute("DELETE FROM login_attempts WHERE username=?", (username,))
                self._audit(row["id"], "user.login", row["id"])
                result = dict(row)
            else:
                failures = (attempt["failures"] if attempt and attempt["locked_until"] == 0 else 0) + 1
                locked_until = time.time() + 600 if failures >= 5 else 0
                self.db.execute("INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)", (username, failures, locked_until))
                result = None
        if not result:
            raise ValueError("Usuario o contraseña incorrectos.")
        return {k: result[k] for k in ("id", "username", "role")}

    def list_users(self, actor):
        self._admin(actor)
        return [dict(r) for r in self.db.execute("SELECT id,username,role,active FROM users ORDER BY username")]

    def set_user_active(self, actor, target, active):
        self._admin(actor)
        if actor == target:
            raise ValueError("No puedes desactivar tu propia cuenta.")
        with self.lock, self.db:
            self.db.execute("UPDATE users SET active=? WHERE id=?", (int(active), target))
            self._audit(actor, "user.activate" if active else "user.deactivate", target)

    def change_password(self, actor, old_password, new_password):
        self.user(actor)
        row = self.db.execute("SELECT password_hash FROM users WHERE id=?", (actor,)).fetchone()
        if not verify_password(old_password, row[0]):
            raise ValueError("La contraseña actual no es correcta.")
        encoded = hash_password(new_password)
        with self.lock, self.db:
            self.db.execute("UPDATE users SET password_hash=? WHERE id=?", (encoded, actor))
            self._audit(actor, "user.password", actor)

    def create_patient(self, actor, name, sex="No especificado"):
        self.user(actor)
        name = " ".join(name.split())
        if not 2 <= len(name) <= 100:
            raise ValueError("El nombre o seudónimo debe tener entre 2 y 100 caracteres.")
        if sex not in ("No especificado", "Femenino", "Masculino"):
            raise ValueError("Sexo no válido.")
        patient_id = uuid.uuid4().hex
        with self.lock, self.db:
            self.db.execute("INSERT INTO patients VALUES(?,?,?,?)", (patient_id, actor, self._encrypt({"name": name, "sex": sex}), self._now()))
            self._audit(actor, "patient.create", patient_id)
        return patient_id

    def patients(self, actor):
        self.user(actor)
        rows = self.db.execute("SELECT * FROM patients WHERE owner_id=? ORDER BY created_at", (actor,))
        return [{"id": r["id"], "created_at": r["created_at"], **self._decrypt(r["payload"])} for r in rows]

    def patient(self, actor, patient_id):
        self.user(actor)
        r = self.db.execute("SELECT * FROM patients WHERE id=? AND owner_id=?", (patient_id, actor)).fetchone()
        if not r:
            raise PermissionError("El expediente no está disponible para esta cuenta.")
        return {"id": r["id"], "created_at": r["created_at"], **self._decrypt(r["payload"])}

    def update_patient(self, actor, patient_id, name, sex):
        self.patient(actor, patient_id)
        name = " ".join(name.split())
        if not 2 <= len(name) <= 100 or sex not in ("No especificado", "Femenino", "Masculino"):
            raise ValueError("Revisa el nombre y el sexo del paciente.")
        with self.lock, self.db:
            self.db.execute("UPDATE patients SET payload=? WHERE id=? AND owner_id=?", (self._encrypt({"name": name, "sex": sex}), patient_id, actor))
            self._audit(actor, "patient.update", patient_id)

    def evaluations(self, actor, patient_id=None, include_archived=False):
        self.user(actor)
        if patient_id:
            self.patient(actor, patient_id)
        query = "SELECT e.* FROM evaluations e JOIN patients p ON p.id=e.patient_id WHERE p.owner_id=?"
        args = [actor]
        if patient_id:
            query += " AND e.patient_id=?"
            args.append(patient_id)
        if not include_archived:
            query += " AND e.archived=0"
        query += " ORDER BY e.evaluated_on,e.created_at"
        return [{**{k: r[k] for k in ("id", "patient_id", "evaluated_on", "revision", "archived", "created_at", "updated_at")}, **self._decrypt(r["payload"])} for r in self.db.execute(query, args)]

    def evaluation(self, actor, evaluation_id):
        self.user(actor)
        r = self.db.execute("SELECT e.* FROM evaluations e JOIN patients p ON p.id=e.patient_id WHERE e.id=? AND p.owner_id=?", (evaluation_id, actor)).fetchone()
        if not r:
            raise PermissionError("La evaluación no está disponible para esta cuenta.")
        return {**{k: r[k] for k in ("id", "patient_id", "evaluated_on", "revision", "archived", "created_at", "updated_at")}, **self._decrypt(r["payload"])}

    def save_evaluation(self, actor, patient_id, inputs, evaluation_id=None, revision=None, allow_same_day=False):
        patient = self.patient(actor, patient_id)
        result = calculate(inputs)
        canonical = asdict(inputs)
        # Normalize numeric representations so 110 and 110.0 cannot bypass duplicate checks.
        for k in ("age", "glucose", "triglycerides", "creatinine", "weight", "height"):
            canonical[k] = float(canonical[k])
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
        payload = {"inputs": asdict(inputs), "result": result, "patient_snapshot": {"name": patient["name"], "sex": patient["sex"]}}
        evaluation_id_new = evaluation_id or uuid.uuid4().hex
        with self.lock, self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if evaluation_id:
                previous = self.evaluation(actor, evaluation_id)
                if previous["patient_id"] != patient_id or previous["archived"]:
                    raise ValueError("No se puede editar esta evaluación.")
                if previous["revision"] != revision:
                    raise ValueError("Otra sesión modificó esta evaluación. Vuelve a cargarla.")
            same_day = self.db.execute("SELECT id FROM evaluations WHERE patient_id=? AND evaluated_on=? AND archived=0 AND id<>?", (patient_id, inputs.evaluated_on, evaluation_id_new)).fetchone()
            if same_day and not allow_same_day:
                raise DuplicateEvaluation("Ya existe una evaluación en esa fecha. Confirma que deseas registrar otra.")
            now = self._now()
            try:
                if evaluation_id:
                    self.db.execute("UPDATE evaluations SET evaluated_on=?,payload=?,fingerprint=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?", (inputs.evaluated_on, self._encrypt(payload), fingerprint, now, evaluation_id, revision))
                else:
                    self.db.execute("INSERT INTO evaluations(id,patient_id,evaluated_on,payload,fingerprint,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (evaluation_id_new, patient_id, inputs.evaluated_on, self._encrypt(payload), fingerprint, now, now))
            except sqlite3.IntegrityError:
                raise DuplicateEvaluation("Estos mismos datos ya están guardados para este paciente y fecha.") from None
            self._audit(actor, "evaluation.update" if evaluation_id else "evaluation.create", evaluation_id_new)
        return evaluation_id_new

    def archive(self, actor, evaluation_id, archived, revision):
        self.evaluation(actor, evaluation_id)
        with self.lock, self.db:
            try:
                cursor = self.db.execute("UPDATE evaluations SET archived=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?", (int(archived), self._now(), evaluation_id, revision))
            except sqlite3.IntegrityError:
                raise DuplicateEvaluation("Hay una evaluación idéntica activa. No se puede restaurar este duplicado.") from None
            if not cursor.rowcount:
                raise ValueError("La evaluación cambió. Vuelve a cargarla.")
            self._audit(actor, "evaluation.archive" if archived else "evaluation.restore", evaluation_id)

    def audit(self, actor):
        self._admin(actor)
        return [dict(r) for r in self.db.execute("SELECT actor_id,action,resource_id,occurred_at FROM audit ORDER BY id DESC LIMIT 100")]

    def backup(self, actor):
        self._admin(actor)
        fd, path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        try:
            with self.lock:
                target = sqlite3.connect(path)
                try:
                    self.db.backup(target)
                finally:
                    target.close()
            data = Path(path).read_bytes()
            with self.db:
                self._audit(actor, "database.backup", "database")
            return data
        finally:
            Path(path).unlink(missing_ok=True)
