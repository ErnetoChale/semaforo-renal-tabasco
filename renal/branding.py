"""Logo de la aplicación, compartido por la vista pública y la profesional."""
from base64 import b64encode
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO_PNG = ASSETS / "logo.png"
_LOGO_URI = "data:image/svg+xml;base64," + b64encode((ASSETS / "logo.svg").read_bytes()).decode()

def logo_img(css_class="brand-logo"):
    return f'<img class="{css_class}" src="{_LOGO_URI}" alt="Logo de Semáforo Renal">'
