"""Anonymous public calculator. Does not initialize or access the patient database."""
import smtplib
import streamlit as st
from renal.domain import COHORT_NOTE, CREATININE_CUTOFF, STRATA, TYG_BANDS, TYG_CUTOFF, TYG_GENERAL_NOTE, calculate_tyg, classify, tyg_band
from renal.semaforo_view import guide, result_card, summary_text
from renal.branding import logo_img
from renal.mailer import MAX_SENDS_PER_SESSION, mailto_link, send_result, valid_email
from renal.sharing import public_calculator_url, qr_png

PUBLIC_NOTE = "Este resultado es informativo. Por sí solo no diagnostica una enfermedad ni indica un tratamiento. Revísalo con un profesional de salud junto con tus estudios y antecedentes."
TYG_REFERENCE = "https://pubmed.ncbi.nlm.nih.gov/31687367/"
MODES = {"Sí, estoy en hemodiálisis": "hd", "No": "general"}

def result_items(result):
    items = list((STRATA if result["inputs"]["mode"] == "hd" else TYG_BANDS).items())
    return items, dict(items)[result["light"]]

def clear_public_inputs():
    for key in list(st.session_state):
        if key.startswith("public_") and key != "public_generation":
            del st.session_state[key]
    st.session_state.public_generation = st.session_state.get("public_generation", 0) + 1

def result_text(result, info):
    i = result["inputs"]
    lines = ["Semáforo Renal Tabasco · Tu resultado", "", f"Índice TyG: {result['tyg']:.4f}",
             f"Glucosa en ayunas: {i['glucose']:g} mg/dL", f"Triglicéridos en ayunas: {i['triglycerides']:g} mg/dL"]
    if i["mode"] == "hd":
        lines.append(f"Creatinina prediálisis: {i['creatinine']:g} mg/dL")
    lines += ["Fórmula: ln((triglicéridos × glucosa) / 2)", "", summary_text(info), "",
              PUBLIC_NOTE, "", "Proyecto académico UJAT · Semáforo Renal Tabasco"]
    return "\n".join(lines) + "\n"

def email_section(summary, generation, smtp):
    """Envía el resultado al correo de la persona. La dirección no se guarda."""
    with st.container(key="public-email"):
        st.markdown("#### ✉️ Enviar a mi correo")
        email = st.text_input("Tu correo electrónico (opcional)", key=f"public_email_{generation}", placeholder="nombre@correo.com",
                              help="Solo se usa para enviarte este resultado. No se guarda ni se agrega a ningún expediente.")
        if smtp is None:
            st.link_button("Enviar a mi correo", mailto_link(email, summary), width="stretch")
            st.caption("Se abrirá tu aplicación de correo con el resultado ya escrito; solo revisa el destinatario y pulsa Enviar.")
            return
        if st.button("Enviar a mi correo", key=f"public_send_{generation}", width="stretch"):
            sends = st.session_state.get("mail_sends", 0)
            if not valid_email(email):
                st.error("Escribe un correo válido, por ejemplo nombre@correo.com.")
            elif sends >= MAX_SENDS_PER_SESSION:
                st.warning("Ya enviaste varios correos en esta sesión. Descarga tu resultado o inténtalo más tarde.")
            else:
                try:
                    with st.spinner("Enviando…"):
                        send_result(smtp, email, summary)
                except (smtplib.SMTPException, OSError):
                    st.error("No pudimos enviar el correo en este momento. Descarga tu resultado con el botón de arriba.")
                else:
                    st.session_state.mail_sends = sends + 1
                    st.success(f"Listo. Enviamos tu resultado a {email.strip()}. Revisa también la carpeta de spam.")

