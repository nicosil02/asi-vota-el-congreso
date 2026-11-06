"""Lee Base_legislativa (solo lectura) y arma los datos del sitio: votaciones,
congresistas, bancadas e iniciativas. Sin HTML aquí; eso va en sitio.py."""
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from semana import BANCADAS, DB

AQUI = Path(__file__).parent
K = ("si", "no", "abst")
MES = "ene feb mar abr may jun jul ago sep oct nov dic".split()
MESES = "enero febrero marzo abril mayo junio julio agosto setiembre octubre noviembre diciembre".split()
CORTO = {v: k for k, v in BANCADAS.items() if k != "OBRAS"}  # nombre -> sigla


def fecha(iso, larga=False):
    a, m, d = iso[:10].split("-")
    return f"{int(d)} de {MESES[int(m) - 1]}" if larga else f"{int(d)} {MES[int(m) - 1]}"


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def llave(s):
    """Apellidos sin tildes ni espacios: los PDF a veces pegan palabras ('CASTILLOTERRONES')."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z]", "", s)


def bancada_de(texto):
    """'Juntos por el Perú - Voces del Pueblo' -> 'Juntos por el Perú'."""
    return next((n for n in CORTO if (texto or "").startswith(n)), None)


# ---------- títulos legibles ----------

PROPIOS = [("tribunal constitucional", "Tribunal Constitucional"), ("código penal", "Código Penal"), ("código civil", "Código Civil"),
           ("código procesal penal", "Código Procesal Penal"), ("fenómeno el niño", "fenómeno El Niño"), ("ley universitaria", "Ley Universitaria"),
           ("ley general de salud", "Ley General de Salud"), ("banco central de reserva", "Banco Central de Reserva"),
           ("oficina nacional de procesos electorales", "Oficina Nacional de Procesos Electorales"), ("poder ejecutivo", "Poder Ejecutivo"),
           ("poder judicial", "Poder Judicial"), ("ministerio público", "Ministerio Público"), ("armada de chile", "Armada de Chile"),
           ("fuerzas armadas", "Fuerzas Armadas"), ("policía nacional", "Policía Nacional"), ("el peruano", "El Peruano")]
SIGLAS = r"\b(cas|eps|sunarp|sunat|essalud|onpe|jne|reniec|mype|mypes|bcr|vraem|mef|minsa|minedu|sutran|ositran|osiptel|indecopi)\b"
LUGARES = r"\b(perú|lima|callao|piura|sullana|paita|talara|cusco|puno|arequipa|loreto|junín|huancayo|satipo|ayacucho|cajamarca|tacna|tumbes|ica|áncash|chile|república|congreso|senado)\b"


def oracion(t):
    """Texto oficial en mayúsculas -> oración legible. ponytail: reglas fijas; un modelo lo haría mejor (paso 3)."""
    t = re.sub(r"\s+", " ", t or "").strip().rstrip(".")
    t = re.sub(r"^(PROPOSICI[OÓ]N|PROYECTO)( DE RESOLUCI[OÓ]N)? LEGISLATIVA( DEL CONGRESO| DEL SENADO| DE LA C[AÁ]MARA DE DIPUTADOS)?( QUE| DE| POR LA QUE SE)?\s*", "", t, flags=re.I)
    t = re.sub(r"^LEY QUE ", "", t, flags=re.I)
    if not t:
        return ""
    t = t.lower()
    for a, b in PROPIOS:
        t = t.replace(a, b)
    t = re.sub(r"\b(ley|decreto legislativo|decreto supremo|decreto de urgencia|resolución legislativa)( n\.?[°º]?)? ?(?=\d)", lambda m: m.group(1).capitalize() + " ", t)
    t = re.sub(SIGLAS, lambda m: m.group(1).upper(), t)
    t = re.sub(LUGARES, lambda m: m.group(1).capitalize(), t)
    t = re.sub(r"\b(\d+-)([a-z])\b", lambda m: m.group(1) + m.group(2).upper(), t)
    return t[0].upper() + t[1:]


TEMAS = {"Educación": "Educación", "Salud": "Salud", "Farma": "Salud", "Trabajo": "Trabajo y pensiones", "Pensiones": "Trabajo y pensiones",
         "Tributos": "Economía", "Banca": "Economía", "Comercio": "Economía", "Mype": "Economía", "Informalidad": "Economía",
         "Consumo masivo": "Economía", "Control de la actividad privada": "Economía", "Horeca": "Economía",
         "Transporte": "Obras y servicios", "Infraestructura": "Obras y servicios", "Construcción": "Obras y servicios",
         "Telecomunicaciones": "Obras y servicios", "Transporte y telecomunicaciones": "Obras y servicios", "Saneamiento": "Obras y servicios",
         "Inmobiliario": "Obras y servicios", "Tecnología": "Obras y servicios", "Ambiente": "Ambiente y recursos", "Energía": "Ambiente y recursos",
         "Minería": "Ambiente y recursos", "Energía y minas": "Ambiente y recursos", "Pesca": "Ambiente y recursos", "Agricultura": "Agro"}
PALABRAS = [("Justicia", r"penal|delito|prescripci|amnist|extinci[oó]n de dominio|judicial|fiscal[ií]a|c[aá]rcel|penitenciar|corrupci"),
            ("Seguridad", r"polic[ií]a|seguridad ciudadana|crimen|delincuencia|drones|armas|munici|fuerzas armadas|naval|militar|emergencia"),
            ("Estado y elecciones", r"reglamento del (congreso|senado)|elecci|electoral|onpe|jne|tribunal constitucional|president|contralor|gobiernos? (regional|local)|municipal|ministr"),
            ("Salud", r"salud|m[eé]dic|hospital|enfermer"), ("Educación", r"educaci|universi|colegio|docente|escolar"),
            ("Sociedad", r"d[ií]a nacional|semana nacional|patrimonio cultural|declara de inter[eé]s|familia|mujer|ni[ñn]|pueblos ind[ií]genas|discapacidad")]


def tema(tema_db, titulo):
    """Temas para el público. Los de la base están pensados para clientes ('Horeca', 'Farma')."""
    t = (titulo or "").lower()
    for nombre, patron in PALABRAS[:3]:  # justicia, seguridad y Estado pesan más que el sector si lo dice al inicio
        m = re.search(patron, t)
        if m and (tema_db in (None, "", "Otros") or m.start() < 60):
            return nombre
    if tema_db in TEMAS:
        return TEMAS[tema_db]
    return next((n for n, p in PALABRAS[3:] if re.search(p, t)), "Otros")


ESTADOS = [("PRESENTADO", "pres"), ("ACTUALIZADA", "pres"), ("EN COMISI", "com"), ("CON DICTAMEN", "dict"), ("EN AGENDA", "pleno"),
           ("EN DEBATE", "pleno"), ("EXPEDIENTE", "sen"), ("PROPUESTA LEGISLATIVA APROBADA", "sen"), ("APROBADO", "apr"), ("AUT", "apr"),
           ("PUBLICADA", "ley"), ("RETIRADO", "ret"), ("ARCHIVADO", "arch"), ("DECRETO", "arch")]


def estado(e):
    E = (e or "").upper()
    return next((c for p, c in ESTADOS if E.startswith(p)), "com")


# ---------- trámite y documentos ----------

def paso(e, com, det):
    E = (e or "").upper()
    if E.startswith("PRESENTADO"): return "Se presenta"
    if E.startswith("EN COMISI"):
        return (f"Pasa a la Comisión {com}" if com.startswith("Bicameral") else f"Pasa a la Comisión de {com}") if com else "Pasa a comisión"
    if E.startswith("CON DICTAMEN"):
        m = re.match(r"(POR UNANIMIDAD|EN MAYOR[IÍ]A)", det or "")
        return "Dictamen de la comisión" + ((", por unanimidad" if "UNANIM" in m.group(1) else ", en mayoría") if m else "")
    if "AGENDA" in E: return "Entra a la agenda del pleno"
    if "DEBATE" in E: return "Se debate en el pleno"
    if E.startswith("PROPUESTA LEGISLATIVA APROBADA"): return "Diputados envía el texto aprobado"
    if E.startswith("APROBADO"): return "Aprobada en el pleno"
    if E.startswith("EXPEDIENTE"): return "Pasa al Senado"
    if E.startswith("AUT"): return "Se firma el texto final (autógrafa)"
    if E.startswith("PUBLICADA"):
        m = re.search(r"(RESOLUCI[OÓ]N LEGISLATIVA|LEY) N[°º] ?(\d+)", det or "")
        return f"Se publica como {'Ley' if m.group(1) == 'LEY' else 'Resolución Legislativa'} {m.group(2)}" if m else "Se publica en El Peruano"
    if E.startswith("ARCHIVADO"): return "Se archiva"
    if E.startswith("RETIRADO"): return "La retira su autor"
    return oracion(e)


def doc(d, p):
    D = (d or "").upper()
    for k, v in [("EXP. MOT", "Exposición de motivos"), ("RETIRO", "Retiro de firma"), ("MEMORANDO", "Memorando"), ("REPORTE", "Reporte del expediente"),
                 ("OFICIO", "Oficio"), ("DECRETO", "Decreto de trámite"), ("ANEXO", "Anexo"), ("ACTA", "Acta"), ("ASI", "Asistencia y votación"), ("CARGO", "Autógrafa")]:
        if k in D: return v
    if D.startswith("TS"): return "Texto sustitutorio"
    if "DICTAMEN" in D or p.startswith("Dictamen"): return "Dictamen"
    if p.startswith("Se publica"): return "Norma publicada"
    if p.startswith("Se firma"): return "Autógrafa"
    if p.startswith(("Aprobada", "Diputados envía")): return "Texto aprobado"
    if p.startswith(("Se presenta", "Pasa a")): return "Texto del proyecto"
    return "Documento"


def tramite(con, pid, num, tipo):
    pasos = []
    for sid, f, e, cm, det in con.execute(
            "select seguimiento_pley_id, fecha, estado, comisiones, detalle from seguimientos where per_par_id=? and pley_num=? and cod_tipo_parl=? order by fecha, seguimiento_pley_id",
            (pid, num, tipo)):
        nom = paso(e, cm, det)
        if not pasos or pasos[-1]["p"] != nom:
            pasos.append({"p": nom, "f": fecha(f), "d": []})
        vistos = {x["n"] for x in pasos[-1]["d"]}
        for desc, url in con.execute("select descripcion, url from archivos where seguimiento_pley_id=? order by proyecto_archivo_id", (sid,)):
            n = doc(desc, nom)
            if n not in vistos and url:
                pasos[-1]["d"].append({"n": n, "u": url})
                vistos.add(n)
    return pasos


# ---------- carga ----------

REF_PL = re.compile(r"(?:PROPOSICI[OÓ]N(?:ES)?\s*LEGISLATIVAS?|PROYECTOS?\s*DE\s*(?:LEY|RESOLUCI[OÓ]N\s*LEGISLATIVA)(?:\s*DEL\s*SENADO)?)"
                    r"\s*((?:\d+(?:-\d{4}-\d{4}-[A-Z])?(?:\s*,\s*|\s+Y\s+)?)+)")


def citadas(asunto, cam):
    """Iniciativas que nombra el asunto de una votación: [(tipo, num)]. Sin letra, se asume la cámara que vota."""
    out = []
    for grupo in REF_PL.findall(asunto or ""):
        for num, letra in re.findall(r"(\d+)(?:-\d{4}-\d{4}-([A-Z]))?", grupo):
            out.append((letra or ("S" if cam == "senado" else "D"), int(num)))
    return out


def es_tramite(asunto):
    return bool(re.search(r"N[OÓ]MINA|CUARTO INTERMEDIO|RECONSIDERACI|DISPENSA|INTEGRANTES|CONFORMACI[OÓ]N|ADMISI[OÓ]N|CUESTI[OÓ]N PREVIA|AMPLIACI[OÓ]N DE AGENDA",
                          (asunto or "").upper()))


def cargar():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    agendas = dict(((c, f), u) for c, f, u in con.execute("select camara, fecha, pdf_url from pleno_agenda_pdf"))
    unicos = lambda xs: list({id(x): x for x in xs if x}.values())
    titulos = json.loads((AQUI / "titulos.json").read_text(encoding="utf-8"))

    # Iniciativas del periodo 2026-2031
    inis, por_pl = [], {}
    for pid, tipo, num, pl, f, est, tema_db, grupo, prop, autores, tit, url in con.execute(
            """select per_par_id, cod_tipo_parl, pley_num, proyecto_ley, fec_presentacion, estado, tema, grupo_parlamentario,
                      proponente, autores_raw, titulo, url_portal
               from proyectos where proyecto_ley like '%2026-2031%' order by fec_presentacion desc, pley_num desc"""):
        banc = bancada_de(grupo)
        com = [r[0] for r in con.execute("select nombre from proyecto_comision where per_par_id=? and pley_num=? and cod_tipo_parl=?", (pid, num, tipo))]
        pasos = tramite(con, pid, num, tipo)
        lista_aut = [a.strip() for a in (autores or "").split(";") if a.strip()]
        quien = banc or (grupo if grupo and grupo != "" else (prop or "").title().replace(" - Actualización", ""))
        i = {"k": f"{tipo}{num}", "num": num, "cam": tipo, "f": fecha(f), "iso": f[:10], "e": estado(est), "tema": tema(tema_db, tit),
             "quien": quien, "sig": CORTO.get(banc, ""), "t": oracion(tit),
             "com": ", ".join(com) or ("Todavía no se asigna" if len(pasos) <= 1 else "No pasó a comisión"),
             "aut": lista_aut, "url": url or "", "tram": pasos}
        inis.append(i)
        por_pl[(tipo, num)] = i

    # Votaciones
    nominal = defaultdict(list)
    for vid, nombre, sigla, voto in con.execute("select votacion_id, congresista, coalesce(bancada, '?'), voto from voto_pleno_nominal"):
        nominal[vid].append((nombre, BANCADAS.get(sigla, sigla), voto))
    vs = []
    for vid, cam, f, hora, asunto, tipo_pl, num_pl, si, no, abst, cuadra, pdf in con.execute(
            """select id, camara, fecha, hora, asunto, pl_cod_tipo_parl, pley_num, si, no, abst, cuadra, pdf_url
               from votacion_pleno where tipo = 'votacion' order by fecha desc, hora desc"""):
        t = titulos.get(vid, {})
        bancs = defaultdict(lambda: dict.fromkeys(K + ("aus",), 0))
        filas = []
        # el lector a veces lee dos veces la lista (una con el nombre cortado): una fila por persona, la de nombre más largo
        unicas = {}
        for nombre, banc, voto in nominal[vid]:
            c = (banc, llave(nombre.split(",")[0])[:10])
            if len(nombre) > len(unicas.get(c, ("",))[0]):
                unicas[c] = (nombre, banc, voto)
        if True:  # vale el desglose si suma igual que el acta, aunque la base no lo marque como cuadrado
            for nombre, banc, voto in unicas.values():
                k = voto.lower() if voto in ("SI", "NO", "ABST") else "aus"
                bancs[banc][k] += 1
                filas.append((nombre, banc, k))
        bancadas = sorted(bancs.items(), key=lambda kv: -sum(kv[1].values()))
        # si la lista por congresista no suma igual que el acta se muestra igual, con un aviso de cuánto difiere
        lista = tuple(sum(b[k] for _, b in bancadas) for k in K)
        difiere = lista if bancadas and lista != (si, no, abst) else None
        vs.append({"id": vid, "slug": slug(vid), "camara": cam, "f": fecha(f), "fl": fecha(f, True), "iso": f, "asunto": asunto,
                   "titulo": t.get("t") or oracion(asunto), "resumen": t.get("r"), "tramite": t.get("tramite", es_tramite(asunto) if not t else False),
                   "si": si, "no": no, "abst": abst, "pdf": pdf, "docs": t.get("docs", []), "bancadas": bancadas, "filas": filas, "difiere": difiere,
                   "inis": unicos([por_pl.get((tipo_pl, num_pl))] + [por_pl.get(c) or por_pl.get(("C", c[1])) for c in citadas(asunto, cam)]),
                   "agenda": agendas.get((cam, f))})

    congresistas = unir_congresistas(vs, con)
    return vs, congresistas, inis


# cómo se dice "senador por ..." (la web da el distrito sin tildes)
DISTRITOS = {"ancash": "Áncash", "apurimac": "Apurímac", "huanuco": "Huánuco", "junin": "Junín", "san-martin": "San Martín",
             "la-libertad": "La Libertad", "lima-metropolitana": "Lima Metropolitana", "lima-provincias": "Lima Provincias",
             "nacional-distrito-unico": "el distrito nacional", "peruanos-en-el-exterior": "los peruanos en el extranjero",
             "peruanos-en-el-extranjero": "los peruanos en el extranjero"}


def unir_congresistas(vs, con):
    """Un congresista por persona aunque el PDF lo escriba de varias formas."""
    variantes = defaultdict(Counter)  # (camara, llave de apellidos) -> formas vistas
    banc_de = defaultdict(Counter)
    for v in vs:
        for nombre, banc, k in v["filas"]:
            ap = re.sub(r"\s+COPIA$|\s+RELATORIA$", "", nombre.split(",")[0].strip())
            c = (v["camara"], llave(" ".join(ap.split()[:2])))
            variantes[c][nombre] += 1
            banc_de[c][banc] += 1
    # solo cuentan como persona las llaves con dos apellidos; "VELÁSQUEZ" a secas es un nombre cortado
    canon = sorted([c for c, n in variantes.items() if sum(n.values()) >= 5 and any(len(f.split(",")[0].split()) >= 2 for f in variantes[c])],
                   key=lambda c: -len(c[1]))
    # "ARISTAARBILDOJOSE" es la misma persona que "ARISTAARBILDO" con el nombre pegado
    canon = [c for c in canon if not any(o != c and o[0] == c[0] and c[1].startswith(o[1]) for o in canon)]

    def quien(cam, nombre, banc):
        k = llave(nombre.split(",")[0])
        ok = [c for c in canon if c[0] == cam and (k.startswith(c[1]) or c[1].startswith(k))]
        if len(ok) > 1:  # apellido cortado que calza con varios: decide la bancada
            ok = [c for c in ok if k.startswith(c[1])] or [c for c in ok if banc_de[c].most_common(1)[0][0] == banc]
        return ok[0] if len(ok) == 1 else None

    # nombres completos desde los autores de iniciativas: "Castillo Terrones, José Mercedes"
    completos = {}
    for (autores,) in con.execute("select autores_raw from proyectos where proyecto_ley like '%2026-2031%' and autores_raw is not null"):
        for a in autores.split(";"):
            ap, _, nom = a.strip().partition(",")
            if nom:
                completos.setdefault(llave(ap), (ap.strip(), nom.strip()))

    ruta = AQUI / "fotos" / "congresistas" / "personas.json"
    oficiales = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []
    for o in oficiales:
        o["llave"] = llave(o["nombre"].split(",")[0])

    def oficial(cam, k):
        ok = [o for o in oficiales if o["camara"] == cam and (o["llave"].startswith(k) or k.startswith(o["llave"]))]
        return ok[0] if len(ok) == 1 else None

    cs = {}
    for v in vs:
        for nombre, banc, k in v["filas"]:
            c = quien(v["camara"], nombre, banc)
            if not c:
                continue
            x = cs.setdefault(c, {"camara": c[0], "llave": c[1], "votos": [], "bancadas": Counter()})
            x["votos"].append((v, k))
            x["bancadas"][banc] += 1
    for c, x in cs.items():
        forma = max(variantes[c], key=lambda n: ("," in n, len(n.split(",")[0].split()), variantes[c][n]))  # la mejor escrita
        ap, _, nom = forma.partition(",")
        ap = re.sub(r"\s+COPIA$", "", ap.strip())
        full = next((completos[k] for k in completos if k.startswith(llave(ap)) or llave(ap).startswith(k) and len(k) > 8), None)
        if full:
            ap, nom = full
            nom = nom.split()[0]
        x["nombre"] = f"{nom.strip().title()} {ap.title()}".strip() if nom else ap.title()
        x["nombre"] = re.sub(r"\b(De|Del|La|Los|Las|Y)\b", lambda m: m.group(1).lower(), x["nombre"])
        x["apellidos"] = ap.title()
        x["foto"] = x["url"] = x["distrito"] = None
        of = oficial(x["camara"], llave(ap))
        if of:  # la web del Congreso tiene el nombre bien escrito y la foto
            ap, _, nom = of["nombre"].partition(",")
            x["nombre"] = f"{nom.split()[0]} {ap.strip()}" if nom.strip() else ap.strip()
            x["apellidos"] = ap.strip()
            x["foto"], x["url"] = of["foto"], of["url"]
            x["distrito"] = DISTRITOS.get(of["distrito"]) or of["distrito"].replace("-", " ").title().replace(" De ", " de ")
        x["bancada"] = x["bancadas"].most_common(1)[0][0]
        x["slug"] = slug(f"{x['camara']} {x['nombre']}")
        x["votos"].sort(key=lambda vk: (vk[0]["iso"], vk[0]["id"]), reverse=True)
    return sorted(cs.values(), key=lambda x: llave(x["apellidos"]))


def postura(b):
    return max(K, key=lambda k: b[k]) if any(b[k] for k in K) else "aus"


def ganador(v):
    return "si" if v["si"] > v["no"] else "no"


def estadisticas(cs, vs, inis):
    """Asistencia, voto con la bancada e iniciativas, por congresista y por bancada."""
    mayoria = {(v["id"], n): postura(b) for v in vs for n, b in v["bancadas"]}
    for x in cs:
        votaron = [(v, k) for v, k in x["votos"] if k != "aus"]
        x["asist"] = round(100 * len(votaron) / len(x["votos"])) if x["votos"] else 0
        iguales = [k == mayoria.get((v["id"], x["bancada"])) for v, k in votaron]
        x["con_banc"] = round(100 * sum(iguales) / len(iguales)) if iguales else 0
        x["distinto"] = {v["id"] for v, k in votaron if k != mayoria.get((v["id"], x["bancada"]))}
        x["inis"] = []
    # iniciativas por autor (solo de su cámara: S = Senado, D = Diputados)
    por_cam = defaultdict(list)
    for x in cs:
        por_cam["S" if x["camara"] == "senado" else "D"].append(x)
    for i in inis:
        for pos, a in enumerate(i["aut"]):
            ka = llave(a.split(",")[0])
            x = next((x for x in por_cam.get(i["cam"], []) if ka.startswith(x["llave"])), None)
            if x:
                x["inis"].append((i, "Autor principal" if pos == 0 else "Coautor"))

    bs = {}
    for n in CORTO:
        miembros = [x for x in cs if x["bancada"] == n]
        if not miembros:
            continue
        cohes, distintas = [], []
        for v in vs:
            b = dict(v["bancadas"]).get(n)
            if not b or v["tramite"]:
                continue
            pres = sum(b[k] for k in K)
            if pres:
                cohes.append(max(b[k] for k in K) / pres)
            p = postura(b)
            minor = sorted((b[k] for k in K), reverse=True)[1]
            if pres and (p != ganador(v) or minor >= max(2, 0.2 * pres)):
                distintas.append((v, b, p, minor >= max(2, 0.2 * pres)))
        bs[n] = {"nombre": n, "slug": slug(n), "sig": CORTO[n], "miembros": miembros,
                 "cohesion": round(100 * sum(cohes) / len(cohes)) if cohes else 0,
                 "asist": round(sum(x["asist"] for x in miembros) / len(miembros)),
                 "inis": [i for i in inis if i["sig"] == CORTO[n]], "distintas": distintas}
    return dict(sorted(bs.items(), key=lambda kv: -len(kv[1]["miembros"])))


if __name__ == "__main__":
    vs, cs, inis = cargar()
    bs = estadisticas(cs, vs, inis)
    print(len(vs), "votaciones,", len(cs), "congresistas,", len(inis), "iniciativas")
    assert oracion("PROPOSICIÓN LEGISLATIVA QUE MODIFICA LA LEY 30220, LEY UNIVERSITARIA") == "Modifica la Ley 30220, Ley Universitaria"
    assert estado("Publicada en el Diario Oficial El Peruano") == "ley" and estado("AUTÓGRAFA") == "apr"
    print(Counter(x["camara"] for x in cs))
    for x in cs[:3] + [x for x in cs if "Castillo" in x["nombre"]]:
        print(x["nombre"], x["camara"], x["bancada"], len(x["votos"]), x["asist"], x["con_banc"], len(x["inis"]))
    for n, b in bs.items():
        print(n, len(b["miembros"]), b["cohesion"], b["asist"], len(b["inis"]), len(b["distintas"]))
    print(Counter(i["tema"] for i in inis).most_common())
