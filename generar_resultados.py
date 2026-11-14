"""Regenera todos los resultados verificables y los fragmentos LaTeX del informe.

    python3 generar_resultados.py

Escribe en resultados/ (CSV, JSON, TXT, DOT y, si Graphviz está instalado,
PNG/PDF de los árboles), en resultados/transcripciones/ (salidas reales de
consola) y en documentacion/generado/ (tablas que el informe incluye con
\\input). Al final ejecuta la batería unittest completa; si falla, termina con
código 1. Solo usa la biblioteca estándar (Graphviz es opcional).
"""
import csv
import json
import re
import shutil
import subprocess
import sys
import textwrap
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path[:0] = [str(RAIZ), str(RAIZ / 'tests')]

from agroreglas import analizar, construir_ast, derivacion_izquierda, texto_ast   # noqa: E402
from agroreglas.abstracto import dot_ast                                           # noqa: E402
from agroreglas.gramatica import EOF, EPS, G0, G1, GRAMATICA                       # noqa: E402
from agroreglas.ll1 import ANALISIS, analizar_gramatica                           # noqa: E402
from agroreglas.parser import analizar_tokens                                      # noqa: E402
from agroreglas.lexico import tokenizar                                            # noqa: E402
from casos import CASOS, EJEMPLO_PRINCIPAL, ejecutar                               # noqa: E402

RESULTADOS = RAIZ / 'resultados'
TRANSCRIPCIONES = RESULTADOS / 'transcripciones'
GENERADO = RAIZ / 'documentacion' / 'generado'
ENTRADA_DERIVACION = 'WHEN humedad < 30 AND NOT lluvia == TRUE THEN regar sector_sur DURING 15;'
ENTRADA_TRAZA = 'WHEN h < 1 THEN a b DURING 2;'

# ------------------------------------------------------------------ utilidades
LATIN = set('áéíóúÁÉÍÓÚñÑüÜ¿¡')
ESPECIALES = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '$': r'\$', '&': r'\&', '#': r'\#',
              '^': r'\textasciicircum{}', '_': r'\_', '%': r'\%', '~': r'\textasciitilde{}',
              "'": r'\textquotesingle{}', '`': r'\textasciigrave{}', '<': r'\textless{}',
              '>': r'\textgreater{}', '|': r'\textbar{}', '"': r'\textquotedbl{}',
              'ε': r'\ensuremath{\varepsilon}', '→': r'\ensuremath{\rightarrow}',
              '⇒': r'\ensuremath{\Rightarrow}', '…': r'\ldots{}', '−': r'\ensuremath{-}',
              'º': r'\textordmasculine{}', 'ª': r'\textordfeminine{}'}


def tex(texto):
    """Escapa texto para LaTeX (pdflatex, T1); los caracteres fuera de alcance se muestran como U+XXXX."""
    salida = []
    for c in str(texto):
        if c in ESPECIALES:
            salida.append(ESPECIALES[c])
        elif ord(c) < 128 or c in LATIN:
            salida.append(c)
        else:
            salida.append(rf'\textlangle{{}}U+{ord(c):04X}\textrangle{{}}')
    return ''.join(salida)


def tex_cortable(texto, tramo=24):
    """Texto escapado con cortes permitidos tras '(' y ',' y en tramos largos sin espacios."""
    piezas = []
    for palabra in re.split(r'(\s+)', str(texto)):
        if len(palabra) > tramo and not palabra.isspace():
            palabra = '\0'.join(palabra[i:i + tramo] for i in range(0, len(palabra), tramo))
        piezas.append(palabra)
    escapado = tex(''.join(piezas).replace('(', '(\0').replace(',', ',\0'))
    return escapado.replace('\0', r'\allowbreak{}')


def tex_codigo(texto):
    """Código en monoespaciado con cortes de línea permitidos tras espacios y '_'."""
    return r'\texttt{' + tex(texto).replace(' ', r' \allowbreak{}').replace(r'\_', r'\_\allowbreak{}') + '}'


