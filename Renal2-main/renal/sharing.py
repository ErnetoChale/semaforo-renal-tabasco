"""Public calculator links and locally generated QR images; never include lab values."""
import io
import ipaddress
import re
from urllib.parse import urlencode, urlsplit, urlunsplit

def public_calculator_url(url):
    url = url.strip()
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("Revisa la dirección del sitio publicado.") from None
    if parsed.scheme != "https" or not hostname or parsed.username or parsed.password:
        raise ValueError("Usa la dirección pública HTTPS del sitio, sin credenciales.")
    hostname = hostname.rstrip(".").lower()
    if "." not in hostname or hostname in ("localhost", "localhost.localdomain") or hostname.endswith((".local", ".localhost", ".internal", ".test", ".invalid", ".example")):
        raise ValueError("El QR necesita una dirección pública; una dirección local no funciona desde otros teléfonos.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_host = hostname.encode("idna").decode()
        except UnicodeError:
            raise ValueError("Revisa el dominio del sitio publicado.") from None
        if not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in ascii_host.split(".")):
            raise ValueError("Revisa el dominio del sitio publicado.")
        if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", hostname):
            raise ValueError("Usa el dominio público del sitio, no una dirección local abreviada.")
    else:
        if not address.is_global:
            raise ValueError("El QR necesita una dirección pública, no una dirección de red local.")
    if port is not None and port != 443:
        raise ValueError("Usa la dirección HTTPS pública estándar del sitio.")
    # Deliberately discard other query parameters and fragments: no tokens or lab data in the QR.
    return urlunsplit(("https", parsed.netloc, parsed.path or "/", urlencode({"vista": "publica"}), ""))

def qr_png(url):
    import qrcode
    link = public_calculator_url(url)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="#12314b", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()
