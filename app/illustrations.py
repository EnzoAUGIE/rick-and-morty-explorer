"""Illustrations SVG générées pour les lieux.

L'API ne fournit aucune image de lieu. Plutôt que de dépendre d'un site tiers,
on dessine une petite scène selon le type du lieu (planète, station, dimension…),
avec des couleurs tirées du nom : chaque lieu a toujours la même image, et deux
lieux différents ont des images différentes. Aucune requête réseau.
"""
from __future__ import annotations

import hashlib
import random

from markupsafe import Markup

KINDS: dict[str, tuple[str, ...]] = {
    "planet": ("planet", "dwarf planet", "asteroid", "moon"),
    "cluster": ("cluster", "quadrant", "quasar", "galaxy", "star system"),
    "station": ("space station", "spacecraft", "base", "death star", "machine",
                "customs", "police", "ship"),
    "dimension": ("dimension", "reality", "plane", "hell", "diegesis", "nightmare",
                  "dream", "consciousness", "memory", "artificially"),
    "verse": ("microverse", "miniverse", "teenyverse", "box"),
}


def kind_of(location_type: str) -> str:
    t = (location_type or "").lower()
    for kind, words in KINDS.items():
        if any(w in t for w in words):
            return kind
    return "place"


def _hsl(h: float, s: int, l: int) -> str:
    return f"hsl({h % 360:.0f},{s}%,{l}%)"


def location_art(loc, css_class: str = "art") -> Markup:
    """Renvoie un <svg> 16:9 prêt à insérer dans un template Jinja2."""
    seed = int(hashlib.md5(f"{loc.id}-{loc.name}".encode()).hexdigest(), 16)
    rnd = random.Random(seed)
    hue = seed % 360
    p = f"l{loc.id}"  # préfixe des ids SVG : plusieurs SVG coexistent sur une page
    kind = kind_of(loc.type)

    stars = "".join(
        f'<circle cx="{rnd.uniform(0, 320):.0f}" cy="{rnd.uniform(0, 180):.0f}" '
        f'r="{rnd.choice((0.6, 0.9, 1.3))}" fill="#fff" opacity="{rnd.uniform(.3, 1):.2f}"/>'
        for _ in range(45)
    )
    sky = (f'<defs><radialGradient id="{p}sky" cx="50%" cy="40%" r="80%">'
           f'<stop offset="0" stop-color="{_hsl(hue + 200, 45, 16)}"/>'
           f'<stop offset="1" stop-color="#05060c"/></radialGradient>'
           f'<radialGradient id="{p}a" cx="35%" cy="35%" r="70%">'
           f'<stop offset="0" stop-color="{_hsl(hue, 75, 68)}"/>'
           f'<stop offset="1" stop-color="{_hsl(hue + 20, 60, 22)}"/></radialGradient>'
           f'<radialGradient id="{p}b" cx="35%" cy="35%" r="70%">'
           f'<stop offset="0" stop-color="{_hsl(hue + 140, 70, 65)}"/>'
           f'<stop offset="1" stop-color="{_hsl(hue + 160, 55, 20)}"/></radialGradient></defs>'
           f'<rect width="320" height="180" fill="url(#{p}sky)"/>{stars}')

    if kind == "planet":
        ring = rnd.random() < .5
        r = rnd.randint(42, 58)
        body = (f'<circle cx="160" cy="92" r="{r}" fill="url(#{p}a)"/>'
                + "".join(f'<ellipse cx="{160 + rnd.randint(-25, 25)}" cy="{92 + rnd.randint(-25, 25)}" '
                          f'rx="{rnd.randint(6, 16)}" ry="{rnd.randint(3, 8)}" fill="#000" opacity=".15"/>'
                          for _ in range(4)))
        if ring:
            body += (f'<ellipse cx="160" cy="92" rx="{r + 32}" ry="12" fill="none" '
                     f'stroke="{_hsl(hue + 40, 70, 75)}" stroke-width="4" opacity=".8" '
                     f'transform="rotate(-12 160 92)"/>')
    elif kind == "cluster":
        body = "".join(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#{p}{g})"/>'
            for x, y, r, g in [(110, 95, 34, "a"), (205, 70, 22, "b"), (230, 130, 14, "a"),
                               (70, 45, 10, "b")])
    elif kind == "station":
        c = _hsl(hue, 15, 70)
        body = (f'<rect x="148" y="52" width="24" height="76" rx="6" fill="{c}"/>'
                f'<rect x="88" y="80" width="144" height="20" rx="4" fill="{_hsl(hue, 10, 55)}"/>'
                f'<rect x="60" y="70" width="34" height="40" fill="{_hsl(hue + 200, 60, 40)}" opacity=".9"/>'
                f'<rect x="226" y="70" width="34" height="40" fill="{_hsl(hue + 200, 60, 40)}" opacity=".9"/>'
                f'<circle cx="160" cy="90" r="9" fill="{_hsl(hue + 90, 90, 60)}"/>'
                f'<circle cx="160" cy="58" r="3" fill="#ff5a5a"/>')
    elif kind == "dimension":
        body = "".join(
            f'<ellipse cx="160" cy="90" rx="{70 - i * 11}" ry="{58 - i * 9}" fill="none" '
            f'stroke="{_hsl(95 + i * 8, 70, 45 + i * 7)}" stroke-width="7" opacity=".9" '
            f'transform="rotate({i * 25} 160 90)"/>' for i in range(6)
        ) + '<ellipse cx="160" cy="90" rx="14" ry="11" fill="#d9ff9e" opacity=".9"/>'
    elif kind == "verse":
        body = "".join(
            f'<circle cx="160" cy="90" r="{64 - i * 16}" fill="url(#{p}{"ab"[i % 2]})" '
            f'stroke="#fff" stroke-opacity=".3"/>' for i in range(4))
    else:  # lieu "terrestre" : collines + bâtiments
        body = (f'<circle cx="250" cy="48" r="20" fill="{_hsl(hue + 40, 90, 70)}"/>'
                f'<path d="M0 130 Q80 95 160 125 T320 115 V180 H0Z" fill="{_hsl(hue + 90, 45, 30)}"/>'
                + "".join(f'<rect x="{x}" y="{135 - h}" width="{w}" height="{h + 10}" '
                          f'fill="{_hsl(hue, 20, 18 + i * 4)}"/>'
                          for i, (x, w, h) in enumerate(
                              (rnd.randint(30, 260), rnd.randint(14, 26), rnd.randint(20, 55))
                              for _ in range(5)))
                + f'<path d="M0 150 Q100 135 200 152 T320 148 V180 H0Z" fill="{_hsl(hue + 100, 40, 20)}"/>')

    return Markup(
        f'<svg class="{css_class}" viewBox="0 0 320 180" role="img" '
        f'aria-label="Illustration : {Markup.escape(loc.name)}" '
        f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">'
        f'{sky}{body}</svg>'
    )