def conjunto(simbolos):
    return ', '.join(ANALISIS.ordenar(simbolos))


def conjunto_tex(simbolos):
    return r'\{' + ', '.join(tex_codigo(s) if s != EPS else r'$\varepsilon$'
                              for s in ANALISIS.ordenar(simbolos)) + r'\}'


def produccion_tex(p, flecha=r'$\rightarrow$'):
    derecha = ' '.join(p.derecha) if p.derecha else None
    return f'{tex(p.izquierda)} {flecha} ' + (tex_codigo(derecha) if derecha else r'$\varepsilon$')


def escribir(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido if contenido.endswith('\n') else contenido + '\n', encoding='utf-8')


def ejecutar_consola(argumentos, entrada=None):
    """Ejecuta un comando real y devuelve su transcripción (comando, salida, código)."""
    comando = [sys.executable, *argumentos]
    resultado = subprocess.run(comando, cwd=RAIZ, input=entrada, capture_output=True, text=True,
                               encoding='utf-8')
    visible = 'python3 ' + ' '.join(f'"{a}"' if ' ' in a else a for a in argumentos)
    texto = f'$ {visible}\n{resultado.stdout}{resultado.stderr}$ echo $?\n{resultado.returncode}\n'
    return texto, resultado


# ---------------------------------------------------------- análisis formal
def exportar_analisis():
    g = ANALISIS.gramatica
    partes = [f'# {g.nombre}: S = {g.inicial}; |N| = {len(g.no_terminales)}, |T| = {len(g.terminales)}, '
              f'|P| = {len(g.producciones)}']
    partes += [f'({p.numero:>2}) {p}' for p in g.producciones]
    for otra in (G0, G1):
        partes += ['', f'# {otra.nombre} (versión previa, no LL(1))', otra.texto()]
    escribir(RESULTADOS / 'gramatica.txt', '\n'.join(partes))

    def resumen(a):
        return {'conflictos': [{'no_terminal': c.no_terminal, 'terminal': c.terminal,
                                'producciones': list(c.producciones)} for c in a.conflictos],
                'recursion_izquierda_directa': a.recursion_directa,
                'recursion_izquierda_indirecta': a.recursion_indirecta,
                'prefijos_comunes': [{'no_terminal': x[0], 'producciones': [x[1], x[2]], 'prefijo': list(x[3])}
                                     for x in a.prefijos],
                'es_LL1': a.es_ll1}

    datos = {
        'gramatica': g.nombre, 'inicial': g.inicial, 'epsilon': EPS, 'fin_de_entrada': EOF,
        'no_terminales': g.no_terminales, 'terminales': g.terminales,
        'producciones': [{'numero': p.numero, 'izquierda': p.izquierda, 'derecha': list(p.derecha)}
                         for p in g.producciones],
        'anulables': [a for a in g.no_terminales if a in ANALISIS.anulables],
        'FIRST': {a: ANALISIS.ordenar(ANALISIS.first[a]) for a in g.no_terminales},
        'FOLLOW': {a: ANALISIS.ordenar(ANALISIS.follow[a]) for a in g.no_terminales},
        'SELECT': {str(n): ANALISIS.ordenar(s) for n, s in ANALISIS.seleccion.items()},
        'tabla': {a: {t: ANALISIS.tabla[a, t].numero for t in ANALISIS.fila(a)} for a in g.no_terminales},
        'celdas_con_produccion': len(ANALISIS.tabla),
        'celdas_de_error': len(g.no_terminales) * len(ANALISIS.columnas) - len(ANALISIS.tabla),
        'pasadas_punto_fijo': {'FIRST': ANALISIS.pasadas_first, 'FOLLOW': ANALISIS.pasadas_follow},
        **resumen(ANALISIS),
        'versiones_previas': {otra.nombre: resumen(analizar_gramatica(otra)) for otra in (G0, G1)},
    }
    escribir(RESULTADOS / 'analisis.json', json.dumps(datos, ensure_ascii=False, indent=2))

    with (RESULTADOS / 'first_follow.csv').open('w', encoding='utf-8', newline='') as archivo:
        w = csv.writer(archivo)
        w.writerow(['No terminal', 'Anulable', 'FIRST', 'FOLLOW'])
        for a in g.no_terminales:
            w.writerow([a, 'sí' if a in ANALISIS.anulables else 'no',
                        conjunto(ANALISIS.first[a]), conjunto(ANALISIS.follow[a])])
    with (RESULTADOS / 'seleccion.csv').open('w', encoding='utf-8', newline='') as archivo:
        w = csv.writer(archivo)
        w.writerow(['N.º', 'Producción', 'SELECT'])
        for p in g.producciones:
            w.writerow([p.numero, str(p), conjunto(ANALISIS.seleccion[p.numero])])
    with (RESULTADOS / 'tabla_ll1.csv').open('w', encoding='utf-8', newline='') as archivo:
        w = csv.writer(archivo)
        w.writerow(['No terminal'] + ANALISIS.columnas)
        for a in g.no_terminales:
            w.writerow([a] + [f'{ANALISIS.tabla[a, t].numero}: {ANALISIS.tabla[a, t]}' if (a, t) in ANALISIS.tabla
                              else 'ERROR' for t in ANALISIS.columnas])
    filas = ['| No terminal | ' + ' | '.join(ANALISIS.columnas) + ' |',
             '|---|' + '---|' * len(ANALISIS.columnas)]
    for a in g.no_terminales:
        filas.append(f'| {a} | ' + ' | '.join(str(ANALISIS.tabla[a, t].numero) if (a, t) in ANALISIS.tabla else ' '
                                              for t in ANALISIS.columnas) + ' |')
    escribir(RESULTADOS / 'tabla_ll1.md', '# Tabla LL(1) de AgroReglas\n\nCada número es una producción de '
             '`resultados/gramatica.txt`; las celdas vacías son ERROR.\n\n' + '\n'.join(filas))

    # Fragmentos LaTeX ---------------------------------------------------
    escribir(GENERADO / 'producciones.tex', '\n'.join(
        f'{p.numero} & {produccion_tex(p)} \\\\' for p in g.producciones))
    for otra, nombre in ((G0, 'g0'), (G1, 'g1')):
        escribir(GENERADO / f'gramatica_{nombre}.tex', '\n'.join(
            f'{p.numero} & {produccion_tex(p)} \\\\' for p in otra.producciones))
    escribir(GENERADO / 'first_follow.tex', '\n'.join(
        f'{tex(a)} & {"sí" if a in ANALISIS.anulables else "no"} & {conjunto_tex(ANALISIS.first[a])} & '
        f'{conjunto_tex(ANALISIS.follow[a])} \\\\' for a in g.no_terminales))
    lineas = []
    for a in g.no_terminales:
        alternativas = g.alternativas(a)
        for k, p in enumerate(alternativas):
            disjunto = ''
            if k == 0:
                disjunto = 'sí' if len(alternativas) > 1 else '---'   # una sola alternativa: no hay elección
            lineas.append(f'{tex(a) if k == 0 else ""} & ({p.numero}) {produccion_tex(p)} & '
                          f'{conjunto_tex(ANALISIS.seleccion[p.numero])} & {disjunto} \\\\')
        lineas.append(r'\hline')
    escribir(GENERADO / 'seleccion.tex', '\n'.join(lineas))
    cabecera = ' & '.join(r'\rotatebox{90}{\texttt{%s}}' % tex(t if t != EOF else 'EOF ($)')
                          for t in ANALISIS.columnas)
    filas = [r'\textbf{No terminal} & ' + cabecera + r' \\ \hline']
    for a in g.no_terminales:
        celdas = [r'\textbf{%d}' % ANALISIS.tabla[a, t].numero if (a, t) in ANALISIS.tabla else r'\textcolor{gris}{·}'
                  for t in ANALISIS.columnas]
        filas.append(f'{tex(a)} & ' + ' & '.join(celdas) + r' \\')
    escribir(GENERADO / 'tabla_ll1.tex', '\n'.join(filas))
    conflictos = []
    for otra in (G0, G1):
        a = analizar_gramatica(otra)
        for c in a.conflictos:
            conflictos.append(f'{tex(otra.nombre)} & {tex(c.no_terminal)} & {tex_codigo(c.terminal)} & '
                              + '; '.join(f'({n}) {produccion_tex(otra.produccion(n))}' for n in c.producciones)
                              + r' \\')
    escribir(GENERADO / 'conflictos_previos.tex', '\n'.join(conflictos))
    previas = {otra.nombre: analizar_gramatica(otra) for otra in (G0, G1)}
    return previas


