"""Anonymous public calculator. Does not initialize or access the patient database."""
import streamlit as st
from renal.domain import calculate_tyg
from renal.branding import logo_img
from renal.sharing import public_calculator_url, qr_png

PUBLIC_NOTE = "Este resultado es informativo. Por sí solo no diagnostica una enfermedad ni indica un tratamiento. Revísalo con un profesional de salud junto con tus estudios y antecedentes."
TYG_REFERENCE = "https://pubmed.ncbi.nlm.nih.gov/31687367/"

def clear_public_inputs():
    for key in list(st.session_state):
        if key.startswith("public_") and key != "public_generation":
            del st.session_state[key]
    st.session_state.public_generation = st.session_state.get("public_generation", 0) + 1

def render_public():
    st.markdown("""<style>
    [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
    .block-container{max-width:1080px;padding-top:3rem!important}
    header[data-testid="stHeader"]{background:transparent}
    </style>""", unsafe_allow_html=True)
    with st.container(key="public-page"):
        st.markdown(f'<div class="public-topbar"><div class="public-brand">{logo_img()}<span><strong>Semáforo Renal</strong><small>TABASCO · UJAT</small></span></div><a href="?vista=profesional" target="_self">Acceso profesional ↗</a></div>', unsafe_allow_html=True)
        st.markdown('<section class="public-hero"><span class="public-pill">PARA TI · SIN REGISTRO</span><h1>Conoce tu índice <span>TyG.</span></h1><p>Usa los resultados de glucosa y triglicéridos de tu laboratorio.<br>Dos datos, un cálculo y una explicación sencilla.</p><div class="public-trust"><span>🔒 Sin nombre ni cuenta</span><span>🗂️ No se guarda en expedientes</span><span>⏱️ Menos de un minuto</span></div></section>', unsafe_allow_html=True)
        left, right = st.columns([1.15, 1], gap="large")
        generation = st.session_state.get("public_generation", 0)
        with left:
            with st.form(f"public_calculator_{generation}"):
                st.markdown('<div class="public-step">01 · TUS RESULTADOS DE LABORATORIO</div>', unsafe_allow_html=True)
                st.subheader("Vamos a calcularlo")
                st.write("Busca estos dos valores en tus estudios. Ambos deben estar expresados en **mg/dL**.")
                glucose = st.number_input("Glucosa en ayunas (mg/dL)", min_value=1., max_value=1000., value=None, step=.1, placeholder="Escribe el valor de glucosa", key=f"public_glucose_{generation}", help="Puede aparecer como glucosa o glucemia en el reporte de laboratorio.")
                tg = st.number_input("Triglicéridos en ayunas (mg/dL)", min_value=1., max_value=3000., value=None, step=.1, placeholder="Escribe el valor de triglicéridos", key=f"public_tg_{generation}", help="Usa el resultado de triglicéridos, no el de colesterol.")
                fasting = st.checkbox("Confirmo que los resultados son en ayunas y están en mg/dL.", key=f"public_confirm_{generation}")
                submitted = st.form_submit_button("Calcular mi índice TyG", type="primary", width="stretch")
            st.caption("¿Tus estudios usan otras unidades o no sabes si fueron en ayunas? Confírmalo con tu laboratorio antes de calcular.")
        current = {"glucose": glucose, "triglycerides": tg}
        result = st.session_state.get("public_result")
        if result and (result["inputs"] != current or not fasting):
            st.session_state.pop("public_result", None)
        error = None
        if submitted:
            st.session_state.pop("public_result", None)
            try:
                if glucose is None or tg is None:
                    raise ValueError("Completa los dos resultados de laboratorio para continuar.")
                if not fasting:
                    raise ValueError("Confirma que ambos resultados son en ayunas y están en mg/dL.")
                st.session_state.public_result = {"inputs": current, "tyg": calculate_tyg(glucose, tg)}
            except ValueError as exc:
                error = str(exc)
        with right:
            result = st.session_state.get("public_result")
            if error:
                st.error(error)
            if result:
                st.markdown(f'<div class="public-result"><div class="public-step">02 · TU RESULTADO</div><h2>Tu índice TyG es</h2><div class="public-result-value">{result["tyg"]:.2f}</div><div class="public-result-tag">Índice de triglicéridos y glucosa</div><p>Calculado con glucosa de <strong>{glucose:g} mg/dL</strong> y triglicéridos de <strong>{tg:g} mg/dL</strong>.</p></div>', unsafe_allow_html=True)
                st.markdown("#### ¿Qué hago con este resultado?")
                st.write("Puedes anotarlo y comentarlo en tu próxima consulta. Un profesional de salud puede interpretarlo junto con tus otros estudios.")
                st.info(PUBLIC_NOTE)
                st.download_button("Descargar mi resultado", f"Índice TyG\nResultado: {result['tyg']:.4f}\nGlucosa en ayunas: {glucose:g} mg/dL\nTriglicéridos en ayunas: {tg:g} mg/dL\nFórmula: ln((triglicéridos × glucosa) / 2)\n\n{PUBLIC_NOTE}\n".encode("utf-8"), file_name="mi_indice_tyg.txt", mime="text/plain", width="stretch")
            else:
                st.markdown(f'<div class="public-empty"><div class="public-illustration" aria-hidden="true">{logo_img("")}</div><div class="public-step">02 · TU RESULTADO</div><h2>Un poco más de claridad<br>sobre tus estudios.</h2><p>Completa los dos campos y pulsa <strong>Calcular mi índice TyG</strong>.<br>Tu resultado aparecerá aquí.</p></div>', unsafe_allow_html=True)
            st.button("Borrar mis datos y comenzar de nuevo", on_click=clear_public_inputs, width="stretch")
        st.markdown('<div class="public-bottom"><strong>Tu consulta es personal.</strong> No pedimos nombre, correo ni teléfono. El cálculo se procesa durante esta sesión y no se agrega a los expedientes de la plataforma.</div>', unsafe_allow_html=True)
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
