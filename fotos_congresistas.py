"""Baja de las webs oficiales del Senado y de Diputados la lista de congresistas con su foto.
Deja fotos/congresistas/<camara>-<slug>.jpg (240 px) y fotos/congresistas/personas.json.
Uso: python fotos_congresistas.py   (solo hace falta cuando cambia la composición)
"""
import io
import json
import re
import time
import urllib.request
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).parent
DESTINO = AQUI / "fotos" / "congresistas"
FUENTES = {"senado": "https://senado.congreso.gob.pe/wp-json/wp/v2/senador",
           "diputados": "https://diputados.congreso.gob.pe/wp-json/wp/v2/diputado"}


def pedir(url, intentos=4):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (asi-vota-el-congreso)"})
    for n in range(intentos):  # las webs del Congreso cortan conexiones a ratos
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read()
        except OSError:
            if n == intentos - 1:
                raise
            time.sleep(3 * (n + 1))


def clase(lista, prefijo):
    return next((c[len(prefijo):] for c in lista if c.startswith(prefijo)), "")


if __name__ == "__main__":
    DESTINO.mkdir(parents=True, exist_ok=True)
    personas = []
    for cam, base in FUENTES.items():
        pagina = 1
        while True:
            lote = json.loads(pedir(f"{base}?per_page=100&page={pagina}&_embed=wp:featuredmedia"))
            for x in lote:
                media = (x.get("_embedded") or {}).get("wp:featuredmedia") or [{}]
                foto = f"{cam}-{x['slug']}.jpg"
                if media[0].get("source_url") and not (DESTINO / foto).exists():
                    try:
                        img = Image.open(io.BytesIO(pedir(media[0]["source_url"]))).convert("RGB")
                        img.thumbnail((240, 300))
                        img.save(DESTINO / foto, quality=82)
                    except OSError as err:  # sin foto no se cae todo: queda la inicial
                        print("sin foto:", x["slug"], err)
                personas.append({"camara": cam, "nombre": re.sub(r"<[^>]+>", "", x["title"]["rendered"]).strip(),
                                 "foto": foto if (DESTINO / foto).exists() else None, "url": x["link"],
                                 "distrito": clase(x["class_list"], "distrito_electoral-"),
                                 "genero": clase(x["class_list"], "genero-")})
            if len(lote) < 100:
                break
            pagina += 1
    (DESTINO / "personas.json").write_text(json.dumps(personas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(personas), "congresistas;", sum(bool(p["foto"]) for p in personas), "con foto")