# --------------------------------------------------------------- casos de prueba
def exportar_pruebas():
    filas = [ejecutar(caso) for caso in CASOS]
    columnas = ['id', 'categoria', 'entrada_mostrada', 'esperado', 'obtenido', 'error_esperado', 'error_obtenido',
                'ubicacion_esperada', 'ubicacion_obtenida', 'coincide', 'observacion', 'mensaje', 'esperados',
                'detalle', 'entrada']
    escribir(RESULTADOS / 'pruebas.json', json.dumps([{c: f[c] for c in columnas} for f in filas],
                                                     ensure_ascii=False, indent=2))
    with (RESULTADOS / 'pruebas.csv').open('w', encoding='utf-8', newline='') as archivo:
        w = csv.DictWriter(archivo, fieldnames=columnas[:-1])
        w.writeheader()
        for f in filas:
            w.writerow({c: f[c] for c in columnas[:-1]})
    cuenta = Counter(f['categoria'] for f in filas)
    correctos = Counter(f['categoria'] for f in filas if f['coincide'])
    resumen = [f'{c}: {correctos[c]}/{cuenta[c]} coinciden con lo esperado' for c in ('válida', 'inválida', 'límite')]
    resumen.append(f'TOTAL: {sum(correctos.values())}/{len(filas)}')
    escribir(RESULTADOS / 'resumen_pruebas.txt', '\n'.join(resumen))

    for categoria, archivo in (('válida', 'casos_validos.tex'), ('inválida', 'casos_invalidos.tex'),
                               ('límite', 'casos_limite.tex')):
        bloque = []
        for f, caso in zip(filas, CASOS):
            if f['categoria'] != categoria:
                continue
            marca = r'$\checkmark$' if f['coincide'] else r'\textbf{NO}'
            if f['obtenido'] == 'ACEPTA':
                obtenido = 'ACEPTA'
                esperado = 'ACEPTA'
            else:
                obtenido = f'RECHAZA ({f["error_obtenido"][:4]}., {f["ubicacion_obtenida"]})'
                esperado = f'RECHAZA ({f["error_esperado"][:4]}., {f["ubicacion_esperada"]})'
            bloque.append(f'{f["id"]} & {tex_codigo(f["entrada_mostrada"])} & {esperado} & {obtenido} {marca} & '
                          f'{tex(f["observacion"])} \\\\*')
            if f['mensaje']:
                mensaje = f['mensaje'].split(': ', 1)[1]
                bloque.append(r'\multicolumn{5}{p{\dimexpr\linewidth-2\tabcolsep\relax}}{\raggedright\footnotesize\color{gris}'
                              r'\hspace*{1.2em}Mensaje: ' + tex_cortable(mensaje) + r'} \\')
            else:
                bloque.append(r'\multicolumn{5}{p{\dimexpr\linewidth-2\tabcolsep\relax}}{\raggedright\footnotesize\color{gris}'
                              r'\hspace*{1.2em}AST: ' + tex_cortable(f['detalle']) + r'} \\')
            bloque.append(r'\hline')
        escribir(GENERADO / archivo, '\n'.join(bloque))
    return filas, cuenta, correctos


