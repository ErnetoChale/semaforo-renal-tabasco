from dataclasses import replace
from datetime import date, timedelta
import math
import pytest
from renal.domain import Inputs, calculate, classify, precision_note

@pytest.fixture
def inputs():
    return Inputs(50, 110.0, 180.0, 7.2, 68.0, 160.0, date.today().isoformat())

@pytest.mark.parametrize("tyg,creatinine,expected", [(8.799999, 8.49999, "nutrition"), (8.8, 8.49999, "muscular"), (8.8, 8.5, "metabolic"), (8.799999, 8.5, "reference")])
def test_threshold_inclusion(tyg, creatinine, expected):
    assert classify(tyg, creatinine) == expected

def test_calculations_and_version(inputs):
    result = calculate(inputs)
    assert result["tyg"] == pytest.approx(math.log(9900))
    assert result["bmi"] == pytest.approx(26.5625)
    assert result["method_version"] == "cohorte-1.0"

@pytest.mark.parametrize("field,value", [("age", None), ("age", 1.5), ("glucose", float("nan")), ("triglycerides", float("inf")), ("creatinine", 0), ("weight", -3), ("height", 0), ("glucose", True), ("glucose", 1001), ("evaluated_on", "invalid")])
def test_bad_inputs_rejected(inputs, field, value):
    with pytest.raises(ValueError):
        calculate(replace(inputs, **{field: value}))

def test_future_date_rejected(inputs):
    with pytest.raises(ValueError, match="futuro"):
        calculate(replace(inputs, evaluated_on=(date.today()+timedelta(days=1)).isoformat()))

def test_rounding_does_not_change_classification():
    assert classify(8.799999, 8.4) == "nutrition"
    assert "inferior" in precision_note(8.799999, 8.8, 3)

