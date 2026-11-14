# AgroReglas — analizador sintáctico LL(1)

Proyecto de **Teoría de la Computación (INFO1148)**, Universidad Católica de Temuco, Ingeniería Civil Informática.

AgroReglas es un lenguaje de dominio específico (DSL) para describir reglas de automatización del riego agrícola.
Este proyecto define su gramática, la analiza (recursión izquierda, factorización, ambigüedad, FIRST, FOLLOW y tabla
LL(1)) e implementa a mano un **parser predictivo dirigido por tabla** que acepta o rechaza programas, informa errores
localizados y construye un **árbol sintáctico concreto** y un **AST**.

```text
WHEN humedad < 30 AND NOT (lluvia == TRUE OR viento > 40)
THEN regar sector_norte DURING 15 AND activar alarma;
```

> El proyecto solo **reconoce la sintaxis**: no ejecuta reglas, no valida semántica (sensores, tipos, unidades) y no
> controla equipos reales.

- Integrantes: Juan Claudio Cárdenas Uribe, Juan Esteban Llanca Hernández, Bayron Rodrigo Flores Riquelme.
- Docente: Prof. M. Lévano.
- Fecha: 14 de noviembre de 2026.
- Informe: [`documentacion/Informe_AgroReglas.pdf`](documentacion/Informe_AgroReglas.pdf) (fuente LaTeX en el mismo directorio).

## Requisitos

| Para | Necesita |
|---|---|
| Parser, consola, pruebas y `generar_resultados.py` | **Python 3.10 o superior**, solo biblioteca estándar (verificado con Python 3.13.5) |
| Dibujar los árboles en PNG/PDF (opcional) | Graphviz (`dot`) |
| Abrir o reejecutar el notebook (opcional) | Jupyter, o `pip install nbclient nbformat ipykernel` |
| Recompilar el informe (opcional) | `pdflatex` con babel (español), geometry, longtable, colortbl, graphicx, hyperref, fancyhdr, verbatim, amssymb, lmodern |
| Regenerar las capturas de terminal (opcional) | `xvfb-run`, `xterm`, ImageMagick |

No se usa ningún generador de parsers ni biblioteca que resuelva el análisis: FIRST, FOLLOW, la tabla LL(1) y el
parser están escritos en este repositorio.

## Uso rápido

Todos los comandos se ejecutan desde la raíz del proyecto (la carpeta que contiene `agroreglas/`).

```sh
python3 -m agroreglas ejemplos/riego.agro                  # analiza un archivo
python3 -m agroreglas ejemplos/riego.agro --ast            # ... y muestra el AST
python3 -m agroreglas ejemplos/riego.agro --arbol          # ... y el árbol sintáctico concreto
python3 -m agroreglas -e "WHEN h < 1 THEN regar sur;"      # analiza un texto
python3 -m agroreglas - < ejemplos/riego.agro              # analiza la entrada estándar
python3 -m agroreglas ejemplos/error.agro                  # entrada inválida: error localizado
python3 -m agroreglas --analisis                           # gramática, FIRST, FOLLOW, SELECT y tabla LL(1)
python3 -m unittest discover -s tests -v                   # batería de pruebas
python3 generar_resultados.py                              # regenera resultados/ y las tablas del informe
```

Opciones de análisis: `--tokens`, `--arbol`, `--ast`, `--derivacion` (derivación por la izquierda), `--traza`
(pila/entrada/acción del parser), `--dot-arbol ARCHIVO.dot`, `--dot-ast ARCHIVO.dot` y `--ascii` (árboles sin
caracteres de dibujo Unicode). `python3 -m agroreglas -h` muestra la ayuda.

### Códigos de salida

