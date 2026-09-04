import math
import streamlit as st

# Umbrales según la mediana de la cohorte del estudio
MEDIANA_TYG = 8.8
MEDIANA_CREAT = 8.5

st.set_page_config(
    page_title="Semáforo Renal Tabasco",
    page_icon="🩺",
    layout="centered"
)

st.title("🩺 Semáforo Renal Tabasco")
st.caption("Estratificación Metabólico-Muscular de Bajo Costo en Hemodiálisis | UJAT")

st.subheader("📋 Parámetros del Paciente")
glucosa = st.number_input("Glucosa en ayunas (mg/dL)", value=110.0, step=1.0)
trigliceridos = st.number_input("Triglicéridos (mg/dL)", value=180.0, step=1.0)
creatinina = st.number_input("Creatinina prediálisis (mg/dL)", value=7.2, step=0.1)
peso = st.number_input("Peso post-diálisis (kg)", value=68.0, step=0.5)
talla = st.number_input("Talla / Estatura (cm)", value=160.0, step=1.0)

if st.button("Estratificar Paciente 🚀", type="primary", use_container_width=True):
    if any(v <= 0 for v in [glucosa, trigliceridos, creatinina, peso, talla]):
        st.error("⚠️ Por favor ingrese todos los valores clínicos correctamente.")
    else:
        tyg = math.log((trigliceridos * glucosa) / 2)
        imc = peso / ((talla / 100) ** 2)

        st.markdown("---")
        st.subheader("📊 Resultado de la Evaluación")

        # Tarjetas de métricas
        col1, col2, col3 = st.columns(3)
        col1.metric("Índice TyG", f"{tyg:.2f}", f"Corte: {MEDIANA_TYG}")
        col2.metric("Creatinina", f"{creatinina:.1f} mg/dL", f"Corte: {MEDIANA_CREAT}")
        col3.metric("IMC", f"{imc:.1f} kg/m²", "Antropometría")

        st.markdown("---")

        if tyg >= MEDIANA_TYG and creatinina < MEDIANA_CREAT:
            st.error("🔴 **SARCOPENIA METABÓLICA** (Riesgo Alto)")
            st.info(
                "**💡 Interpretación Clínica:** Presencia de elevada resistencia a la insulina combinada con baja reserva muscular (baja creatinina prediálisis).\n\n"
                "**📋 Acción Sugerida:** Priorizar evaluación nutricional especializada, soporte proteico adaptado y seguimiento clínico estrecho."
            )
        elif tyg < MEDIANA_TYG and creatinina < MEDIANA_CREAT:
            st.warning("🟡 **DESGASTE NUTRICIONAL** (Riesgo Moderado-Alto)")
            st.info(
                "**💡 Interpretación Clínica:** Baja reserva muscular sin resistencia a la insulina severa ni alteración lipídica marcada.\n\n"
                "**📋 Acción Sugerida:** Monitorear masa muscular, optimizar el aporte calórico-proteico en dieta y vigilancia nutricional continua."
            )
        elif tyg >= MEDIANA_TYG and creatinina >= MEDIANA_CREAT:
            st.warning("🟠 **OBESIDAD MUSCULAR / RIESGO CARDIOMETABÓLICO**")
            st.info(
                "**💡 Interpretación Clínica:** Reserva muscular adecuada o preservada, pero con alteración en el perfil metabólico (resistencia a la insulina / hipertrigliceridemia).\n\n"
                "**📋 Acción Sugerida:** Enfocar tratamiento en control glucémico, manejo de dislipidemia y prevención de riesgo cardiovascular."
            )
        else:
            st.success("🟢 **MÚSCULO PROTEGIDO** (Perfil Controlado)")
            st.info(
                "**💡 Interpretación Clínica:** Buena reserva muscular asociada a un perfil metabólico dentro de parámetros controlados respecto a la cohorte.\n\n"
                "**📋 Acción Sugerida:** Mantener esquema de hemodiálisis habitual, educación preventiva y seguimiento de rutina."
            )
