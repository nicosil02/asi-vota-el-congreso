"""Genera el sitio público en sitio/ con el diseño aprobado en el lienzo ("Diario de bolsillo").

Páginas: inicio (carrusel + últimas votaciones), votaciones, una por votación, iniciativas
(buscador con ficha), congresistas, una por congresista, bancadas, una por bancada y resumen semanal.
Los datos salen de datos.py (Base_legislativa en solo lectura). Titulares del carrusel: guion.json.
Uso: python sitio.py   y luego   python -m http.server -d sitio
"""
import json
import re
import math
import shutil
from html import escape as e
from pathlib import Path

from datos import AQUI, CORTO, K, cargar, estadisticas, ganador, postura, slug

SALIDA = AQUI / "sitio"
VERSION = __import__("time").strftime("%Y%m%d%H%M")  # cambia en cada generación: el navegador no usa archivos viejos
ETIQ = {"si": "A favor", "no": "En contra", "abst": "Abstención", "aus": "No votó"}
EST = {"pres": ("Presentada", "#4F5B6B"), "com": ("En comisión", "#2C5AA0"), "dict": ("Con dictamen", "#8C6D0E"),
       "pleno": ("En el pleno", "#8C6D0E"), "sen": ("Pasó al Senado", "#2C5AA0"), "apr": ("Aprobada", "#1E8A4C"),
       "ley": ("Publicada", "#14663A"), "ret": ("Retirada", "#6B7685"), "arch": ("Archivada", "#6B7685")}
LOGOS = {p.stem: p.name for p in (AQUI / "logos").iterdir() if p.suffix != ".html"}
NAV = [("Inicio", "index.html"), ("Votaciones", "votaciones.html"), ("Iniciativas", "iniciativas.html"),
       ("Congresistas", "congresistas.html"), ("Bancadas", "bancadas.html"), ("Resumen semanal", "resumen.html")]


def logo(nombre, pre="", clase="logo"):
    f = LOGOS.get(slug(nombre or ""))
    return f'<img class="{clase}" src="{pre}logos/{f}" alt="" title="{e(nombre)}">' if f else ""


def foto(x, pre="", clase="cara"):
    """Foto oficial del congresista; si no hay, sus iniciales."""
    if x.get("foto"):
        return f'<img class="{clase}" src="{pre}fotos/congresistas/{x["foto"]}" alt="" loading="lazy">'
    ini = "".join(p[0] for p in x["nombre"].split() if p[0].isupper())[:2]
    return f'<span class="{clase} sin">{e(ini)}</span>'


def camara(c, corto=True):
    return ("Senado" if corto else "Senado de la República") if c in ("senado", "S") else "Diputados" if c in ("diputados", "D") else "Congreso"


def barra(d, alto=6):
    return f'<div class="barra" style="height:{alto}px">' + "".join(
        f'<span class="tramo t-{k}" style="flex:{d[k]}"></span>' for k in ("si", "no", "abst", "aus") if d.get(k)) + "</div>"


def punto(e_):
    n, c = EST[e_]
    return f'<span class="estado" style="color:{c}"><i style="background:{c}"></i>{n}</span>'


def pestanas(nombre, items):
    """items: [(id, rótulo, html)]; el primero abierto. El cambio lo hace app.js."""
    botones = "".join(f'<button role="tab" id="tab-{i}" aria-controls="pan-{i}" aria-selected="{str(n == 0).lower()}">{e(r)}</button>'
                      for n, (i, r, _) in enumerate(items))
    paneles = "".join(f'<div role="tabpanel" id="pan-{i}" aria-labelledby="tab-{i}" class="panel"{"" if n == 0 else " hidden"}>{h}</div>'
                      for n, (i, _, h) in enumerate(items))
    return f'<div class="pestanas" role="tablist" aria-label="{e(nombre)}" style="--n:{len(items)}">{botones}</div>{paneles}'


def chips(grupo, opciones, sel=None):
    sel = sel or opciones[0][0]
    return f'<div class="chips" data-grupo="{grupo}">' + "".join(
        f'<button type="button" data-v="{v}" aria-pressed="{str(v == sel).lower()}">{e(t)}</button>' for v, t in opciones) + "</div>"


