"""Componentes visuales del semáforo: luces, explicación, riesgos y enlaces de divulgación."""
from html import escape

import streamlit as st

from renal.domain import LINKS, light_name


def traffic_light(items, active):
    """items: lista de (clave, info) en orden; active: clave encendida."""
    lamps = "".join(
        f'<span class="lamp{" on" if key == active else ""}" style="--lamp:{info["color"]}" title="{escape(info["light"])}"></span>'
        for key, info in items
    )
    return f'<div class="tl-housing" role="img" aria-label="Semáforo: luz {light_name(dict(items)[active])} encendida">{lamps}</div>'


def legend(items, active):
    chips = "".join(
        f'<span class="tl-chip{" on" if key == active else ""}" style="--lamp:{info["color"]}"><i></i>{escape(info["title"])}</span>'
        for key, info in items
    )
    return f'<div class="tl-legend">{chips}</div>'


def result_card(items, active, eyebrow, metrics_html=""):
    info = dict(items)[active]
    return (
        f'<div class="tl-result" style="--lamp:{info["color"]}">'
        f'{traffic_light(items, active)}'
        f'<div class="tl-body"><div class="tl-eyebrow">{escape(eyebrow)} · LUZ {light_name(info).upper()}</div>'
        f'<h2>{escape(info["title"])}</h2><span class="tl-label">{escape(info["label"])}</span>'
        f'{metrics_html}<p>{escape(info["meaning"])}</p></div></div>'
        f'{legend(items, active)}'
    )


def links_html(keys):
    cards = "".join(
        f'<a class="tl-link" href="{escape(LINKS[k][2])}" target="_blank" rel="noopener noreferrer">'
        f'<strong>{escape(LINKS[k][0])}</strong><small>{escape(LINKS[k][1])} ↗</small></a>'
        for k in keys
    )
    return f'<div class="tl-links">{cards}</div>'


DEFAULT_RISKS_TITLE = "Si sigue así, podría aumentar el riesgo de"


def guide(info):
    """Riesgos, acciones y lecturas recomendadas para la luz encendida."""
    risks_title = info.get("risks_title", DEFAULT_RISKS_TITLE)
    left, right = st.columns(2, gap="medium")
    with left:
        st.markdown(f'<div class="tl-box risk"><h4>⚠️ {escape(risks_title)}</h4><ul>'
                    + "".join(f"<li>{escape(r)}</li>" for r in info["risks"]) + "</ul></div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="tl-box todo"><h4>✅ ¿Qué puedes hacer?</h4><ul>'
                    + "".join(f"<li>{escape(a)}</li>" for a in info["actions"]) + "</ul></div>", unsafe_allow_html=True)
    st.markdown('<div class="tl-read">📚 Para saber más · artículos de divulgación en español</div>' + links_html(info["links"]),
                unsafe_allow_html=True)


def summary_text(info):
    risks_title = info.get("risks_title", DEFAULT_RISKS_TITLE)
    lines = [f'Semáforo: luz {light_name(info)} · {info["title"]} ({info["label"]})', "", info["meaning"], "",
             risks_title + ":"]
    lines += [f"  - {r}" for r in info["risks"]]
    lines += ["", "¿Qué puedes hacer?"] + [f"  - {a}" for a in info["actions"]]
    lines += ["", "Para saber más:"] + [f"  - {LINKS[k][0]} ({LINKS[k][1]}): {LINKS[k][2]}" for k in info["links"]]
    return "\n".join(lines)
