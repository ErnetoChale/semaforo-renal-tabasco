from datetime import date, timedelta
from cryptography.fernet import Fernet
from renal.domain import Inputs
from renal.storage import Store

def make_demo():
    store = Store(":memory:", Fernet.generate_key())
    user_id = store.create_user("demostracion", "Solo-demostracion-2026!", role="admin", bootstrap=True)
    examples = [
        ("Paciente ejemplo A", "Femenino", 54, [(106, 155, 7.3, 66), (102, 148, 7.7, 66.5), (98, 130, 8.1, 67)]),
        ("Paciente ejemplo B", "Masculino", 62, [(115, 190, 9.1, 78), (110, 180, 9.0, 77.5), (104, 170, 8.9, 77)]),
        ("Paciente ejemplo C", "No especificado", 47, [(80, 100, 8.8, 62), (82, 105, 8.9, 62.5), (80, 110, 9.0, 63)]),
    ]
    for name, sex, age, visits in examples:
        patient = store.create_patient(user_id, name, sex)
        for n, (glucose, tg, creat, weight) in enumerate(visits):
            store.save_evaluation(user_id, patient, Inputs(age, glucose, tg, creat, weight, 164 if age != 62 else 174, (date.today()-timedelta(days=(2-n)*28)).isoformat()))
    return store, store.user(user_id)