def pagina(titulo, activo, cuerpo, pre="", desc="Cómo vota el Congreso del Perú: votaciones, iniciativas, congresistas y bancadas."):
    nav = "".join(f'<a href="{pre}{h}"{" aria-current=page" if n == activo else ""}>{n}</a>' for n, h in NAV)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#E3E8EE"><meta name="description" content="{e(desc)}">
<title>{e(titulo)} | Así vota el Congreso</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{pre}estilo.css?v={VERSION}">
</head><body>
<header class="cab"><div class="col cab-in">
  <a class="marca" href="{pre}index.html">Así vota el Congreso</a>
  <nav aria-label="Secciones">{nav}</nav>
</div></header>
<main class="col">{cuerpo}</main>
<footer class="col pie">
  <p>Proyecto independiente y sin fines de lucro. Los datos salen de lo que publica el Congreso de la República: actas, votos por congresista, proyectos y su trámite.
  Fotos y logos de Wikimedia Commons.</p>
</footer>
<script src="{pre}app.js?v={VERSION}" defer></script>
</body></html>"""


# ---------- piezas de votación ----------

def fila_votacion(v, pre=""):
    return f"""<a class="fila" href="{pre}v/{v['slug']}.html" data-camara="{v['camara']}" data-q="{e(v['titulo'].lower())}"{' data-tramite' if v['tramite'] else ''}>
  <span class="meta">{camara(v['camara'])}, {v['f']}</span>
  <b class="clamp2">{e(v['titulo'])}</b>{barra(v)}</a>"""


def marcador(v, grande=False):
    tam = "big" if grande else ""
    abst = "Abst." if not grande else ("Abstención" if v["abst"] == 1 else "Abstenciones")
    return f"""<div class="tarjeta marcador {tam}">
  <div class="cifras"><span><b class="c-si">{v['si']}</b>A favor</span><span><b class="c-no">{v['no']}</b>En contra</span><span><b class="c-abst">{v['abst']}</b>{abst}</span></div>
  {barra(v, 8)}
  <p class="nota">{'Aprobada' if ganador(v) == 'si' else 'Rechazada'}. Los ausentes y licencias no cuentan.</p></div>"""


def asientos(n, filas):
    """n asientos en semicírculos con igual separación (como un hemiciclo real). Radio exterior = 1."""
    r0 = (n / math.pi - filas * (filas - 1) / 2) / filas
    radios = [r0 + i for i in range(filas)]
    por_fila = [round(n * r / sum(radios)) for r in radios]
    por_fila[-1] += n - sum(por_fila)
    pts = [(math.pi * (1 - j / (k - 1)), r / radios[-1]) for r, k in zip(radios, por_fila) for j in range(k)]
    pts.sort(key=lambda p: -p[0])
    assert len(pts) == n
    return [(r * math.cos(a), r * math.sin(a)) for a, r in pts], 0.36 / (filas - 1 + r0)


def hemiciclo(v):
    orden = sorted(v["bancadas"], key=lambda nb: -(nb[1]["si"] / max(1, sum(nb[1].values()))))
    votos = [(n, k) for n, b in orden for k in ("si", "abst", "aus", "no") for _ in range(b[k])]
    pts, r = asientos(len(votos), 5 if len(votos) <= 70 else 8)
    circ = "".join(f'<circle class="asiento s-{k}" cx="{x:.3f}" cy="{-y:.3f}" r="{r:.4f}" style="animation-delay:{i * .008:.3f}s"><title>{e(n)}: {ETIQ[k]}</title></circle>'
                   for i, ((x, y), (n, k)) in enumerate(zip(pts, votos)))
    leyenda = "".join(f'<span><i class="t-{k}"></i>{ETIQ[k]}</span>' for k in ("si", "no", "abst", "aus"))
    return (f'<div class="tarjeta pad"><svg class="hemi" viewBox="-1.06 -1.06 2.12 1.12" role="img" aria-label="Hemiciclo: un punto por congresista, '
            f'coloreado según su voto">{circ}</svg><div class="leyenda">{leyenda}</div></div>')


def panel_bancadas(v, pre):
    filas = []
    for n, b in v["bancadas"]:
        p = postura(b)
        res = f"{ETIQ[p]}: {b[p]} de {sum(b.values())}" if p != "aus" else "No votó"
        filas.append(f"""<a class="fila banc" href="{pre}b/{slug(n)}.html">{logo(n, pre)}
  <span class="crece"><span class="linea"><b class="corta">{e(n)}</b><span class="res c-{p}">{res}</span></span>{barra(b, 5)}</span></a>""")
    return f'<div class="tarjeta">{"".join(filas)}</div>'


def panel_nominal(v, pre, por_nombre):
    filas = []
    for nombre, banc, k in sorted(v["filas"], key=lambda f: f[0]):
        x = por_nombre.get((v["camara"], nombre))
        nom = f'<a href="{pre}c/{x["slug"]}.html">{e(x["nombre"])}</a>' if x else e(nombre.title())
        filas.append(f'<tr data-v="{k}" data-q="{e((x["nombre"] if x else nombre).lower())}"><td><span class="con-logo">{foto(x, pre) if x else ""}{logo(banc, pre, "insignia")}</span></td><td>{nom}</td>'
                     f'<td class="der"><span class="pill p-{k}">{ETIQ[k]}</span></td></tr>')
    quien = "senadores" if v["camara"] == "senado" else "diputados"
    return f"""<div class="tarjeta filtrable">
  <div class="herr"><label for="q-{v['slug']}">Buscar por apellido</label>
  <input id="q-{v['slug']}" type="search" class="buscar" placeholder="Por ejemplo: {'Moyano' if v['camara'] == 'senado' else 'Aranda'}">
  {chips('v', [('', 'Todos'), ('si', 'A favor'), ('no', 'En contra'), ('abst', 'Abstención'), ('aus', 'No votó')])}</div>
  <div class="desliza"><table class="nominal"><caption class="cuenta" data-total="{len(filas)}" data-quien="{quien}"></caption><tbody>{''.join(filas)}</tbody></table></div>
