"""Streamlit entry point. Run with: streamlit run app.py."""
from datetime import date
from html import escape
import hmac
import os
from pathlib import Path
import sys
import time

import altair as alt
import pandas as pd
import streamlit as st

# Permite importar el paquete `renal` aunque la app se ejecute desde otra carpeta.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from renal.demo import make_demo
from renal.domain import COHORT_NOTE, Inputs, light_name, METHOD_NOTE, METHOD_VERSION, STRATA, TYG_CUTOFF, CREATININE_CUTOFF, calculate, precision_note
from renal.reports import csv_bytes, pdf_bytes, safe_cell
from renal.storage import Store
from renal.public_view import render_public, render_sharing
from renal.branding import LOGO_PNG, logo_img
from renal.mailer import SmtpConfig
from renal.semaforo_view import guide, result_card

ROOT = Path(__file__).parent
public_view = st.query_params.get("vista", "publica") != "profesional"
st.set_page_config(page_title="Calcula tu índice TyG · Semáforo Renal" if public_view else "Semáforo Renal · Tabasco", page_icon=str(LOGO_PNG), layout="wide", initial_sidebar_state="collapsed" if public_view else "expanded")
st.markdown(f"<style>{(ROOT / 'assets/theme.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

def setting(name, default=""):
    if name in os.environ:
        return os.environ[name]
    try:
        return str(st.secrets.get(name, default))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default

def navigate(page):
    st.session_state.nav = page
    st.session_state.pop("draft", None)
    st.session_state.pop("edit_id", None)

def reset_form():
    st.session_state.form_generation = st.session_state.get("form_generation", 0) + 1
    st.session_state.pop("draft", None)

def evaluate_patient(patient_id):
    st.session_state.selected_patient = patient_id
    navigate("Nueva evaluación")

def end_session():
    session_store = st.session_state.get("store")
    if session_store:
        session_store.close()
    st.session_state.clear()

def title(text, description):
    st.title(text)
    st.markdown(f'<p class="page-intro">{escape(description)}</p>', unsafe_allow_html=True)

def hero(eyebrow, heading, description, badge="ACOMPAÑAR · OBSERVAR · COMPRENDER"):
    st.markdown(f'<section class="hero"><div class="eyebrow">{escape(eyebrow)}</div><h1>{escape(heading)}</h1><p>{escape(description)}</p><span class="hero-badge">{escape(badge)}</span></section>', unsafe_allow_html=True)

def stat(label, value, foot, color):
    st.markdown(f'<div class="stat-card" style="--accent:{color}"><div class="label">{escape(str(label))}</div><div class="value">{escape(str(value))}</div><div class="foot">{escape(str(foot))}</div></div>', unsafe_allow_html=True)

def patient_label(patient):
    return f'{patient["name"]} · {patient["id"][:8].upper()}'

def choose_patient(patients, key):
    if not patients:
        st.info("Primero crea un expediente en Pacientes para registrar una evaluación.")
        st.button("Crear primer paciente", on_click=navigate, args=("Pacientes",), key=f"empty_{key}")
        return None
    mapping = {p["id"]: p for p in patients}
    current = st.session_state.get("selected_patient")
    ids = list(mapping)
    selected = st.selectbox("Expediente del paciente", ids, format_func=lambda pid: patient_label(mapping[pid]), index=ids.index(current) if current in ids else 0, key=key)
    return mapping[selected]

def patient_header(patient):
    st.markdown(f'<div class="patient-header"><div class="eyebrow">EXPEDIENTE {patient["id"][:8].upper()}</div><h2>{escape(patient["name"])}</h2><p>{escape(patient["sex"])} · Identificador único: {patient["id"]}</p></div>', unsafe_allow_html=True)

def result_panel(record, previous=None):
    r, i = record["result"], record["inputs"]
    s = STRATA[r["stratum"]]
    metrics = f'<div class="tl-metrics"><span>TyG <b>{r["tyg"]:.2f}</b></span><span>Creatinina <b>{i["creatinine"]:g}</b> mg/dL</span></div>'
    st.markdown(result_card(list(STRATA.items()), r["stratum"], f'FENOTIPO {s["symbol"]}', metrics), unsafe_allow_html=True)
    st.markdown(f'**Acción sugerida para el equipo clínico:** {s["clinical_action"]}')
    with st.expander("Orientación para compartir con el paciente: riesgos, qué hacer y lecturas"):
        guide(s)
    with st.container(key="result-metrics"):
        cols = st.columns(3)
        metrics = [("Índice TyG", r["tyg"], 3, None, "tyg"), ("Creatinina prediálisis", i["creatinine"], 2, "mg/dL", "creatinine"), ("IMC", r["bmi"], 1, "kg/m²", "bmi")]
        for column, (label, value, decimals, unit, field) in zip(cols, metrics):
            delta = None
            if previous and previous["result"]["method_version"] == r["method_version"]:
                previous_value = previous["inputs"]["creatinine"] if field == "creatinine" else previous["result"][field]
                delta = f"{value-previous_value:+.{decimals}f} vs. evaluación anterior"
            column.metric(label, f'{value:.{decimals}f}' + (f" {unit}" if unit else ""), delta, delta_color="off", help="La diferencia indica un cambio numérico; no determina una mejoría clínica.")
    st.caption(f'Cortes de esta evaluación: TyG {r["tyg_cutoff"]} · Creatinina {r["creatinine_cutoff"]} mg/dL · Método {r["method_version"]}')
    st.caption(precision_note(r["tyg"], r["tyg_cutoff"], 3))
    st.caption(precision_note(i["creatinine"], r["creatinine_cutoff"], 2))
    with st.expander("Datos utilizados y detalle del cálculo"):
        st.text(f'Fecha: {record["evaluated_on"]} · Paciente: {record["patient_snapshot"]["name"]} · Edad: {i["age"]} años')
        st.write(f'Glucosa: {i["glucose"]:g} mg/dL · Triglicéridos: {i["triglycerides"]:g} mg/dL · Creatinina: {i["creatinine"]:g} mg/dL')
        st.write(f'Peso postdiálisis: {i["weight"]:g} kg · Talla: {i["height"]:g} cm')
        st.latex(r"TyG=\ln\left(\frac{Triglicéridos\times Glucosa}{2}\right)")
        st.write(f'ln(({i["triglycerides"]:g} × {i["glucose"]:g}) / 2) = {r["tyg"]:.6f}')
        st.latex(r"IMC=\frac{Peso\ (kg)}{Talla\ (m)^2}")
        st.write(f'{i["weight"]:g} / ({i["height"]/100:g}²) = {r["bmi"]:.3f} kg/m²')

def download_report(record, key):
    st.download_button("Descargar reporte PDF", pdf_bytes(record), file_name=f'evaluacion_{record["id"][:12]}.pdf', mime="application/pdf", key=key, width='stretch')

def evaluation_table(evaluations, patients):
    names = {p["id"]: p["name"] for p in patients}
    return pd.DataFrame([{"Fecha": e["evaluated_on"], "Paciente": safe_cell(names.get(e["patient_id"], e["patient_snapshot"]["name"])), "Expediente": e["patient_id"][:8].upper(), "TyG": round(e["result"]["tyg"], 3), "Creatinina (mg/dL)": e["inputs"]["creatinine"], "IMC (kg/m²)": round(e["result"]["bmi"], 1), "Patrón": STRATA[e["result"]["stratum"]]["title"], "Registro": "Archivado" if e["archived"] else "Activo"} for e in reversed(evaluations)])

def evaluation_form(store, user, patient, existing=None):
    context = existing["id"] if existing else "new"
    nonce = st.session_state.get("form_generation", 0)
    prefix = f"{context}_{patient['id']}_{nonce}"
    old = existing["inputs"] if existing else {}
    old = {key: float(value) if key in ("glucose", "triglycerides", "creatinine", "weight", "height") else value for key, value in old.items()}
    st.caption("Unidades: glucosa, triglicéridos y creatinina en mg/dL; peso en kg; talla en cm.")
    if not existing:
        if st.button("Cargar valores de ejemplo", key=f"sample_{prefix}"):
            sample = {"age": 50, "glucose": 110.0, "triglycerides": 180.0, "creatinine": 7.2, "weight": 68.0, "height": 160.0}
            for k, value in sample.items():
                st.session_state[f"{prefix}_{k}"] = value
            st.session_state[f"{prefix}_is_example"] = True
            st.session_state.pop("draft", None)
        if st.session_state.get(f"{prefix}_is_example"):
            st.warning("Se cargaron valores ficticios. Sustitúyelos por los datos de la evaluación antes de guardar.")
    with st.form(f"evaluation_{prefix}"):
        st.subheader("1. Datos de la evaluación")
        left, right = st.columns(2)
        age = left.number_input("Edad (años) *", min_value=1, max_value=120, value=old.get("age"), step=1, placeholder="Edad al momento de evaluar", key=f"{prefix}_age")
        evaluated_on = right.date_input("Fecha de evaluación *", value=date.fromisoformat(old["evaluated_on"]) if old else date.today(), max_value=date.today(), min_value=date(1900, 1, 1), key=f"{prefix}_date")
        st.subheader("2. Laboratorio")
        left, right = st.columns(2)
        glucose = left.number_input("Glucosa en ayunas (mg/dL) *", 1.0, 1000.0, value=old.get("glucose"), step=1.0, placeholder="Ej. 110", key=f"{prefix}_glucose")
        tg = right.number_input("Triglicéridos (mg/dL) *", 1.0, 3000.0, value=old.get("triglycerides"), step=1.0, placeholder="Ej. 180", key=f"{prefix}_triglycerides")
        creatinine = left.number_input("Creatinina prediálisis (mg/dL) *", .1, 50.0, value=old.get("creatinine"), step=.1, format="%.2f", placeholder="Ej. 7.2", key=f"{prefix}_creatinine")
        st.subheader("3. Antropometría")
        left, right = st.columns(2)
        weight = left.number_input("Peso postdiálisis (kg) *", 1.0, 400.0, value=old.get("weight"), step=.1, placeholder="Ej. 68", key=f"{prefix}_weight")
        height = right.number_input("Talla (cm) *", 50.0, 250.0, value=old.get("height"), step=.1, placeholder="Ej. 160", key=f"{prefix}_height")
        verified = st.checkbox("Verifiqué los valores, las unidades y que las muestras corresponden a esta evaluación.", key=f"{prefix}_verified")
        submitted = st.form_submit_button("Calcular vista previa", type="primary", width='stretch')
    values = dict(age=age, glucose=glucose, triglycerides=tg, creatinine=creatinine, weight=weight, height=height, evaluated_on=evaluated_on.isoformat())
    draft = st.session_state.get("draft")
    if draft and (draft["context"] != prefix or draft["inputs"] != values or not verified):
        st.session_state.pop("draft", None)
    if submitted:
        st.session_state.pop("draft", None)
        try:
            if not verified:
                raise ValueError("Confirma la revisión de los datos antes de calcular.")
            inputs = Inputs(**values)
            result = calculate(inputs)
            st.session_state.draft = {"context": prefix, "inputs": values, "result": result, "revision": existing["revision"] if existing else None, "patient_snapshot": {"name": patient["name"], "sex": patient["sex"]}, "evaluated_on": values["evaluated_on"]}
        except ValueError as exc:
            st.error(str(exc))
    draft = st.session_state.get("draft")
    if draft and draft["context"] == prefix:
        st.subheader("Vista previa · pendiente de guardar")
        st.caption("Este resultado corresponde a los datos enviados al calcular. Si modificas el formulario, vuelve a calcular antes de guardar.")
        result_panel(draft)
        st.info(METHOD_NOTE)
        same_day = [e for e in store.evaluations(user["id"], patient["id"]) if e["evaluated_on"] == draft["evaluated_on"] and e["id"] != context]
        allow = False
        if same_day:
            st.warning("Ya hay una evaluación de este paciente en esta fecha.")
            allow = st.checkbox("Confirmo que esta es otra evaluación de la misma fecha.", key=f"same_day_{prefix}")
        if st.button("Confirmar y guardar cambios" if existing else "Confirmar y guardar evaluación", type="primary", key=f"save_{prefix}", width='stretch'):
            try:
                eid = store.save_evaluation(user["id"], patient["id"], Inputs(**draft["inputs"]), evaluation_id=existing["id"] if existing else None, revision=draft["revision"], allow_same_day=allow)
                st.session_state.saved_evaluation = eid
                st.session_state.flash = "Evaluación guardada correctamente."
                reset_form()
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))