| Código | Significado |
|---|---|
| 0 | Entrada sintácticamente válida (`ACEPTADA: ...` en la salida estándar), o `--analisis` sin conflictos |
| 1 | Entrada rechazada por un error léxico o sintáctico (mensaje en la salida de errores) |
| 2 | Error de uso o de lectura: argumentos inválidos, archivo inexistente, carpeta, sin permiso o no UTF-8 |
| 3 | `--analisis` encontró conflictos LL(1) (solo si se modifica la gramática) |

### Ejemplo de salida

```text
$ python3 -m agroreglas ejemplos/error.agro
RECHAZADA: ejemplos/error.agro
Error sintáctico en línea 1, columna 16 (posición 15): se esperaba un valor (número entero, TRUE o FALSE)
después del operador '<', pero se encontró la palabra reservada THEN.
  Esperados: NUM, TRUE, FALSE
  Cima de la pila: Valor
   1 | WHEN humedad < THEN regar sector_norte;
     |                ^^^^
```

## Formato de entrada

Archivos de texto UTF-8 (se tolera la marca BOM y el fin de línea CRLF). Un programa es **una o más reglas**:

```text
WHEN <condición> THEN <acción> [AND <acción>]... ;
```

- **Condición:** comparaciones `sensor OP valor` combinadas con `NOT`, `AND`, `OR` y paréntesis.
  Precedencia `NOT` > `AND` > `OR`; los paréntesis la modifican.
- **Comparación:** un identificador, un operador relacional (`<`, `<=`, `>`, `>=`, `==`, `!=`) y un valor:
  número entero sin signo (`30`, `007`) o booleano (`TRUE`, `FALSE`).
- **Acción:** verbo y objetivo (dos identificadores), con duración opcional en minutos: `regar sector_norte DURING 15`.
  Varias acciones se separan con `AND`.
- **Identificadores:** `[A-Za-z_][A-Za-z0-9_]*` (solo ASCII; distinguen mayúsculas).
- **Palabras reservadas** (no distinguen mayúsculas; no pueden ser identificadores):
  `WHEN THEN AND OR NOT TRUE FALSE DURING`.
- Los blancos (espacio, tabulación, `\r`, `\n`) separan tokens y se descartan.

No se admiten: decimales, números con signo, comas, comentarios, cadenas, identificadores como valor derecho,
números a la izquierda de una comparación, programas vacíos ni `;` sobrantes.

### Gramática final (G2, 23 producciones)

```text
Programa     -> Regla Resto
Resto        -> Regla Resto | ε
Regla        -> WHEN Condicion THEN Acciones PUNTO_COMA
Condicion    -> Conjuncion ColaOr
ColaOr       -> OR Conjuncion ColaOr | ε
Conjuncion   -> Factor ColaAnd
ColaAnd      -> AND Factor ColaAnd | ε
Factor       -> NOT Factor | PARENT_IZQ Condicion PARENT_DER | Comparacion
Comparacion  -> ID OP_REL Valor
Valor        -> NUM | TRUE | FALSE
Acciones     -> Accion ColaAcciones
ColaAcciones -> AND Accion ColaAcciones | ε
Accion       -> ID ID Duracion
Duracion     -> DURING NUM | ε
```

La gramática es LL(1): 31 celdas con producción, 179 celdas de error y 0 conflictos
([`resultados/tabla_ll1.md`](resultados/tabla_ll1.md)). Las versiones previas G0 (ambigua) y G1 (con precedencia) están en
`agroreglas/gramatica.py` y tienen 6 y 9 conflictos, respectivamente.

## Uso como biblioteca

```python
from agroreglas import analizar, analizar_tokens, analizador_lexico, construir_ast, texto_ast, formula, ErrorAgro

arbol = analizar('WHEN humedad < 30 THEN regar sector_norte DURING 15;')   # árbol concreto
print(arbol.texto())
ast = construir_ast(arbol)
print(texto_ast(ast))
print(formula(ast.reglas[0].condicion))          # humedad < 30

# El parser también recibe la secuencia de tokens del lexer docente: [(TIPO, lexema), ...]
analizar_tokens(analizador_lexico('WHEN h < 1 THEN a b;'))

try:
    analizar('WHEN humedad < THEN regar sector_norte;')
except ErrorAgro as error:
    print(error.linea, error.columna, error.esperados)   # 1 16 ('NUM', 'TRUE', 'FALSE')
```