</div>"""


def lista_tramite(pasos, actual_color="#2C5AA0", marcar=None):
    out = []
    for n, p in enumerate(pasos):
        color = actual_color if (marcar == n if marcar is not None else n == len(pasos) - 1) else "#8994A3"
        out.append(f'<li><span class="num" style="background:{color}">{n + 1}</span><div><b>{e(p["p"])}</b><span class="meta">{e(p["f"])}</span>'
                   + "".join(f'<a class="pdf" href="{e(d["u"])}" target="_blank" rel="noopener"><span>PDF</span>{e(d["n"])}</a>' for d in p["d"])
                   + "</div></li>")
    return f'<ol class="tramite">{"".join(out)}</ol>'


def panel_docs(v):
    partes = []
    if v["pdf"]:
        partes.append(f'<a class="pdf" href="{e(v["pdf"])}" target="_blank" rel="noopener"><span>PDF</span>Acta de esta votación</a>')
    if v["agenda"]:
        partes.append(f'<a class="pdf" href="{e(v["agenda"])}" target="_blank" rel="noopener"><span>PDF</span>Agenda del pleno de ese día</a>')
    for i in v["inis"]:
        if not i["tram"]:
            continue
        aqui = next((n for n, p in enumerate(i["tram"]) if p["p"].startswith("Aprobada")), None)
        partes.append(f'<h3 class="sub-docs">Iniciativa n.º {i["num"]}</h3><p class="nota">{e(i["t"])}. <a href="../iniciativas.html#{i["k"]}">Ver su ficha</a></p>'
                      + lista_tramite(i["tram"], marcar=aqui))
    if v["docs"] and not v["inis"]:
        partes.append("".join(f'<a class="pdf" href="{e(u)}" target="_blank" rel="noopener"><span>PDF</span>{e(t)}</a>' for t, u in v["docs"]))
    partes.append(f'<details class="acta"><summary>Lo que dice el acta</summary><p>{e(v["asunto"] or "")}</p></details>')
    return f'<div class="tarjeta pad">{"".join(partes)}</div>'


def pag_votacion(v, por_nombre):
    pre = "../"
    tabs = []
    if v["bancadas"]:
        tabs.append(("bancadas", "Bancadas", panel_bancadas(v, pre)))
        tabs.append(("nominal", "Senadores" if v["camara"] == "senado" else "Diputados", panel_nominal(v, pre, por_nombre)))
        tabs.append(("hemiciclo", "Hemiciclo", hemiciclo(v)))
    tabs.append(("docs", "Documentos", panel_docs(v)))
    d = v["difiere"]
    aviso = (f'<p class="nota aviso">La lista por congresista que publicó el Congreso suma {d[0]} a favor, {d[1]} en contra y {d[2]} abstenciones; '
             f'el acta oficial dice {v["si"]}, {v["no"]} y {v["abst"]}. Arriba va el resultado del acta; abajo, la lista tal como se publicó.</p>' if d else "")
    resumen = (f'<p class="resumen clamp2" id="resumen">{e(v["resumen"])}</p><button type="button" class="leer" data-abre="resumen">Leer más</button>'
               if v["resumen"] else "")
    return pagina(v["titulo"], "Votaciones", f"""
