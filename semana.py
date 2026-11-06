"""Completa guion.json con el voto por bancada de cada noticia, desde Base_legislativa.

Cada noticia con "votacion_id" (id de votacion_pleno) recibe "voto": el total del
acta y, si el voto nominal cuadra con el acta, filas por bancada con sí / no /
abstención. Ausentes, licencias y sin respuesta no cuentan.
Uso: python semana.py
"""
import json
import os
import sqlite3
from pathlib import Path

DB = Path(os.environ.get("CONGRESO_DB") or Path.home() / "Documents/GitHub/Base_legislativa/proyectos.db")
GUION = Path(__file__).parent / "guion.json"
BANCADAS = {
    "FP": "Fuerza Popular", "JP": "Juntos por el Perú", "RP": "Renovación Popular",
    "AN": "Ahora Nación", "PBG": "Partido del Buen Gobierno", "PCO": "Partido Cívico Obras", "OBRAS": "Partido Cívico Obras",
}


def voto(con, votacion_id):
    si, no, abst, cuadra = con.execute(
        "select si, no, abst, cuadra from votacion_pleno where id = ?", (votacion_id,)).fetchone()
    # cuadra = 0: la lectura del PDF nominal no cierra; solo se usa el total del acta.
    bancadas = por_bancada(con, votacion_id, (si, no, abst)) if cuadra else None
    return {"si": si, "no": no, "abst": abst, "bancadas": bancadas}


def por_bancada(con, votacion_id, acta):
    filas = {}
    for sigla, voto, n in con.execute(
        """select coalesce(bancada, '?'), voto, count(*) from voto_pleno_nominal
           where votacion_id = ? and voto in ('SI', 'NO', 'ABST') group by 1, 2""",
        (votacion_id,),
    ):
        nombre = BANCADAS.get(sigla, sigla)  # OBRAS y PCO son la misma bancada
        f = filas.setdefault(nombre, {"bancada": nombre, "si": 0, "no": 0, "abst": 0})
        f[{"SI": "si", "NO": "no", "ABST": "abst"}[voto]] += n
    if not filas:
        raise SystemExit(f"Sin voto nominal para {votacion_id}")
    suma = tuple(sum(f[k] for f in filas.values()) for k in ("si", "no", "abst"))
    assert suma == acta, f"{votacion_id}: nominal {suma} no cuadra con el acta {acta}"
    return sorted(filas.values(), key=lambda f: -(f["si"] + f["no"] + f["abst"]))


if __name__ == "__main__":
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    guion = json.loads(GUION.read_text(encoding="utf-8"))
    for n in guion["noticias"]:
        n["voto"] = voto(con, n["votacion_id"]) if n.get("votacion_id") else None
    GUION.write_text(json.dumps(guion, ensure_ascii=False, indent=2), encoding="utf-8")
    print("guion.json actualizado")