def chart(evaluations, field, label, color, cutoff_key=None):
    rows = [{"Fecha": e["evaluated_on"], "Valor": e["inputs"]["creatinine"] if field == "creatinine" else e["result"][field], "Evaluación": e["id"][:8], "Método": e["result"]["method_version"], "Orden": e["created_at"], "Corte": e["result"][cutoff_key] if cutoff_key else None} for e in evaluations]
    df = pd.DataFrame(rows)
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    base = alt.Chart(df).encode(x=alt.X("Fecha:T", title="Fecha de evaluación", axis=alt.Axis(format="%d/%m/%Y")), y=alt.Y("Valor:Q", title=label, scale=alt.Scale(zero=False)), tooltip=[alt.Tooltip("Fecha:T", format="%d/%m/%Y"), alt.Tooltip("Valor:Q", format=".4f"), "Evaluación:N", "Método:N"])
    line = base.mark_line(color=color, strokeWidth=3).encode(order=alt.Order("Orden:N"))
    points = base.mark_circle(color=color, size=85, opacity=1)
    layers = line + points
    if cutoff_key:
        rule = alt.Chart(df).mark_rule(color="#8A98A8", strokeDash=[6, 4]).encode(y="Corte:Q", tooltip=[alt.Tooltip("Corte:Q", title="Corte de la cohorte")])
        layers = layers + rule
    st.altair_chart(layers.properties(height=230).configure_view(stroke=None), width='stretch')