<div class="dos">
  <div class="izq">
    <span class="sello">{camara(v['camara'])}, {v['fl']}</span>
    <h1 class="titulo">{e(v['titulo'])}</h1>
    {resumen}
    {marcador(v)}
    {aviso}
  </div>
  <div class="der-col">{pestanas('Detalle de la votación', tabs)}</div>
</div>""", pre, desc=v["titulo"])


# ---------- inicio ----------

def carrusel(guion, por_id):
    items, barras = [], []
    for n, x in enumerate(guion["noticias"]):
        v = por_id.get(x.get("votacion_id"))
        voto = ""
        if v and v["bancadas"]:
            lado = lambda k: "".join(logo(nb, "", "mini") for nb, b in v["bancadas"] if postura(b) == k)
            voto = f'<div class="voto"><span><b class="v-si">{v["si"]}</b>{lado("si")}</span><span><b class="v-no">{v["no"]}</b>{lado("no")}</span></div>'
        href = f'v/{v["slug"]}.html' if v else "resumen.html"
        items.append(f"""<a class="lamina" href="{href}" aria-roledescription="tema" aria-label="{n + 1} de {len(guion['noticias'])}">
  <img class="foto" src="fotos/{x.get('foto', 'hemiciclo')}.jpg" alt="">
  <div class="texto"><span class="sello">{e(x['camara'])}: {e(x['estado'].lower())}</span>
  <h2>{e(x['titular'])}</h2><p>{e(x['puntos'][0])}</p>{voto}</div></a>""")
        barras.append(f'<button type="button" class="b" aria-label="Ir al tema {n + 1}: {e(x["titular"])}"></button>')
    return f"""<section class="carrusel" aria-label="Temas principales de la semana" aria-roledescription="carrusel">
  <div class="pista">{''.join(items)}</div>
  <div class="barras">{''.join(barras)}</div>
  <button type="button" class="flecha atras" aria-label="Tema anterior"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7"/></svg></button>
  <button type="button" class="flecha adelante" aria-label="Tema siguiente"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7"/></svg></button>
</section>"""


def inicio(vs, inis, guion, por_id, bs):
    ultimas = [v for v in vs if not v["tramite"]][:6]
    nuevas = inis[:5]
    filas_ini = "".join(f'<a class="fila" href="iniciativas.html#{i["k"]}"><span class="meta">{camara(i["cam"])}, {i["f"]}</span>'
                        f'<b class="clamp2">{e(i["t"])}</b><span class="linea">{punto(i["e"])}<span class="meta corta">{e(i["quien"])}</span></span></a>' for i in nuevas)
    # las más reñidas: menor diferencia entre a favor y en contra, sin trámites internos
    renidas = sorted((v for v in vs if not v["tramite"] and v["no"]), key=lambda v: abs(v["si"] - v["no"]) / (v["si"] + v["no"] + v["abst"]))[:4]
    filas_ren = "".join(f"""<a class="fila" href="v/{v['slug']}.html"><span class="linea arriba"><b class="clamp2">{e(v['titulo'])}</b>
  <span class="res">{v['si']} a {v['no']}</span></span>{barra(v)}<span class="meta">{camara(v['camara'])}, {v['f']}, {'aprobada' if ganador(v) == 'si' else 'rechazada'}</span></a>""" for v in renidas)
    filas_banc = "".join(f"""<a class="fila banc" href="b/{b['slug']}.html">{logo(n)}<span class="crece"><b class="corta">{e(n)}</b>
  <span class="meta">{len(b['miembros'])} congresistas, {len(b['inis'])} iniciativas</span></span>
  <span class="dato"><b>{b['cohesion']}%</b>cohesión</span><span class="dato"><b>{b['asist']}%</b>asistencia</span></a>""" for n, b in bs.items())
    return pagina("Inicio", "Inicio", f"""