def render_public(smtp=None):
    st.markdown("""<style>
    [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
    .block-container{max-width:1080px;padding-top:3rem!important}
    header[data-testid="stHeader"]{background:transparent}
    </style>""", unsafe_allow_html=True)
    with st.container(key="public-page"):
        st.markdown(f'<div class="public-topbar"><div class="public-brand">{logo_img()}<span><strong>Semáforo Renal</strong><small>TABASCO · UJAT</small></span></div><a href="?vista=profesional" target="_self">Acceso profesional ↗</a></div>', unsafe_allow_html=True)
        st.markdown('<section class="public-hero"><span class="public-pill">PARA TI · SIN REGISTRO</span><h1>Tu <span>Semáforo Renal.</span></h1><p>Con tus estudios de glucosa, triglicéridos y creatinina te mostramos, en colores, cómo está tu perfil metabólico y muscular, qué puede implicar y qué puedes hacer.</p><div class="public-trust"><span>🔒 Sin nombre ni cuenta</span><span>🗂️ No se guarda en expedientes</span><span>⏱️ Menos de un minuto</span></div></section>', unsafe_allow_html=True)
        generation = st.session_state.get("public_generation", 0)
        left, right = st.columns([1.05, 1], gap="large")
        with left:
            st.markdown('<div class="public-step">01 · CUÉNTANOS UN POCO</div>', unsafe_allow_html=True)
            mode_label = st.radio("¿Recibes tratamiento de hemodiálisis?", list(MODES), key=f"public_mode_{generation}", horizontal=True,
                                  help="Con hemodiálisis se usa el Semáforo Renal de 4 luces (TyG + creatinina). Sin hemodiálisis se muestra un semáforo orientativo solo con el TyG.")
            hd = MODES[mode_label] == "hd"
            with st.form(f"public_calculator_{generation}"):
                st.markdown('<div class="public-step">02 · TUS RESULTADOS DE LABORATORIO</div>', unsafe_allow_html=True)
                st.subheader("Vamos a calcularlo")
                st.write(f"Busca estos {'tres' if hd else 'dos'} valores en tus estudios. Todos deben estar en **mg/dL**.")
                glucose = st.number_input("Glucosa en ayunas (mg/dL)", min_value=1., max_value=1000., value=None, step=.1, placeholder="Escribe el valor de glucosa", key=f"public_glucose_{generation}", help="Puede aparecer como glucosa o glucemia en el reporte de laboratorio.")
                tg = st.number_input("Triglicéridos en ayunas (mg/dL)", min_value=1., max_value=3000., value=None, step=.1, placeholder="Escribe el valor de triglicéridos", key=f"public_tg_{generation}", help="Usa el resultado de triglicéridos, no el de colesterol.")
                creatinine = None
                if hd:
                    creatinine = st.number_input("Creatinina antes de la diálisis (mg/dL)", min_value=.1, max_value=50., value=None, step=.1, placeholder="Escribe el valor de creatinina", key=f"public_creat_{generation}", help="Es la creatinina de la muestra tomada antes de conectarte a la sesión de hemodiálisis.")
                fasting = st.checkbox("Confirmo que los resultados son en ayunas y están en mg/dL.", key=f"public_confirm_{generation}")
                submitted = st.form_submit_button("Ver mi semáforo", type="primary", width="stretch")
            st.caption("¿Tus estudios usan otras unidades o no sabes si fueron en ayunas? Confírmalo con tu laboratorio antes de calcular.")
        current = {"mode": "hd" if hd else "general", "glucose": glucose, "triglycerides": tg, "creatinine": creatinine}
        result = st.session_state.get("public_result")
        if result and (result["inputs"] != current or not fasting):
            st.session_state.pop("public_result", None)
        error = None
        if submitted:
            st.session_state.pop("public_result", None)
            try:
                if glucose is None or tg is None or (hd and creatinine is None):
                    raise ValueError(f"Completa los {'tres' if hd else 'dos'} resultados de laboratorio para continuar.")
                if not fasting:
                    raise ValueError("Confirma que los resultados son en ayunas y están en mg/dL.")
                tyg = calculate_tyg(glucose, tg)
                light = classify(tyg, creatinine) if hd else tyg_band(tyg)
                st.session_state.public_result = {"inputs": current, "tyg": tyg, "light": light}
            except ValueError as exc:
                error = str(exc)
        result = st.session_state.get("public_result")
        with right:
            if error:
                st.error(error)
            if result:
                items, info = result_items(result)
                metrics = f'<div class="tl-metrics"><span>TyG <b>{result["tyg"]:.2f}</b></span>'
                if result["inputs"]["mode"] == "hd":
                    metrics += f'<span>Creatinina <b>{creatinine:g}</b> mg/dL</span>'
                metrics += "</div>"
                eyebrow = "03 · TU SEMÁFORO RENAL" if result["inputs"]["mode"] == "hd" else "03 · TU SEMÁFORO TyG"
                st.markdown(result_card(items, result["light"], eyebrow, metrics), unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="public-empty"><div class="public-illustration" aria-hidden="true">{logo_img("")}</div><div class="public-step">03 · TU SEMÁFORO</div><h2>Tu resultado aparecerá<br>aquí, en colores.</h2><p>Completa los campos y pulsa <strong>Ver mi semáforo</strong>.<br>Te explicaremos qué puede significar y qué hacer.</p></div>', unsafe_allow_html=True)
            st.button("Borrar mis datos y comenzar de nuevo", on_click=clear_public_inputs, width="stretch")
        if result:
            items, info = result_items(result)
            st.markdown("### ¿Qué puede implicar este resultado?")
            guide(info)
            if result["inputs"]["mode"] == "hd":
                st.caption(f"Cortes del Semáforo Renal: TyG {TYG_CUTOFF} y creatinina prediálisis {CREATININE_CUTOFF} mg/dL. {COHORT_NOTE}")
            else:
                st.caption(TYG_GENERAL_NOTE)
            st.info(PUBLIC_NOTE)
            summary = result_text(result, info)
            c1, c2 = st.columns(2, gap="medium")
            with c1:
                st.markdown("#### 📄 Guardar mi resultado")
                st.download_button("Descargar mi resultado", summary.encode("utf-8"), file_name="mi_semaforo_renal.txt", mime="text/plain", width="stretch")
            with c2:
                email_section(summary, generation, smtp)
        st.markdown('<div class="public-bottom"><strong>Tu consulta es personal.</strong> No pedimos nombre ni teléfono, y el correo es opcional: solo se usa para enviarte el resultado. El cálculo se procesa durante esta sesión y no se agrega a los expedientes de la plataforma.</div>', unsafe_allow_html=True)
        with st.expander("¿Qué es el índice TyG y cómo se calcula?"):
            st.write("TyG es la abreviatura de triglicéridos y glucosa. Combina esos dos resultados de laboratorio en un valor numérico que se estudia como indicador metabólico.")
            st.latex(r"TyG=\ln\left(\frac{Triglicéridos\ (mg/dL)\times Glucosa\ (mg/dL)}{2}\right)")
            st.write(PUBLIC_NOTE)
            st.markdown(f"[Consultar una publicación que describe esta fórmula]({TYG_REFERENCE})")
        st.caption("Semáforo Renal Tabasco · Proyecto académico UJAT · Información para acompañar tu consulta de salud.")
        st.markdown('<div class="public-theme-hint">🌓 La página sigue el modo claro u oscuro de tu dispositivo. También puedes cambiarlo en el menú ⋮ › Settings › Theme.</div>', unsafe_allow_html=True)

def render_sharing(default_url=""):
    st.title("Compartir calculadora")
    st.write("Prepara el código QR para que pacientes y visitantes abran directamente la calculadora, sin iniciar sesión.")
    st.info("Publica primero el sitio y utiliza su dirección HTTPS definitiva. Cada persona que escanee el QR entrará a una calculadora vacía y personal.")
    with st.form("public_link"):
        url = st.text_input("Dirección pública del sitio", value=default_url, placeholder="https://tu-sitio-publicado.com/")
        generate = st.form_submit_button("Generar código QR", type="primary")
    if generate:
        st.session_state.pop("sharing_link", None)
        try:
            st.session_state.sharing_link = public_calculator_url(url)
        except ValueError as exc:
            st.error(str(exc))
    link = st.session_state.get("sharing_link")
    if link:
        st.subheader("Escanea y calcula tu índice TyG")
        image = qr_png(link)
        st.image(image, width=280)
        st.link_button("Abrir calculadora pública", link)
        st.code(link, language=None)
        st.download_button("Descargar QR para imprimir", image, file_name="qr_calculadora_tyg.png", mime="image/png")
        st.caption("Antes de imprimirlo, escanéalo desde un teléfono con datos móviles y confirma que el sitio abre sin pedir una cuenta.")
