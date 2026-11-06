"""Arranque único de la base propia (base.db): copia, desde la base pública de la rama `datos`
de Base_legislativa, solo las tablas que usan los lectores de este repo. Después la base vive
en la rama `datos` de este repo y la actualizan los lectores de lectores/. Uso: python bajar_base.py
"""
import gzip
import sqlite3
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/nicosil02/Base_legislativa/datos/data/proyectos.{}.db.gz"
TABLAS = ["proyectos", "seguimientos", "archivos", "proyecto_comision", "comisiones", "sync_runs",
          "pleno_agenda_pdf", "votacion_pleno", "voto_pleno_nominal", "pleno_votacion_pdf", "pleno_votacion_ocr"]
AQUI = Path(__file__).parent
DESTINO = AQUI / "base.db"

DESTINO.unlink(missing_ok=True)
con = sqlite3.connect(DESTINO)
for parte in ("base", "votaciones"):
    tmp = AQUI / f"_{parte}.db"
    with urllib.request.urlopen(URL.format(parte), timeout=180) as r:
        tmp.write_bytes(gzip.decompress(r.read()))
    con.execute("ATTACH ? AS o", (str(tmp),))
    objetos = con.execute("SELECT type, name, tbl_name, sql FROM o.sqlite_master WHERE sql IS NOT NULL").fetchall()
    for tipo, nombre, tabla, sql in objetos:  # tablas con su esquema e índices: los lectores hacen upsert
        if tabla in TABLAS and tipo == "table":
            con.execute(f'DROP TABLE IF EXISTS main."{nombre}"')
            con.execute(sql)
            con.execute(f'INSERT INTO main."{nombre}" SELECT * FROM o."{nombre}"')
    for tipo, nombre, tabla, sql in objetos:
        if tabla in TABLAS and tipo == "index":
            con.execute(sql.replace("CREATE INDEX", "CREATE INDEX IF NOT EXISTS").replace("CREATE UNIQUE INDEX", "CREATE UNIQUE INDEX IF NOT EXISTS"))
    con.commit()
    con.execute("DETACH o")
    tmp.unlink()
con.execute("VACUUM")
print(con.execute("SELECT count(*) FROM votacion_pleno").fetchone()[0], "votaciones;",
      con.execute("SELECT count(*) FROM proyectos").fetchone()[0], "proyectos ->", DESTINO)