<p class="semana">Semana del {e(guion['semana'].replace('–', 'al'))}</p>
<div class="portada">
  <div class="principal">
    {carrusel(guion, por_id)}
    <div class="encab"><h2>Las más reñidas</h2><a href="votaciones.html">Ver todas</a></div>
    <div class="tarjeta">{filas_ren}</div>
    <div class="encab"><h2>Así votan las bancadas</h2><a href="bancadas.html">Ver bancadas</a></div>
    <div class="tarjeta">{filas_banc}</div>
    <p class="nota">Cohesión: qué tan seguido sus integrantes votan igual que la mayoría de su bancada.</p>
  </div>
  <div class="lado">
    <div class="encab"><h2>Últimas votaciones</h2><a href="votaciones.html">Ver las {len(vs)}</a></div>
    <div class="tarjeta">{''.join(fila_votacion(v) for v in ultimas)}</div>
    <div class="encab"><h2>Iniciativas nuevas</h2><a href="iniciativas.html">Ver las {len(inis)}</a></div>
    <div class="tarjeta">{filas_ini}</div>
  </div>
</div>""")


def pag_votaciones(vs):
    return pagina("Votaciones", "Votaciones", f"""
<h1 class="titulo">Todas las votaciones</h1>
<p class="sub">{len(vs)} votaciones del pleno desde julio de 2026</p>
<div class="filtrable">
  <div class="herr suelta"><label class="oculto" for="q">Buscar votaciones</label>
  <input id="q" type="search" class="buscar" placeholder="Busca un tema: emergencia, BCR, Tribunal…">
  {chips('camara', [('', 'Todas'), ('senado', 'Senado'), ('diputados', 'Diputados')])}
  <label class="check"><input type="checkbox" class="ver-tramites"> Mostrar trámites internos (nóminas, cuartos intermedios)</label></div>
  <p class="cuenta nota" data-quien="votaciones"></p>
  <div class="tarjeta lista">{''.join(fila_votacion(v) for v in vs)}</div>
  <p class="vacio nota" hidden>Ninguna votación con esa búsqueda. Prueba con otra palabra.</p>
</div>""")


# ---------- iniciativas ----------

def datos_iniciativas(inis):
    corta = lambda c: re.sub(r"^Comisión (Bicameral )?(de |del |de la )?", "", c or "")
    indice = [[i["k"], i["num"], i["cam"], i["f"], i["e"], i["tema"], i["sig"], i["quien"], i["t"], i["iso"], corta(i["com"])] for i in inis]
    fichas = {i["k"]: {"com": i["com"], "aut": autores(i["aut"]), "url": i["url"], "tram": i["tram"]} for i in inis}
    return indice, fichas


def autores(lista):
    if not lista:
        return ""
    ap, _, nom = lista[0].partition(",")
    pri = f"{nom.strip().split()[0] if nom.strip() else ''} {ap.strip()}".strip()
    return pri + (f" y {len(lista) - 1} más" if len(lista) > 1 else "")


def pag_iniciativas(inis):
    temas = sorted({i["tema"] for i in inis} - {"Otros"}) + ["Otros"]
    quienes = sorted({i["quien"] for i in inis if i["quien"]})
    opc = lambda xs: "".join(f'<option value="{e(x)}">{e(x)}</option>' for x in xs)
    estados = [("", "Todas")] + [(k, n) for k, (n, _) in EST.items() if k not in ("ret", "arch", "pleno")] + [("fin", "Archivada o retirada")]
    return pagina("Iniciativas", "Iniciativas", f"""
