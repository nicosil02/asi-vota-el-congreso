"""Baja la base pública (rama `datos` de Base_legislativa, solo lectura) y la deja en base.db.
Une la parte general con la de votaciones. Uso: python bajar_base.py
"""
import gzip
import sqlite3
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/nicosil02/Base_legislativa/datos/data/proyectos.{}.db.gz"
AQUI = Path(__file__).parent

for parte in ("base", "votaciones"):
    with urllib.request.urlopen(URL.format(parte), timeout=120) as r:
        (AQUI / f"{parte}.db").write_bytes(gzip.decompress(r.read()))

con = sqlite3.connect(AQUI / "base.db")
con.execute("ATTACH ? AS v", (str(AQUI / "votaciones.db"),))
for (t,) in con.execute("SELECT name FROM v.sqlite_master WHERE type='table'").fetchall():
    con.execute(f'DROP TABLE IF EXISTS main."{t}"')
    con.execute(f'CREATE TABLE main."{t}" AS SELECT * FROM v."{t}"')
con.commit()
print(con.execute("SELECT count(*) FROM votacion_pleno").fetchone()[0], "votaciones en la base")
