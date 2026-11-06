# Así vota el Congreso

Sitio público y gratuito para seguir las votaciones del Congreso del Perú: https://nicosil02.github.io/asi-vota-el-congreso/

Se arma solo dos veces al día con GitHub Actions (`.github/workflows/sitio.yml`):

1. Trae la base propia de la rama `datos` (la primera vez la arma `bajar_base.py`).
2. La actualiza con los lectores de `lectores/` (copia de los de Base_legislativa): iniciativas, agendas, votaciones del Pleno y OCR de las actas escaneadas.
3. Guarda la base en `datos`, genera el sitio con `sitio.py` y lo publica en la rama `gh-pages`.