<h1 class="titulo">Todas las iniciativas</h1>
<p class="sub">{len(inis)} presentadas desde julio de 2026</p>
<script src="datos/iniciativas.js?v={VERSION}" defer></script>
<div id="iniciativas">
  <div class="herr suelta">
    <label class="oculto" for="qi">Buscar iniciativas</label>
    <input id="qi" type="search" class="buscar" placeholder="Busca un tema o un número, por ejemplo: universidades">
    <div class="selects">
      <label>Tema<select data-f="tema"><option value="">Todos</option>{opc(temas)}</select></label>
      <label>Cámara<select data-f="cam"><option value="">Ambas</option><option value="D">Diputados</option><option value="S">Senado</option></select></label>
      <label>Presentada por<select data-f="quien"><option value="">Todos</option>{opc(quienes)}</select></label>
    </div>
    {chips('estado', estados)}
  </div>
  <p class="cuenta nota"></p>
  <div class="tabla-caja"><table class="tabla-i"><thead><tr>
    <th data-o="9" aria-sort="descending"><button type="button">Presentada</button></th><th data-o="1"><button type="button">N.º</button></th>
    <th class="c-cam">Cámara</th><th>Título</th><th data-o="4"><button type="button">Estado</button></th>
    <th class="c-ext">Bancada</th><th class="c-ext">Comisión</th><th class="c-ext" data-o="5"><button type="button">Tema</button></th>
  </tr></thead><tbody id="lista-i"></tbody></table></div>
  <button type="button" class="mas" hidden>Mostrar más</button>
</div>
<div class="velo" hidden></div>
<section class="hoja" role="dialog" aria-modal="true" aria-labelledby="h-titulo" hidden tabindex="-1">
  <div class="hoja-cab"><span class="meta" id="h-meta"></span><button type="button" class="cerrar">Cerrar</button></div>
  <h2 id="h-titulo"></h2><div id="h-estado"></div>
  <div class="hoja-cuerpo" id="h-cuerpo"></div>
</section>""")


# ---------- congresistas y bancadas ----------

def pag_congresistas(cs):
    filas = "".join(f"""<a class="fila persona" href="c/{x['slug']}.html" data-camara="{x['camara']}" data-q="{e(x['nombre'].lower())}">
  <span class="con-logo">{foto(x)}{logo(x['bancada'], '', 'insignia')}</span><span class="crece"><b>{e(x['nombre'])}</b><span class="meta">{'Senado' if x['camara'] == 'senado' else 'Diputados'}{', por ' + e(x['distrito']) if x['distrito'] else ''}. {e(x['bancada'])}</span></span>
  <span class="dato"><b>{x['asist']}%</b>asistencia</span></a>""" for x in cs)
    return pagina("Congresistas", "Congresistas", f"""
<h1 class="titulo">Congresistas</h1>
<p class="sub">60 senadores y 130 diputados. Toca uno para ver cómo vota.</p>
<div class="filtrable">
  <div class="herr suelta"><label class="oculto" for="qc">Buscar congresistas</label>
  <input id="qc" type="search" class="buscar" placeholder="Busca por nombre o apellido">
  {chips('camara', [('', 'Todos'), ('senado', 'Senado'), ('diputados', 'Diputados')])}</div>
  <p class="cuenta nota" data-quien="congresistas"></p>
  <div class="tarjeta lista">{filas}</div>
</div>""")


def stats(items):
    return '<div class="stats">' + "".join(f'<div class="tarjeta"><b>{a}</b><span>{e(b)}</span></div>' for a, b in items) + "</div>"


def filas_inis(lista, pre, cats=True):
    if not lista:
        return '<p class="nota pad">Todavía no tiene iniciativas registradas.</p>'
    f = "".join(f"""<a class="fila" href="{pre}iniciativas.html#{i['k']}" data-v="{e(i['tema'])}">
  <b class="clamp2">{e(i['t'])}</b><span class="linea">{punto(i['e'])}<span class="meta">{e(extra or i['tema'])}</span><span class="meta fin">{i['f']}</span></span></a>"""
                for i, extra in lista)
    temas = sorted({i["tema"] for i, _ in lista})
    filtro = chips("v", [("", "Todas")] + [(t, t) for t in temas]) if cats and len(temas) > 1 else ""
    return f'<div class="tarjeta filtrable">{f"<div class=herr>{filtro}</div>" if filtro else ""}<div class="desliza">{f}</div></div>'


def pag_congresista(x):
    pre = "../"
    votos = []
    for v, k in x["votos"]:
        dist = v["id"] in x["distinto"]
        votos.append(f"""<a class="fila" href="{pre}v/{v['slug']}.html" data-v="{k}{' distinto' if dist else ''}">
  <span class="linea arriba"><b class="clamp2">{e(v['titulo'])}</b><span class="pill p-{k}">{ETIQ[k]}</span></span>
  <span class="linea"><span class="meta">{v['f']}, {'aprobada' if ganador(v) == 'si' else 'rechazada'}</span>{'<span class="ojo">Distinto a su bancada</span>' if dist else ''}</span></a>""")
    panel_votos = f"""<div class="tarjeta filtrable" data-modo="contiene">
  <div class="herr">{chips('v', [('', 'Todas'), ('no', 'En contra'), ('distinto', 'Distinto a su bancada'), ('aus', 'No votó')])}</div>
  <div class="desliza">{''.join(votos)}</div></div>"""
    cargo = "Senador(a)" if x["camara"] == "senado" else "Diputado(a)"
    return pagina(x["nombre"], "Congresistas", f"""
