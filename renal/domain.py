"""Versioned research calculations. These strata are not diagnoses."""
from dataclasses import dataclass
from datetime import date
import math

METHOD_VERSION = "cohorte-1.0"
TYG_CUTOFF = 8.8
CREATININE_CUTOFF = 8.5
COHORT_NOTE = (
    "Los cortes son las medianas de una cohorte de 82 adultos con enfermedad renal crónica estadio 5 "
    "en hemodiálisis de un hospital de referencia de Villahermosa, Tabasco (mayo a agosto de 2025)."
)
METHOD_NOTE = (
    "Herramienta académica para explorar fenotipos metabólico-musculares en pacientes en hemodiálisis. "
    + COHORT_NOTE + " No son criterios diagnósticos universales y la validación externa está pendiente. "
    "Requiere interpretación del equipo clínico; no confirma ni descarta enfermedad."
)

# --- Enlaces de divulgación (verificados en noviembre de 2026) ---------------------------
LINKS = {
    "insulina": ("Resistencia a la insulina y la prediabetes", "NIDDK · Institutos Nacionales de Salud",
                 "https://www.niddk.nih.gov/health-information/informacion-de-la-salud/diabetes/informacion-general/que-es/resistencia-insulina-prediabetes"),
    "trigliceridos": ("Triglicéridos: qué son y por qué importan", "MedlinePlus en español",
                      "https://medlineplus.gov/spanish/triglycerides.html"),
    "proteina": ("Cómo aumentar la ingesta de proteínas durante la diálisis", "National Kidney Foundation",
                 "https://www.kidney.org/es/temas-del-rinon/como-aumentar-la-ingesta-de-proteinas-durante-la-dialisis"),
    "alimentacion": ("Alimentación saludable durante la hemodiálisis", "NIDDK · Institutos Nacionales de Salud",
                     "https://www.niddk.nih.gov/health-information/informacion-de-la-salud/enfermedades-rinones/insuficiencia-renal/hemodialisis/alimentacion-saludable-durante"),
    "ejercicio": ("El ejercicio y la enfermedad del riñón crónica", "National Kidney Foundation",
                  "https://www.kidney.org/es/temas-del-rinon/el-ejercicio-y-la-enfermedad-del-rinon-cronica"),
    "corazon": ("Cómo mantener tu corazón sano durante la diálisis", "National Kidney Foundation",
                "https://www.kidney.org/es/temas-del-rinon/toma-medidas-para-mantener-tu-corazon-sano-durante-la-dialisis"),
    "dieta_hd": ("La hemodiálisis y tu dieta", "National Kidney Foundation",
                 "https://www.kidney.org/es/temas-del-rinon/la-hemodialisis-y-tu-dieta"),
}

