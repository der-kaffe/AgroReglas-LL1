#!/usr/bin/env bash
# Capturas de pantalla reales de una terminal xterm ejecutando los comandos del proyecto.
#
# Se usa un servidor gráfico virtual (Xvfb), por lo que no abre ventanas en el escritorio.
# Cada comando se muestra precedido de "$" y seguido de su código de salida real.
# Requisitos (opcionales, solo para regenerar las imágenes): xvfb-run, xterm, ImageMagick.
#
#   bash herramientas/capturar_terminal.sh        # desde la raíz del proyecto
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SALIDA="$RAIZ/resultados/capturas"
mkdir -p "$SALIDA"
for programa in xvfb-run xterm import convert; do
  command -v "$programa" >/dev/null || { echo "Falta $programa; no se generan capturas." >&2; exit 2; }
done
TEMPORAL="$(mktemp -d)"
trap 'rm -rf "$TEMPORAL"' EXIT

# escena NOMBRE COLUMNAS FILAS COMANDO...   (TAMANO_FUENTE opcional, por defecto 9)
escena() {
  local nombre="$1" columnas="$2" filas="$3" fuente="${TAMANO_FUENTE:-9}"; shift 3
  local guion="$TEMPORAL/$nombre.sh"
  {
    echo 'cd "$1"; export LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1; tput civis'
    for comando in "$@"; do
      printf 'printf "\\033[1;32m$\\033[0m %%s\\n" %q\n' "$comando"
      printf '%s\nprintf "\\033[2m[código de salida: %%s]\\033[0m\\n\\n" "$?"\n' "$comando"
    done
    echo 'touch "$2"; sleep 30'
  } > "$guion"
  rm -f "$TEMPORAL/$nombre.listo"
  xvfb-run -a -s "-screen 0 2400x2400x24" bash -c '
    xterm -u8 -geometry '"${columnas}x${filas}"'+0+0 -fa "DejaVu Sans Mono" -fs '"$fuente"' -bg "#1e1e1e" \
          -fg "#e6e6e6" -e bash "'"$guion"'" "'"$RAIZ"'" "'"$TEMPORAL/$nombre.listo"'" &
    for _ in $(seq 1 200); do [ -e "'"$TEMPORAL/$nombre.listo"'" ] && break; sleep 0.1; done
    sleep 0.7
    import -window root "'"$TEMPORAL/$nombre.png"'"
    kill %1 2>/dev/null || true'
  convert "$TEMPORAL/$nombre.png" -trim +repage -bordercolor "#1e1e1e" -border 0 \
          -fuzz 0 -trim +repage -bordercolor "#1e1e1e" -border 14 "$SALIDA/$nombre.png"
  echo "  $SALIDA/$nombre.png"
}

echo "Capturas en $SALIDA:"
escena 01_entrada_valida 120 46 \
  'python3 -m agroreglas ejemplos/riego.agro --ast'
escena 02_errores_sintacticos 150 40 \
  'python3 -m agroreglas ejemplos/error.agro' \
  'python3 -m agroreglas ejemplos/invalidos/03_parentesis_sin_cerrar.agro' \
  'python3 -m agroreglas ejemplos/invalidos/07_regla_truncada.agro'
escena 03_lexico_limites_y_uso 150 40 \
  'python3 -m agroreglas ejemplos/invalidos/05_coma_entre_acciones.agro' \
  'python3 -m agroreglas ejemplos/invalidos/06_contenido_sobrante.agro' \
  'python3 -m agroreglas ejemplos/invalidos/08_vacio.agro' \
  'python3 -m agroreglas ejemplos/no_existe.agro'
escena 04_analisis_gramatica 112 98 \
  'python3 -m agroreglas --analisis'
TAMANO_FUENTE=8 escena 05_traza_ll1 182 34 \
  'python3 -m agroreglas -e "WHEN h < 1 THEN a b DURING 2;" --traza'
escena 06_pruebas_y_resultados 120 24 \
  'python3 -m unittest discover -s tests -q' \
  'python3 generar_resultados.py'