# ---------------------------------------------------- árboles, derivación y traza
def exportar_arboles():
    arbol = analizar(EJEMPLO_PRINCIPAL)
    ast = construir_ast(arbol)
    escribir(RESULTADOS / 'arbol_concreto.txt', f'Entrada:\n{EJEMPLO_PRINCIPAL}\n\n{arbol.texto()}')
    escribir(RESULTADOS / 'ast.txt', f'Entrada:\n{EJEMPLO_PRINCIPAL}\n\n{texto_ast(ast)}')
    escribir(RESULTADOS / 'arbol_concreto.dot', arbol.dot('Árbol sintáctico concreto (ejemplo del enunciado)'))
    escribir(RESULTADOS / 'ast.dot', dot_ast(ast, 'AST (ejemplo del enunciado)'))
    escribir(GENERADO / 'arbol_concreto.tex', arbol.texto(unicode=False))
    escribir(GENERADO / 'arbol_concreto_traza.tex', analizar(ENTRADA_TRAZA).texto(unicode=False))
    escribir(GENERADO / 'ast.tex', texto_ast(ast, unicode=False))
    dibujos = []
    if shutil.which('dot'):
        for nombre in ('arbol_concreto', 'ast'):
            for formato in ('png', 'pdf'):
                opciones = ['-Gdpi=170'] if formato == 'png' else []
                subprocess.run(['dot', f'-T{formato}', *opciones, str(RESULTADOS / f'{nombre}.dot'),
                                '-o', str(RESULTADOS / f'{nombre}.{formato}')], check=True)
                dibujos.append(f'{nombre}.{formato}')

    arbol = analizar(ENTRADA_DERIVACION)
    producciones, formas = derivacion_izquierda(arbol)
    texto = [f'Entrada: {ENTRADA_DERIVACION}', '', ' '.join(formas[0])]
    texto += [f'⇒ {" ".join(f)}   [{p.numero}]' for p, f in zip(producciones, formas[1:])]
    escribir(RESULTADOS / 'derivacion.txt', '\n'.join(texto))
    filas = [f'0 & --- & {tex_codigo(" ".join(formas[0]))} \\\\']
    for k, (p, forma) in enumerate(zip(producciones, formas[1:]), 1):
        filas.append(f'{k} & {p.numero} & $\\Rightarrow$ {tex_codigo(" ".join(forma))} \\\\')
    escribir(GENERADO / 'derivacion.tex', '\n'.join(filas))

    traza = []
    analizar_tokens(tokenizar(ENTRADA_TRAZA), traza=traza)
    texto = [f'Entrada: {ENTRADA_TRAZA}', '', f'{"Paso":>4}  {"Pila (cima a la derecha)":<58}  {"Entrada":<44}  Acción']
    texto += [f'{n:>4}  {p:<58}  {e:<44}  {a}' for n, (p, e, a) in enumerate(traza, 1)]
    escribir(RESULTADOS / 'traza.txt', '\n'.join(texto))
    escribir(GENERADO / 'traza.tex', '\n'.join(
        f'{n} & {tex_codigo(p)} & {tex_codigo(e)} & {tex(a)} \\\\' for n, (p, e, a) in enumerate(traza, 1)))
    return len(producciones), len(traza), dibujos