<div class="perfil">
  <span class="con-logo grande-f">{foto(x, pre, 'cara grande-c')}{logo(x['bancada'], pre, 'insignia')}</span>
  <div><h1 class="titulo">{e(x['nombre'])}</h1><a class="meta" href="{pre}b/{slug(x['bancada'])}.html">{cargo}{' por ' + e(x['distrito']) if x['distrito'] else ''}, {e(x['bancada'])}</a>
  {f'<a class="meta enl" href="{e(x["url"])}" target="_blank" rel="noopener">Su página en la web del Congreso</a>' if x['url'] else ''}</div>
</div>
{stats([(f"{x['asist']}%", "Asistencia a las votaciones"), (f"{x['con_banc']}%", "Votó igual que su bancada"), (len(x['inis']), "Iniciativas que firmó")])}
{pestanas('Detalle del congresista', [('votos', 'Cómo votó', panel_votos), ('ini', 'Iniciativas', filas_inis(x['inis'], pre))])}
<p class="nota">Cuenta {len(x['votos'])} votaciones del pleno con lista por congresista.</p>""", pre, desc=f"Cómo vota {x['nombre']}")


def pag_bancadas(bs):
    tarjetas = "".join(f"""<a class="tarjeta banca" href="b/{b['slug']}.html">{logo(n, '', 'grande')}<b>{e(n)}</b>
  <span class="meta">{sum(x['camara'] == 'senado' for x in b['miembros'])} senadores, {sum(x['camara'] == 'diputados' for x in b['miembros'])} diputados</span></a>"""
                       for n, b in bs.items())
    return pagina("Bancadas", "Bancadas", f"""
<h1 class="titulo">Bancadas</h1><p class="sub">Toca una para ver cómo vota y qué propone.</p>
<div class="rejilla">{tarjetas}</div>""")


def pag_bancada(b):
    pre = "../"
    distintas = []
    for v, bb, p, dividida in b["distintas"]:
        pres = sum(bb[k] for k in K)
        orden = sorted(K, key=lambda k: -bb[k])
        res = (f'<span class="res c-abst">Dividida: {bb[orden[0]]} a {bb[orden[1]]}</span>' if dividida
               else f'<span class="res c-{p}">{ETIQ[p]}: {bb[p]} de {pres}</span>')
        distintas.append(f'<a class="fila" href="{pre}v/{v["slug"]}.html"><span class="linea arriba"><b class="clamp2">{e(v["titulo"])}</b>{res}</span>{barra(bb, 5)}</a>')
    panel_dist = (f'<div class="tarjeta"><p class="nota pad">Votaciones en que la bancada votó distinto a la mayoría del pleno o se dividió.</p>'
                  f'<div class="desliza">{"".join(distintas)}</div></div>') if distintas else '<p class="nota pad">Ninguna por ahora.</p>'
    miembros = "".join(f'<a class="fila persona" href="{pre}c/{x["slug"]}.html">{foto(x, pre)}<span class="crece"><b>{e(x["nombre"])}</b>'
                       f'<span class="meta">{"Senado" if x["camara"] == "senado" else "Diputados"}</span></span><span class="dato"><b>{x["asist"]}%</b>asistencia</span></a>'
                       for x in sorted(b["miembros"], key=lambda x: (x["camara"] != "senado", x["apellidos"])))
    s = sum(x["camara"] == "senado" for x in b["miembros"])
    return pagina(b["nombre"], "Bancadas", f"""