# --- Semáforo Renal: cuatro fenotipos (orden de mayor a menor prioridad) -----------------
STRATA = {
    "muscular": {
        "title": "Sarcopenia metabólica", "light": "Rojo", "label": "Prioridad alta", "symbol": "01",
        "color": "#D93A47", "background": "#FCEBEC",
        "detail": "TyG igual o superior al corte y creatinina inferior al corte de la cohorte.",
        "clinical_action": "Priorizar evaluación nutricional y seguimiento intensivo.",
        "meaning": "Tus valores sugieren dos cosas al mismo tiempo: que el cuerpo podría no estar usando bien la insulina (resistencia a la insulina) y que la reserva de músculo podría ser baja. Esta combinación puede existir aunque el peso o el IMC parezcan normales o altos. En el estudio de Tabasco fue el grupo con el perfil más vulnerable.",
        "risks": [
            "Pérdida progresiva de fuerza y músculo, con más cansancio y dificultad para las actividades diarias.",
            "Mayor probabilidad de caídas, infecciones y hospitalizaciones.",
            "Más riesgo de problemas del corazón y de los vasos sanguíneos, la principal causa de complicaciones en personas en diálisis.",
            "Descontrol de la glucosa y de las grasas en la sangre.",
        ],
        "actions": [
            "Comenta este resultado con tu nefrólogo y pide pronto una valoración con nutrición renal.",
            "Pregunta cuánta proteína necesitas: en hemodiálisis suele requerirse más que antes de iniciarla.",
            "Pregunta qué ejercicio es seguro para ti, como caminar, ejercicios de fuerza o bicicleta durante la sesión.",
            "Reduce refrescos, pan dulce y frituras siguiendo las indicaciones de tu equipo.",
        ],
        "links": ["proteina", "ejercicio", "insulina", "corazon"],
    },
    "nutrition": {
        "title": "Desgaste nutricional", "light": "Naranja", "label": "Prioridad moderada-alta", "symbol": "02",
        "color": "#E8772E", "background": "#FDF0E6",
        "detail": "TyG y creatinina inferiores a los cortes de la cohorte.",
        "clinical_action": "Vigilancia de masa muscular y soporte nutricional.",
        "meaning": "El azúcar y las grasas de tu sangre no muestran una alteración marcada, pero la creatinina baja sugiere que la reserva de músculo podría estar disminuida. En hemodiálisis esto suele relacionarse con recibir menos proteína y energía de las que el cuerpo necesita, o con inflamación (desgaste proteico-energético).",
        "risks": [
            "Debilidad, cansancio y pérdida de peso o de músculo.",
            "Defensas más bajas y mayor riesgo de infecciones.",
            "Recuperación más lenta y más hospitalizaciones.",
            "Peor calidad de vida y más complicaciones si el desgaste avanza.",
        ],
        "actions": [
            "Pide una valoración con nutrición renal para revisar si comes suficiente proteína y energía.",
            "Avisa a tu equipo si tienes poco apetito, náuseas o bajaste de peso sin querer.",
            "Pregunta por actividad física adaptada para conservar el músculo.",
            "No suspendas ni acortes tus sesiones de hemodiálisis.",
        ],
        "links": ["proteina", "alimentacion", "ejercicio"],
    },
    "metabolic": {
        "title": "Obesidad muscular / riesgo cardiometabólico", "light": "Amarillo", "label": "Prioridad moderada", "symbol": "03",
        "color": "#E5B000", "background": "#FFF7DB",
        "detail": "TyG y creatinina iguales o superiores a los cortes de la cohorte.",
        "clinical_action": "Control metabólico y prevención cardiovascular.",
        "meaning": "Tu reserva de músculo parece conservada, lo cual es favorable. Sin embargo, el índice TyG elevado sugiere resistencia a la insulina y alteración del azúcar o de las grasas de la sangre.",
        "risks": [
            "Mayor riesgo de infarto, insuficiencia cardiaca y enfermedad cerebrovascular.",
            "Aparición o descontrol de diabetes tipo 2.",
            "Triglicéridos altos que dañan los vasos sanguíneos.",
            "Con el tiempo, el desequilibrio metabólico también puede afectar al músculo.",
        ],
        "actions": [
            "Revisa con tu médico el control de glucosa, triglicéridos, colesterol y presión arterial.",
            "Limita bebidas azucaradas, harinas refinadas y frituras dentro de tu plan de alimentación renal.",
            "Mantente activo con el ejercicio que apruebe tu equipo.",
            "Si fumas, pide ayuda para dejarlo.",
        ],
        "links": ["corazon", "insulina", "trigliceridos"],
    },
    "reference": {
        "title": "Músculo protegido", "light": "Verde", "label": "Seguimiento habitual", "symbol": "04", "risks_title": "Aun así, ten presente que",
        "color": "#22A06B", "background": "#E6F6EE",
        "detail": "TyG inferior al corte y creatinina igual o superior al corte de la cohorte. No implica ausencia de riesgo.",
        "clinical_action": "Seguimiento rutinario y educación preventiva.",
        "meaning": "Tus valores sugieren una buena reserva de músculo y un perfil de azúcar y grasas controlado en comparación con la cohorte. Es el patrón más favorable del semáforo, aunque no significa ausencia de riesgo.",
        "risks": [
            "La pérdida de músculo puede aparecer con el tiempo, con la edad o después de una hospitalización.",
            "El riesgo del corazón sigue siendo mayor que en la población general por la enfermedad renal.",
            "Si se descuidan la alimentación, la actividad física o las sesiones, los valores pueden cambiar.",
        ],
        "actions": [
            "Continúa con tus sesiones y tu plan de alimentación.",
            "Mantente activo de forma regular.",
            "Repite la evaluación con tus próximos estudios para vigilar cambios.",
        ],
        "links": ["dieta_hd", "ejercicio"],
    },
}