# ------------------------------------------------------------ transcripciones
COMANDOS = [
    ('01_valida_ast', ['-m', 'agroreglas', 'ejemplos/riego.agro', '--ast']),
    ('02_invalida_falta_valor', ['-m', 'agroreglas', 'ejemplos/error.agro']),
    ('03_invalida_parentesis', ['-m', 'agroreglas', 'ejemplos/invalidos/03_parentesis_sin_cerrar.agro']),
    ('04_invalida_truncada', ['-m', 'agroreglas', 'ejemplos/invalidos/07_regla_truncada.agro']),
    ('05_invalida_lexico', ['-m', 'agroreglas', 'ejemplos/invalidos/05_coma_entre_acciones.agro']),
    ('06_invalida_sobrante', ['-m', 'agroreglas', 'ejemplos/invalidos/06_contenido_sobrante.agro']),
    ('07_entrada_vacia', ['-m', 'agroreglas', 'ejemplos/invalidos/08_vacio.agro']),
    ('08_tokens_derivacion', ['-m', 'agroreglas', '-e', 'WHEN humedad < 30 THEN regar sur DURING 15;',
                              '--tokens', '--derivacion']),
    ('09_analisis_gramatica', ['-m', 'agroreglas', '--analisis']),
    ('10_archivo_inexistente', ['-m', 'agroreglas', 'ejemplos/no_existe.agro']),
]