def login_screen(store):
    hero("SEMÁFORO RENAL · TABASCO", "Un espacio para el seguimiento integral.", "Organiza evaluaciones y explora la evolución metabólico-muscular con una mirada más clara.", "ACCESO A TU ESPACIO DE TRABAJO")
    left, right = st.columns([1, 1])
    with left:
        if store.user_count() == 0:
            st.subheader("Configura la primera cuenta")
            token = setting("RENAL_SETUP_TOKEN")
            if not token:
                st.error("Configura RENAL_SETUP_TOKEN en el servidor para habilitar el alta del administrador inicial.")
                st.stop()
            with st.form("bootstrap"):
                entered = st.text_input("Token de configuración", type="password")
                username = st.text_input("Usuario administrador")
                password = st.text_input("Contraseña (mínimo 12 caracteres)", type="password")
                confirmation = st.text_input("Repetir contraseña", type="password")
                create = st.form_submit_button("Crear cuenta administradora", type="primary")
            if create:
                try:
                    if not hmac.compare_digest(entered, token):
                        raise ValueError("Token de configuración incorrecto.")
                    if password != confirmation:
                        raise ValueError("Las contraseñas no coinciden.")
                    store.create_user(username, password, role="admin", bootstrap=True)
                    st.success("Cuenta creada. Ya puedes iniciar sesión.")
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
        else:
            with st.form("login"):
                st.subheader("Iniciar sesión")
                username = st.text_input("Usuario", autocomplete="username")
                password = st.text_input("Contraseña", type="password", autocomplete="current-password")
                submit = st.form_submit_button("Entrar a mi espacio", type="primary", width='stretch')
            if submit:
                try:
                    st.session_state.user = store.authenticate(username, password)
                    st.session_state.last_activity = time.time()
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    with right:
        st.info("Cada cuenta accede a sus propios expedientes. La información de pacientes y sus evaluaciones se guarda cifrada.")
        st.caption(METHOD_NOTE)
    st.stop()