# --- Semáforo del TyG para personas que no están en hemodiálisis ------------------------
# No existe un punto de corte universal. Se usan como referencia orientativa:
# 8.5 (resistencia a la insulina; Rev Cubana Endocrinol 2025) y 8.8 (síndrome metabólico;
# Unger et al., Endocrinol Nutr 2014).
TYG_GENERAL_LOW, TYG_GENERAL_HIGH = 8.5, 8.8
TYG_GENERAL_NOTE = (
    "No existe un punto de corte universal del índice TyG. Como referencia orientativa se usan 8.5, "
    "asociado con resistencia a la insulina, y 8.8, asociado con síndrome metabólico en estudios publicados."
)
TYG_BANDS = {
    "green": {
        "title": "TyG en rango favorable", "light": "Verde", "risks_title": "Aun así, ten presente que", "label": f"Menor de {TYG_GENERAL_LOW}", "color": "#22A06B",
        "meaning": "Tu resultado está por debajo de los valores que varios estudios asocian con resistencia a la insulina.",
        "risks": ["Un buen resultado hoy no garantiza el futuro: el sedentarismo, el aumento de peso y una dieta alta en azúcares pueden elevarlo con los años."],
        "actions": ["Mantén una alimentación equilibrada y actividad física regular.", "Repite tus estudios de laboratorio en tus revisiones habituales."],
        "links": ["insulina"],
    },
    "yellow": {
        "title": "TyG en zona de vigilancia", "light": "Amarillo", "label": f"Entre {TYG_GENERAL_LOW} y {TYG_GENERAL_HIGH}", "color": "#E5B000",
        "meaning": "Tu resultado está en la zona en la que algunos estudios empiezan a encontrar resistencia a la insulina, es decir, que el cuerpo necesita más insulina para controlar el azúcar.",
        "risks": ["Si sigue subiendo, aumenta la probabilidad de prediabetes y diabetes tipo 2.", "También se relaciona con triglicéridos altos, hígado graso y más riesgo del corazón."],
        "actions": ["Coméntalo en tu próxima consulta y pregunta si necesitas otros estudios.", "Reduce bebidas azucaradas y harinas refinadas, y aumenta tu actividad física.", "Si tienes sobrepeso, bajar un poco de peso puede ayudar."],
        "links": ["insulina", "trigliceridos"],
    },
    "red": {
        "title": "TyG elevado", "light": "Rojo", "label": f"{TYG_GENERAL_HIGH} o más", "color": "#D93A47",
        "meaning": "Tu resultado está en el rango que diversos estudios asocian con resistencia a la insulina y síndrome metabólico.",
        "risks": ["Mayor probabilidad de desarrollar diabetes tipo 2 o de que se descontrole si ya la tienes.", "Más riesgo de infarto, enfermedad cerebrovascular e hígado graso.", "Los triglicéridos muy altos también pueden inflamar el páncreas."],
        "actions": ["Agenda una consulta para revisar glucosa, triglicéridos, colesterol y presión arterial.", "Pide orientación de nutrición y comienza actividad física de forma gradual.", "Evita refrescos, alcohol en exceso y alimentos fritos o muy procesados."],
        "links": ["insulina", "trigliceridos"],
    },
}

LIGHT_NAMES = {"Rojo": "roja", "Naranja": "naranja", "Amarillo": "amarilla", "Verde": "verde"}

def light_name(info):
    """Nombre de la luz concordado con «luz» (luz roja, luz amarilla…)."""
    return LIGHT_NAMES[info["light"]]

def tyg_band(tyg):
    if not math.isfinite(tyg):
        raise ValueError("El índice TyG debe ser un número finito.")
    if tyg >= TYG_GENERAL_HIGH:
        return "red"
    return "yellow" if tyg >= TYG_GENERAL_LOW else "green"

@dataclass(frozen=True)
class Inputs:
    age: int
    glucose: float
    triglycerides: float
    creatinine: float
    weight: float
    height: float
    evaluated_on: str

    def validate(self):
        bounds = {
            "age": (1, 120, "Edad"), "glucose": (1, 1000, "Glucosa"),
            "triglycerides": (1, 3000, "Triglicéridos"), "creatinine": (.1, 50, "Creatinina"),
            "weight": (1, 400, "Peso"), "height": (50, 250, "Talla"),
        }
        for field, (low, high, label) in bounds.items():
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{label}: ingresa un valor entre {low} y {high}.")
        if int(self.age) != self.age:
            raise ValueError("La edad debe expresarse en años enteros.")
        try:
            evaluation_date = date.fromisoformat(self.evaluated_on)
        except (TypeError, ValueError):
            raise ValueError("La fecha de evaluación no es válida.") from None
        if evaluation_date > date.today():
            raise ValueError("La fecha de evaluación no puede estar en el futuro.")

def classify(tyg, creatinine, tyg_cutoff=TYG_CUTOFF, creatinine_cutoff=CREATININE_CUTOFF):
    if not all(math.isfinite(v) for v in (tyg, creatinine, tyg_cutoff, creatinine_cutoff)):
        raise ValueError("Los indicadores deben ser números finitos.")
    if tyg >= tyg_cutoff:
        return "muscular" if creatinine < creatinine_cutoff else "metabolic"
    return "nutrition" if creatinine < creatinine_cutoff else "reference"

def calculate_tyg(glucose, triglycerides):
    """TyG only: no patient identity, kidney-specific cutoffs or persistence."""
    for value, high, label in ((glucose, 1000, "Glucosa"), (triglycerides, 3000, "Triglicéridos")):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= high:
            raise ValueError(f"{label}: escribe el resultado de tu laboratorio, entre 1 y {high} mg/dL.")
    return math.log(triglycerides * glucose / 2)

def calculate(inputs):
    inputs.validate()
    tyg = calculate_tyg(inputs.glucose, inputs.triglycerides)
    return {
        "tyg": tyg, "bmi": inputs.weight / (inputs.height / 100) ** 2,
        "stratum": classify(tyg, inputs.creatinine), "method_version": METHOD_VERSION,
        "tyg_cutoff": TYG_CUTOFF, "creatinine_cutoff": CREATININE_CUTOFF,
    }

def precision_note(value, cutoff, decimals):
    if value < cutoff and round(value, decimals) >= cutoff:
        return f"Valor completo {value:.6f}; inferior al corte {cutoff}. La clasificación usa el valor sin redondear."
    return "La clasificación utiliza valores sin redondear."