def ajustar(texto, ancho=100):
    """Divide las líneas largas para que quepan en la página del informe (sangría de continuación)."""
    salida = []
    for linea in texto.splitlines():
        if len(linea) <= ancho:
            salida.append(linea)
        else:
            salida += textwrap.wrap(linea, ancho, subsequent_indent='    ', break_on_hyphens=False)
    return '\n'.join(salida)


def exportar_transcripciones():
    for nombre, argumentos in COMANDOS:
        texto, _ = ejecutar_consola(argumentos)
        escribir(TRANSCRIPCIONES / f'{nombre}.txt', texto)
        escribir(GENERADO / f'transcripcion_{nombre}.txt', ajustar(texto))
    lineas = []
    for archivo in sorted((RAIZ / 'ejemplos').rglob('*.agro')):
        relativo = archivo.relative_to(RAIZ).as_posix()
        _, resultado = ejecutar_consola(['-m', 'agroreglas', relativo])
        primera = (resultado.stdout or resultado.stderr).splitlines()
        detalle = primera[1] if resultado.returncode == 1 and len(primera) > 1 else (primera[0] if primera else '')
        lineas.append(f'[{resultado.returncode}] {relativo}\n    {detalle}')
    texto = '# python3 -m agroreglas <archivo> para cada ejemplo; [código de salida]\n' + '\n'.join(lineas)
    escribir(TRANSCRIPCIONES / '00_todos_los_ejemplos.txt', texto)
    escribir(GENERADO / 'transcripcion_00_todos_los_ejemplos.txt', ajustar(texto))


def extracto(ruta, inicio, fin):
    """Líneas numeradas desde la que comienza con ``inicio`` hasta la primera que comienza con ``fin``."""
    lineas = (RAIZ / ruta).read_text(encoding='utf-8').splitlines()
    a = next(i for i, l in enumerate(lineas) if l.startswith(inicio))
    b = next(i for i in range(a + 1, len(lineas)) if lineas[i].startswith(fin))
    return '\n'.join(f'{n + 1:>4}  {lineas[n]}' for n in range(a, b + 1)), a + 1, b + 1


def exportar_extractos():
    rangos = {}
    for nombre, ruta, inicio, fin in [
            ('extracto_parser', 'agroreglas/parser.py', 'def analizar_tokens(', '    return raiz'),
            ('extracto_first_follow', 'agroreglas/ll1.py', 'def first_secuencia(', '    return follow, pasadas'),
            ('extracto_tabla', 'agroreglas/ll1.py', 'def conjunto_seleccion(', '    return tabla, conflictos'),
            ('extracto_semantica', 'agroreglas/abstracto.py', 'REGLAS_SEMANTICAS = {', '}'),
            ('extracto_viables', 'agroreglas/parser.py', 'def _viables(pila):', '    return resultado')]:
        try:
            texto, a, b = extracto(ruta, inicio, fin)
        except StopIteration:
            raise SystemExit(f'No se encontró el extracto {nombre} en {ruta}')
        escribir(GENERADO / f'{nombre}.txt', texto)
        rangos[nombre] = (ruta, a, b)
    return rangos