if public_view:
    render_public(SmtpConfig.from_settings(setting))
    st.stop()

mode = setting("RENAL_MODE", "demo").strip().lower()
if mode not in ("demo", "clinical"):
    st.error("RENAL_MODE debe ser demo o clinical.")
    st.stop()
demo = mode == "demo"
if demo:
    if "store" not in st.session_state:
        st.session_state.store, st.session_state.user = make_demo()
    store, user = st.session_state.store, st.session_state.user
else:
    key = setting("RENAL_DB_KEY")
    if not key:
        st.error("El modo persistente requiere configurar RENAL_DB_KEY. Consulta la guía de instalación.")
        st.stop()
    if "store" not in st.session_state:
        try:
            st.session_state.store = Store(setting("RENAL_DB_PATH", str(ROOT / "data/renal.sqlite")), key)
        except (ValueError, OSError) as exc:
            st.error(f"No se pudo abrir el almacenamiento: {exc}")
            st.stop()
    store = st.session_state.store
    if "user" not in st.session_state:
        login_screen(store)
    if time.time() - st.session_state.get("last_activity", 0) > 1800:
        end_session()
        st.rerun()
    try:
        user = store.user(st.session_state.user["id"])
    except PermissionError:
        end_session()
        st.rerun()
    st.session_state.last_activity = time.time()