<div class="perfil">{logo(b['nombre'], pre, 'grande')}
  <div><h1 class="titulo">{e(b['nombre'])}</h1><span class="meta">{s} senadores y {len(b['miembros']) - s} diputados</span></div></div>
{stats([(f"{b['cohesion']}%", "De cohesión en sus votaciones"), (len(b['inis']), "Iniciativas presentadas"), (f"{b['asist']}%", "Asistencia a las votaciones")])}
{pestanas('Detalle de la bancada', [('ini', 'Iniciativas', filas_inis([(i, '') for i in b['inis']], pre)), ('dist', 'Votó distinto', panel_dist),
                                    ('miembros', 'Integrantes', f'<div class="tarjeta desliza">{miembros}</div>')])}""", pre)


def pag_resumen(guion, hay_video):
    video = ('<video src="semana.mp4" poster="portada.jpg" controls playsinline preload="none"></video>'
             if hay_video else '<p class="nota">El video de esta semana todavía no está listo.</p>')
    temas = "".join(f'<li><b>{e(n["titular"])}</b><span class="meta">{e(n["importa"])}</span></li>' for n in guion["noticias"])
    return pagina("Resumen semanal", "Resumen semanal", f"""
<h1 class="titulo">Resumen semanal</h1><p class="sub">Semana del {e(guion['semana'].replace('–', 'al'))}. Un minuto para compartir en WhatsApp, TikTok o Instagram.</p>
<div class="dos"><div class="video">{video}</div><div><ol class="temas">{temas}</ol></div></div>""")


if __name__ == "__main__":
    vs, cs, inis = cargar()
    bs = estadisticas(cs, vs, inis)
    guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    por_id = {v["id"]: v for v in vs}
    # nombre tal como viene en el PDF -> congresista, para enlazar la tabla de cada votación
    from datos import llave
    por_nombre = {}
    for v in vs:
        for nombre, banc, k in v["filas"]:
            kk = llave(nombre.split(",")[0])
            x = next((x for x in cs if x["camara"] == v["camara"] and (kk.startswith(x["llave"]) or x["llave"].startswith(kk)) and x["bancada"] == banc), None)
            if x:
                por_nombre[(v["camara"], nombre)] = x

    SALIDA.mkdir(exist_ok=True)
    for p in SALIDA.iterdir():  # se vacía en vez de borrar: Windows no deja borrar una carpeta en uso
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for d in ("v", "b", "c", "datos"):
        (SALIDA / d).mkdir()
    shutil.copytree(AQUI / "logos", SALIDA / "logos", ignore=shutil.ignore_patterns("*.html"))
    shutil.copytree(AQUI / "fotos", SALIDA / "fotos", ignore=shutil.ignore_patterns("*.json"))
    shutil.copy(AQUI / "web/estilo.css", SALIDA / "estilo.css")
    shutil.copy(AQUI / "web/app.js", SALIDA / "app.js")
    hay_video = (AQUI / "out/semana.mp4").exists()
    if hay_video:
        shutil.copy(AQUI / "out/semana.mp4", SALIDA / "semana.mp4")
        shutil.copy(AQUI / "out/portada.jpg", SALIDA / "portada.jpg")

    escribir = lambda ruta, html: (SALIDA / ruta).write_text(html, encoding="utf-8")
    indice, fichas = datos_iniciativas(inis)
    escribir("datos/iniciativas.js", "window.INICIATIVAS=" + json.dumps(indice, ensure_ascii=False, separators=(",", ":")))
    escribir("datos/fichas.js", "window.FICHAS=" + json.dumps(fichas, ensure_ascii=False, separators=(",", ":")))
    escribir("index.html", inicio(vs, inis, guion, por_id, bs))
    escribir("votaciones.html", pag_votaciones(vs))
    escribir("iniciativas.html", pag_iniciativas(inis))
    escribir("congresistas.html", pag_congresistas(cs))
    escribir("bancadas.html", pag_bancadas(bs))
    escribir("resumen.html", pag_resumen(guion, hay_video))
    for v in vs:
        escribir(f"v/{v['slug']}.html", pag_votacion(v, por_nombre))
    for x in cs:
        escribir(f"c/{x['slug']}.html", pag_congresista(x))
    for b in bs.values():
        escribir(f"b/{b['slug']}.html", pag_bancada(b))
    print(f"{len(vs)} votaciones, {len(inis)} iniciativas, {len(cs)} congresistas, {len(bs)} bancadas -> {SALIDA}")