def cifras_pruebas():
    """Cantidades exactas de entradas evaluadas por las pruebas aleatorias y diferenciales."""
    from oraculos import a_texto, reconoce_earley
    from test_lexico import N_CADENAS_ALEATORIAS, cadenas_aleatorias
    from test_parser import N_DIFERENCIALES, N_MUTACIONES_INMEDIATA, N_ORACIONES_G0, muestras_diferenciales
    from agroreglas import ErrorAgro
    muestras, rng = muestras_diferenciales()
    aceptadas = 0
    for tipos in muestras:
        try:
            analizar(a_texto(tipos, rng))
            aceptadas += 1
        except ErrorAgro:
            pass
    earley = sum(reconoce_earley(G0, t) for t in muestras)
    return {'NumAleatoriasLexico': N_CADENAS_ALEATORIAS, 'NumComparadasLexico': len(cadenas_aleatorias()),
            'NumDiferenciales': N_DIFERENCIALES, 'NumDiferencialesAceptadas': aceptadas,
            'NumDiferencialesRechazadas': N_DIFERENCIALES - aceptadas, 'NumEarleyAceptadas': earley,
            'NumOracionesGcero': N_ORACIONES_G0, 'NumMutacionesInmediata': N_MUTACIONES_INMEDIATA}


def ejecutar_unittest():
    texto, resultado = ejecutar_consola(['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    escribir(TRANSCRIPCIONES / '11_unittest.txt', texto)
    escribir(GENERADO / 'transcripcion_11_unittest.txt', ajustar(texto))
    metodos = int(re.search(r'Ran (\d+) tests?', texto).group(1))
    return resultado.returncode, metodos, texto


def main():
    previas = exportar_analisis()
    filas, cuenta, correctos = exportar_pruebas()
    pasos_derivacion, pasos_traza, dibujos = exportar_arboles()
    exportar_transcripciones()
    rangos = exportar_extractos()
    adicionales = cifras_pruebas()
    codigo, metodos, texto = ejecutar_unittest()
    g0, g1 = previas[G0.nombre], previas[G1.nombre]
    macros = {
        'NumCasos': len(filas), 'NumValidas': cuenta['válida'], 'NumInvalidas': cuenta['inválida'],
        'NumLimite': cuenta['límite'], 'NumCorrectos': sum(correctos.values()), 'NumMetodos': metodos,
        'NumCeldas': len(ANALISIS.tabla), 'NumCeldasError': 14 * 15 - len(ANALISIS.tabla),
        'NumConflictosGcero': len(g0.conflictos), 'NumConflictosGuno': len(g1.conflictos),
        'PasosDerivacion': pasos_derivacion, 'PasosTraza': pasos_traza,
        'PasadasFirst': ANALISIS.pasadas_first, 'PasadasFollow': ANALISIS.pasadas_follow,
        'NumEjemplos': len(list((RAIZ / 'ejemplos').rglob('*.agro'))), **adicionales,
    }
    for nombre, (ruta, a, b) in rangos.items():
        clave = ''.join(p.capitalize() for p in nombre.split('_'))
        macros[f'Lineas{clave}'] = f'{tex(ruta)}, líneas {a}--{b}'
    if adicionales['NumDiferencialesAceptadas'] != adicionales['NumEarleyAceptadas']:
        print('Discrepancia entre el parser LL(1) y Earley.', file=sys.stderr)
        return 1
    escribir(GENERADO / 'cifras.tex', '\n'.join(rf'\newcommand{{\{k}}}{{{v}}}' for k, v in macros.items())
             + '\n' + rf'\newcommand{{\EntradaDerivacion}}{{{tex_codigo(ENTRADA_DERIVACION)}}}'
             + '\n' + rf'\newcommand{{\EntradaTraza}}{{{tex_codigo(ENTRADA_TRAZA)}}}')
    print(f'Casos documentados: {sum(correctos.values())}/{len(filas)} coinciden con lo esperado '
          f'({cuenta["válida"]} válidas, {cuenta["inválida"]} inválidas, {cuenta["límite"]} límite).')
    print(f'Tabla LL(1): {len(ANALISIS.tabla)} celdas con producción, {len(ANALISIS.conflictos)} conflictos '
          f'(G0: {len(g0.conflictos)}, G1: {len(g1.conflictos)}).')
    print(f'Árboles dibujados con Graphviz: {", ".join(dibujos) or "no (Graphviz no instalado)"}.')
    print(f'unittest: {metodos} métodos; código de salida {codigo}.')
    if codigo != 0 or sum(correctos.values()) != len(filas):
        print(texto[-3000:], file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