with st.sidebar:
    st.markdown(f'<div class="sidebar-brand">{logo_img()}<div><div class="brand-name">Semáforo Renal</div><div class="eyebrow">TABASCO · UJAT <span class="brand-lights"><i></i><i></i><i></i></span></div></div></div>', unsafe_allow_html=True)
    pages = ["Inicio", "Nueva evaluación", "Pacientes", "Seguimiento", "Historial", "Compartir calculadora", "Metodología", "Mi cuenta"]
    if user["role"] == "admin":
        pages.append("Administración")
    page = st.radio("ESPACIO DE TRABAJO", pages, key="nav")
    st.divider()
    st.link_button("Abrir calculadora pública", "?vista=publica", width="stretch")
    st.markdown(f'<div class="sidebar-note"><strong>{"Demostración interactiva" if demo else "Espacio privado"}</strong><br>{"Datos ficticios · cambios temporales" if demo else "Expedientes persistentes · datos cifrados"}<br>Usuario: {escape(user["username"])}</div>', unsafe_allow_html=True)
    if demo:
        st.caption("Explora el prototipo con datos ficticios. El contenido se reinicia al terminar esta sesión.")
        st.button("Reiniciar demostración", width='stretch', on_click=end_session)
    else:
        st.button("Cerrar sesión", width='stretch', on_click=end_session)
    st.caption(f"Método {METHOD_VERSION} · Aplicación 2.0")

if st.session_state.pop("flash", None):
    st.success("Evaluación guardada correctamente.")
if demo:
    st.caption("MODO DEMOSTRACIÓN · Usa únicamente datos ficticios. Los expedientes mostrados son ejemplos.")
patients = store.patients(user["id"])
evaluations = store.evaluations(user["id"])

if page == "Inicio":
    hero("OBSERVATORIO METABÓLICO-MUSCULAR", "Cada evaluación cuenta una historia.", "Reúne los datos de tus pacientes, identifica patrones de la cohorte y acompaña su evolución desde un mismo lugar.")
    st.markdown('<div class="section-label">TU ESPACIO, DE UN VISTAZO</div>', unsafe_allow_html=True)
    latest = {}
    for e in evaluations:
        latest[e["patient_id"]] = e
    with st.container(key="kpi-row"):
        cols = st.columns(4)
        cards = [("Pacientes", len(patients), "Expedientes en tu espacio", "#087F8C"), ("Evaluaciones", len(evaluations), "Registros activos", "#6850AD"), ("Seguimientos", sum(sum(x["patient_id"] == p["id"] for x in evaluations) > 1 for p in patients), "Pacientes con más de una evaluación", "#CC6A35"), ("Último registro", date.fromisoformat(evaluations[-1]["evaluated_on"]).strftime("%d %b") if evaluations else "—", "Fecha de evaluación más reciente", "#B43750")]
        for col, args in zip(cols, cards):
            with col:
                stat(*args)
    a, b = st.columns([2, 1])
    a.subheader("Evaluaciones recientes")
    b.button("+ Nueva evaluación", type="primary", on_click=navigate, args=("Nueva evaluación",), width='stretch')
    if evaluations:
        st.dataframe(evaluation_table(evaluations[-5:], patients), hide_index=True, width='stretch')
    else:
        st.info("Tu espacio está listo. Crea un paciente y registra su primera evaluación.")
    st.subheader("Una lectura orientada por patrones")
    st.caption("Distribución según la última evaluación activa de cada paciente. Las categorías no son diagnósticos.")
    for col, (code, s) in zip(st.columns(4), STRATA.items()):
        count = sum(e["result"]["stratum"] == code for e in latest.values())
        col.markdown(f'<div class="stratum-card" style="--accent:{s["color"]};--tint:{s["background"]}"><span class="number">{s["symbol"]} · {count} pacientes</span><h4>{escape(s["title"])}</h4><p>{escape(s["label"])}</p></div>', unsafe_allow_html=True)
    st.info(METHOD_NOTE)