## Estructura

```text
agroreglas/
  lexico.py         lexer basado en el notebook docente (modificaciones M1–M7 documentadas)
  gramatica.py      G2 (final) y las versiones previas G0 y G1, como datos
  ll1.py            anulables, FIRST, FOLLOW, SELECT, tabla, conflictos, recursión izquierda y prefijos comunes
  parser.py         parser predictivo dirigido por tabla (pila explícita), traza y derivación
  arbol.py          árbol sintáctico concreto, texto y Graphviz
  abstracto.py      AST y regla semántica de cada producción
  errores.py        ErrorLexico y ErrorSintactico (ubicación, esperados, puntero)
  __main__.py       interfaz de consola
tests/
  casos.py          59 casos documentados con oráculos (veredicto, tipo, línea y columna del error)
  oraculos.py       reconocedor de Earley y generador aleatorio (solo para pruebas diferenciales)
  test_*.py         75 métodos unittest en 7 módulos
ejemplos/           riego.agro, error.agro, validos/*.agro, invalidos/*.agro
generar_resultados.py
herramientas/       capturar_terminal.sh (capturas reales con Xvfb) y ejecutar_notebook.py
resultados/         gramatica.txt, analisis.json, first_follow.csv, seleccion.csv, tabla_ll1.csv/.md,
                    pruebas.csv/.json, resumen_pruebas.txt, arbol_concreto.*, ast.*, derivacion.txt, traza.txt,
                    transcripciones/ (salidas reales de consola) y capturas/ (capturas de terminal)
documentacion/
  Informe_AgroReglas.pdf / .tex   informe final y su fuente
  generado/                       tablas que el informe incluye (producidas por generar_resultados.py)
  AgroReglas.ipynb                notebook de demostración ejecutado
  anlizador_lexico1.ipynb         notebook original del docente, sin modificaciones
```

## Pruebas y resultados

```sh
python3 -m unittest discover -s tests -v
```

- **59 casos documentados** (16 válidos, 22 inválidos y 21 casos límite), cada uno con veredicto esperado y, en los
  rechazos, tipo de error, línea, columna y fragmento del mensaje. Resultado: 59/59 coinciden
  ([`resultados/pruebas.csv`](resultados/pruebas.csv)).
- **75 métodos unittest** que además comprueban: compatibilidad con el lexer docente (42 casos y 3000 cadenas
  aleatorias), FIRST/FOLLOW/SELECT/tabla contra el cálculo manual, G0 y G1 con sus conflictos, precedencia y
  asociatividad en el AST, la extensión `DURING`, consumo completo de la entrada, mensajes y posiciones de error,
  códigos de salida de la consola y coherencia de `resultados/` con el código.
- **Prueba diferencial:** 1200 secuencias de tokens (oraciones de G0 y mutaciones) comparadas con un reconocedor de
  Earley sobre G0, G1 y G2; sin discrepancias.

La cantidad de métodos no equivale a la cantidad de entradas: un mismo método recorre los 59 casos con subpruebas.

`python3 generar_resultados.py` regenera todos los archivos de `resultados/`, las transcripciones de consola y las tablas
de `documentacion/generado/`, y termina ejecutando la batería completa (código 1 si algo falla). Para recompilar el
informe después: `cd documentacion && pdflatex Informe_AgroReglas.tex` tres veces.

## Repositorio

<https://github.com/der-kaffe/AgroReglas-LL1>

```sh
git clone https://github.com/der-kaffe/AgroReglas-LL1.git
cd AgroReglas-LL1
python3 -m unittest discover -s tests
```
