"""Versioned research calculations. These strata are not diagnoses."""
from dataclasses import dataclass
from datetime import date
import math

METHOD_VERSION = "cohorte-1.0"
TYG_CUTOFF = 8.8
CREATININE_CUTOFF = 8.5
METHOD_NOTE = (
    "Herramienta académica para explorar patrones en pacientes en hemodiálisis. "
    "Los cortes proceden del prototipo de la cohorte y no son criterios diagnósticos universales. "
    "La referencia bibliográfica y la validación externa están pendientes de documentar. "
    "Requiere interpretación del equipo clínico; no confirma ni descarta enfermedad."
)

STRATA = {
    "muscular": {"title": "Patrón metabólico-muscular", "label": "Revisión integral", "color": "#B43750", "background": "#FCECEF", "symbol": "01", "detail": "TyG igual o superior al corte y creatinina inferior al corte de la cohorte."},
    "nutrition": {"title": "Patrón de vigilancia nutricional", "label": "Revisión nutricional", "color": "#936000", "background": "#FFF5DB", "symbol": "02", "detail": "TyG y creatinina inferiores a los cortes de la cohorte."},
    "metabolic": {"title": "Patrón de vigilancia metabólica", "label": "Revisión metabólica", "color": "#6850AD", "background": "#F1EDFC", "symbol": "03", "detail": "TyG y creatinina iguales o superiores a los cortes de la cohorte."},
    "reference": {"title": "Patrón de referencia de la cohorte", "label": "Seguimiento contextual", "color": "#087F73", "background": "#E5F6F0", "symbol": "04", "detail": "TyG inferior al corte y creatinina igual o superior al corte de la cohorte. No implica ausencia de riesgo."},
}

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