elif page == "Pacientes":
    title("Pacientes", "Un expediente único para cada persona, incluso cuando dos pacientes comparten nombre.")
    with st.expander("+ Crear expediente", expanded=not patients):
        with st.form("new_patient", clear_on_submit=True):
            name = st.text_input("Nombre o seudónimo *", max_chars=100, placeholder="Identificación del paciente")
            sex = st.selectbox("Sexo", ["No especificado", "Femenino", "Masculino"])
            create = st.form_submit_button("Crear expediente", type="primary")
        if create:
            try:
                pid = store.create_patient(user["id"], name, sex)
                st.session_state.selected_patient = pid
                st.success(f"Expediente creado: {pid[:8].upper()}")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    search = st.text_input("Buscar por nombre o identificador", placeholder="Escribe para encontrar un expediente")
    filtered = [p for p in patients if search.casefold() in (p["name"] + " " + p["id"]).casefold()]
    if not filtered and patients:
        st.info("No hay pacientes que coincidan con la búsqueda.")
    elif filtered:
        patient = choose_patient(filtered, "patients_select")
        patient_header(patient)
        n = sum(e["patient_id"] == patient["id"] for e in evaluations)
        st.write(f"**{n} evaluaciones activas** en este expediente.")
        st.button("Registrar evaluación para este paciente", type="primary", on_click=evaluate_patient, args=(patient["id"],))
        with st.expander("Editar identificación"):
            with st.form(f'patient_edit_{patient["id"]}'):
                name = st.text_input("Nombre o seudónimo", value=patient["name"], max_chars=100)
                sexes = ["No especificado", "Femenino", "Masculino"]
                sex = st.selectbox("Sexo del paciente", sexes, index=sexes.index(patient["sex"]))
                update = st.form_submit_button("Guardar identificación")
            if update:
                try:
                    store.update_patient(user["id"], patient["id"], name, sex)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.caption("Los reportes de evaluaciones anteriores conservan la identificación registrada al guardarlas.")

elif page == "Nueva evaluación":
    title("Nueva evaluación", "Captura los datos, revisa el resultado y confirma el guardado cuando todo esté correcto.")
    patient = choose_patient(patients, "evaluation_patient")
    if patient:
        patient_header(patient)
        st.button("Vaciar formulario", on_click=reset_form)
        evaluation_form(store, user, patient)
        saved = st.session_state.get("saved_evaluation")
        if saved:
            record = store.evaluation(user["id"], saved)
            if record["patient_id"] == patient["id"]:
                st.subheader("Última evaluación guardada")
                st.caption(f'Registro {record["id"][:8].upper()} · {record["evaluated_on"]}')
                result_panel(record)
                download_report(record, "new_pdf")

elif page == "Seguimiento":
    title("Seguimiento", "Explora los cambios de cada paciente y compara sus evaluaciones a lo largo del tiempo.")
    patient = choose_patient(patients, "follow_patient")
    if patient:
        patient_header(patient)
        records = store.evaluations(user["id"], patient["id"])
        if not records:
            st.info("Este paciente todavía no tiene evaluaciones activas.")
        else:
            dates = [date.fromisoformat(e["evaluated_on"]) for e in records]
            left, right = st.columns(2)
            start = left.date_input("Desde", min(dates), key="follow_start")
            end = right.date_input("Hasta", max(dates), key="follow_end")
            selected = [e for e in records if start.isoformat() <= e["evaluated_on"] <= end.isoformat()]
            if start > end:
                st.error("La fecha de inicio debe ser anterior o igual a la fecha final.")
            elif not selected:
                st.info("No hay evaluaciones en el periodo seleccionado.")
            else:
                result_panel(selected[-1], selected[-2] if len(selected) > 1 else None)
                if len(selected) == 1:
                    st.info("Hay una evaluación en este periodo. Registra otra para observar una tendencia.")
                st.subheader("Evolución del índice TyG")
                chart(selected, "tyg", "Índice TyG", "#087F8C", "tyg_cutoff")
                st.subheader("Creatinina prediálisis")
                chart(selected, "creatinine", "Creatinina (mg/dL)", "#6850AD", "creatinine_cutoff")
                st.subheader("Evolución del IMC")
                chart(selected, "bmi", "IMC (kg/m²)", "#CC6A35")
                st.caption("Línea discontinua: corte de la cohorte. Cada punto corresponde a una evaluación; los registros de la misma fecha pueden superponerse. Un aumento o descenso no determina por sí solo una mejoría clínica.")
                download_report(selected[-1], "follow_pdf")
                st.download_button("Exportar seguimiento completo CSV", csv_bytes(selected), file_name=f'seguimiento_{patient["id"][:8]}.csv', mime="text/csv")

elif page == "Historial":
    title("Historial de evaluaciones", "Consulta, corrige y exporta registros. Puedes archivar una evaluación y restaurarla después.")
    options = {"all": "Todos los pacientes", **{p["id"]: patient_label(p) for p in patients}}
    left, right = st.columns([2, 1])
    selected = left.selectbox("Filtrar por paciente", list(options), format_func=options.get, key="history_patient")
    archived = right.checkbox("Incluir archivadas")
    records = store.evaluations(user["id"], None if selected == "all" else selected, include_archived=archived)
    if not records:
        st.info("No hay evaluaciones para estos filtros.")
    else:
        st.dataframe(evaluation_table(records, patients), hide_index=True, width='stretch')
        st.download_button("Exportar datos completos CSV", csv_bytes(records), file_name="evaluaciones_renales.csv", mime="text/csv", width='stretch')
        mapping = {e["id"]: e for e in reversed(records)}
        eid = st.selectbox("Abrir una evaluación", list(mapping), format_func=lambda key: f'{mapping[key]["evaluated_on"]} · {mapping[key]["patient_snapshot"]["name"]} · {key[:8].upper()}', key="history_record")
        record = mapping[eid]
        st.caption(f'Revisión {record["revision"]} · Método {record["result"]["method_version"]}')
        result_panel(record)
        download_report(record, "history_pdf")
        if not record["archived"]:
            with st.expander("Corregir esta evaluación"):
                st.caption("La corrección recalcula los indicadores con el método actual y aumenta la revisión del registro.")
                evaluation_form(store, user, store.patient(user["id"], record["patient_id"]), existing=record)
        with st.expander("Restaurar registro" if record["archived"] else "Archivar registro"):
            confirmed = st.checkbox("Confirmo que quiero restaurar esta evaluación." if record["archived"] else "Confirmo que quiero archivar esta evaluación. Podré restaurarla desde el historial.", key=f"archive_confirm_{eid}")
            if st.button("Restaurar evaluación" if record["archived"] else "Archivar evaluación", disabled=not confirmed):
                try:
                    store.archive(user["id"], eid, not record["archived"], record["revision"])
                    st.session_state.pop("draft", None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

elif page == "Compartir calculadora":
    render_sharing(setting("RENAL_PUBLIC_URL"))

elif page == "Metodología":
    title("Metodología y alcance", "Conoce qué calcula la herramienta y cómo interpretar sus límites.")
    st.warning(METHOD_NOTE)
    st.subheader("Método de la cohorte")
    st.write(f"**Versión:** {METHOD_VERSION} · **Corte TyG:** {TYG_CUTOFF} · **Corte creatinina:** {CREATININE_CUTOFF} mg/dL")
    st.latex(r"TyG=\ln\left(\frac{Triglicéridos\ (mg/dL)\times Glucosa\ (mg/dL)}{2}\right)")
    st.latex(r"IMC=\frac{Peso\ postdiálisis\ (kg)}{Talla\ (m)^2}")
    st.write("Los valores iguales al corte se incluyen en el grupo superior. Los cálculos utilizan todos los decimales; el redondeo solo afecta a la presentación.")
    st.subheader("Semáforo Renal: cuatro fenotipos")
    for s in STRATA.values():
        st.markdown(f'<div class="tl-chip on" style="--lamp:{s["color"]}"><i></i>Luz {light_name(s)} · {s["symbol"]}. {escape(s["title"])}</div>', unsafe_allow_html=True)
        st.write(f'{s["detail"]} **Acción sugerida:** {s["clinical_action"]}')
    st.subheader("Cohorte de referencia")
    st.write(COHORT_NOTE + " Diseño observacional, transversal y analítico. Se excluyeron pacientes con hospitalización por evento agudo en los últimos tres meses, enfermedades consuntivas activas, amputación mayor o función renal residual significativa. Las muestras se tomaron antes de la sesión intermedia semanal, con ayuno mínimo de ocho horas.")
    st.write("Pendiente: validación externa en otras unidades de hemodiálisis antes de sostener afirmaciones de validez clínica.")
    st.subheader("Registro y trazabilidad")
    st.write("Cada evaluación guarda valores originales, identificación al momento del registro, versión del método, cortes aplicados, revisión y marcas de tiempo. El CSV exporta todos esos campos. El modo persistente registra las acciones de creación, corrección, archivo y restauración.")

elif page == "Mi cuenta":
    title("Mi cuenta", "Gestiona el acceso a tu espacio de trabajo.")
    st.write(f'**Usuario:** {user["username"]} · **Rol:** {"Administrador" if user["role"] == "admin" else "Clínico"}')
    if demo:
        st.info("La cuenta de demostración es temporal. El cambio de contraseña está disponible en el modo persistente.")
    else:
        with st.form("change_password"):
            old = st.text_input("Contraseña actual", type="password")
            new = st.text_input("Nueva contraseña (mínimo 12 caracteres)", type="password")
            confirm = st.text_input("Repetir nueva contraseña", type="password")
            submit = st.form_submit_button("Actualizar contraseña", type="primary")
        if submit:
            try:
                if new != confirm:
                    raise ValueError("Las contraseñas no coinciden.")
                store.change_password(user["id"], old, new)
                st.success("Contraseña actualizada.")
            except ValueError as exc:
                st.error(str(exc))

elif page == "Administración":
    title("Administración", "Gestiona cuentas, respalda el almacenamiento y consulta la actividad del sistema.")
    st.info("El rol administrador gestiona cuentas y respaldos. Los expedientes permanecen separados por cuenta; el respaldo incluye toda la base de datos y debe custodiarse de forma segura.")
    if demo:
        st.caption("En esta demostración puedes explorar la creación de cuentas. Los cambios no son persistentes.")
    with st.expander("Crear cuenta"):
        with st.form("create_user"):
            username = st.text_input("Nuevo usuario")
            password = st.text_input("Contraseña inicial (mínimo 12 caracteres)", type="password")
            role = st.selectbox("Rol de la cuenta", ["clinician", "admin"], format_func=lambda x: "Clínico" if x == "clinician" else "Administrador")
            submit = st.form_submit_button("Crear cuenta")
        if submit:
            try:
                store.create_user(username, password, role=role, actor=user["id"])
                st.success("Cuenta creada.")
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))
    users = store.list_users(user["id"])
    st.dataframe(pd.DataFrame([{ "Usuario": u["username"], "Rol": u["role"], "Activa": bool(u["active"])} for u in users]), hide_index=True, width='stretch')
    others = {u["id"]: u for u in users if u["id"] != user["id"]}
    if others:
        target = st.selectbox("Cuenta a gestionar", list(others), format_func=lambda k: others[k]["username"])
        confirmed = st.checkbox("Confirmo el cambio de acceso de esta cuenta.")
        if st.button("Desactivar cuenta" if others[target]["active"] else "Reactivar cuenta", disabled=not confirmed):
            store.set_user_active(user["id"], target, not others[target]["active"])
            st.rerun()
    st.subheader("Respaldo del almacenamiento")
    st.caption("El archivo contiene las cuentas y los datos cifrados. Conserva la clave de cifrado por separado; sin ella no se puede recuperar la información.")
    if st.button("Preparar respaldo"):
        st.session_state.backup = store.backup(user["id"])
    if "backup" in st.session_state:
        st.download_button("Descargar respaldo", st.session_state.backup, file_name=f'renal_respaldo_{date.today().isoformat()}.sqlite', mime="application/octet-stream")
    st.subheader("Actividad reciente")
    st.dataframe(pd.DataFrame(store.audit(user["id"])), hide_index=True, width='stretch')

st.markdown('<div class="footer"><strong>Semáforo Renal Tabasco</strong> · Proyecto académico UJAT<br>Seguimiento metabólico-muscular en hemodiálisis · Los patrones de la cohorte requieren interpretación clínica individual.</div>', unsafe_allow_html=True)
