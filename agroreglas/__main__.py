"""Interfaz de consola de AgroReglas.

    python3 -m agroreglas ARCHIVO [opciones]      analiza un archivo (UTF-8)
    python3 -m agroreglas -e "TEXTO" [opciones]   analiza el texto indicado
    python3 -m agroreglas - [opciones]            analiza la entrada estándar
    python3 -m agroreglas --analisis              muestra G, FIRST, FOLLOW y tabla LL(1)

Códigos de salida:
    0  entrada sintácticamente válida (o --analisis sin conflictos)
    1  entrada rechazada: error léxico o sintáctico
    2  error de uso o de lectura del archivo (no se analizó nada)
    3  --analisis detectó conflictos LL(1) (solo si se modifica la gramática)
"""
import argparse
import sys
from pathlib import Path

from .abstracto import construir_ast, dot_ast, texto_ast
from .errores import ErrorAgro
from .gramatica import EPS
from .ll1 import ANALISIS
from .lexico import tokenizar
from .parser import analizar_tokens, derivacion_izquierda


def _crear_argumentos():
    parser = argparse.ArgumentParser(
        prog='python3 -m agroreglas',
        description='Analizador sintáctico LL(1) de AgroReglas (reglas de riego agrícola).',
        epilog='Códigos de salida: 0 válida, 1 error léxico/sintáctico, 2 error de uso o lectura.')
    fuente = parser.add_mutually_exclusive_group()
    fuente.add_argument('archivo', nargs='?', help="archivo .agro en UTF-8, o '-' para stdin")
    fuente.add_argument('-e', '--entrada', metavar='TEXTO', help='texto a analizar')
    parser.add_argument('--tokens', action='store_true', help='muestra los tokens')
    parser.add_argument('--arbol', action='store_true', help='muestra el árbol sintáctico concreto')
    parser.add_argument('--ast', action='store_true', help='muestra el árbol de sintaxis abstracta')
    parser.add_argument('--derivacion', action='store_true', help='muestra la derivación por la izquierda')
    parser.add_argument('--traza', action='store_true', help='muestra la traza pila/entrada/acción')
    parser.add_argument('--dot-arbol', metavar='SALIDA.dot', help='exporta el árbol concreto a Graphviz')
    parser.add_argument('--dot-ast', metavar='SALIDA.dot', help='exporta el AST a Graphviz')
    parser.add_argument('--ascii', action='store_true', help='dibuja los árboles solo con ASCII')
    parser.add_argument('--analisis', action='store_true',
                        help='muestra gramática, FIRST, FOLLOW, SELECT y tabla LL(1)')
    return parser


def _conjunto(simbolos):
    return '{' + ', '.join(ANALISIS.ordenar(simbolos)) + '}'


def mostrar_analisis():
    g = ANALISIS.gramatica
    print(f'Gramática {g.nombre}: S = {g.inicial}; |N| = {len(g.no_terminales)}, '
          f'|T| = {len(g.terminales)}, |P| = {len(g.producciones)}')
    for p in g.producciones:
        print(f'  ({p.numero:>2}) {p}')
    print(f'\nAnulables: {_conjunto(ANALISIS.anulables)}')
    ancho = max(len(a) for a in g.no_terminales)
    print('\nFIRST y FOLLOW:')
    for a in g.no_terminales:
        print(f'  {a:<{ancho}}  FIRST = {_conjunto(ANALISIS.first[a])}  FOLLOW = {_conjunto(ANALISIS.follow[a])}')
    print('\nConjuntos de selección:')
    for p in g.producciones:
        print(f'  ({p.numero:>2}) SELECT = {_conjunto(ANALISIS.seleccion[p.numero])}')
    print(f'\nTabla LL(1): {len(ANALISIS.tabla)} celdas con producción; '
          f'{len(g.no_terminales) * len(ANALISIS.columnas) - len(ANALISIS.tabla)} celdas de error.')
    for a in g.no_terminales:
        celdas = ', '.join(f'{t}→{ANALISIS.tabla[a, t].numero}' for t in ANALISIS.fila(a))
        print(f'  {a:<{ancho}}  {celdas}')
    recursion = ANALISIS.recursion_directa or list(ANALISIS.recursion_indirecta)
    print(f'\nRecursión izquierda: {recursion or "ninguna"}')
    print(f'Prefijos comunes: {ANALISIS.prefijos or "ninguno"}')
    print(f'Conflictos: {len(ANALISIS.conflictos)} -> '
          f'{"la gramática es LL(1)" if ANALISIS.es_ll1 else "NO es LL(1)"}')
    return 0 if ANALISIS.es_ll1 else 3


def _cantidad(n, singular, plural):
    return f'{n} {singular if n == 1 else plural}'


def _leer(args):
    if args.entrada is not None:
        return args.entrada, '<texto>'
    if args.archivo == '-':
        return sys.stdin.read(), '<stdin>'
    return Path(args.archivo).read_text(encoding='utf-8-sig'), args.archivo


def main(argv=None):
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, 'reconfigure'):
            flujo.reconfigure(errors='replace')
    argumentos = _crear_argumentos()
    args = argumentos.parse_args(argv)
    if args.analisis:
        return mostrar_analisis()
    if args.archivo is None and args.entrada is None:
        argumentos.print_usage(sys.stderr)
        print('Error de uso: indique un ARCHIVO, "-" o -e TEXTO.', file=sys.stderr)
        return 2
    try:
        fuente, nombre = _leer(args)
    except FileNotFoundError:
        print(f"Error de lectura: no existe el archivo '{args.archivo}'.", file=sys.stderr)
        return 2
    except IsADirectoryError:
        print(f"Error de lectura: '{args.archivo}' es una carpeta, no un archivo.", file=sys.stderr)
        return 2
    except PermissionError:
        print(f"Error de lectura: sin permiso para leer '{args.archivo}'.", file=sys.stderr)
        return 2
    except UnicodeDecodeError as error:
        print(f"Error de lectura: '{args.archivo}' no está en UTF-8 (byte inválido en la posición "
              f'{error.start}).', file=sys.stderr)
        return 2
    except OSError as error:
        print(f'Error de lectura: {error}', file=sys.stderr)
        return 2
    unicode = not args.ascii
    try:
        tokens = tokenizar(fuente)
        if args.tokens:
            print('Tokens (línea:columna  tipo  lexema):')
            for t in tokens:
                print(f'  {t.linea}:{t.columna:<4} {t.tipo:<11} {t.lexema}')
        traza = [] if args.traza else None
        arbol = analizar_tokens(tokens, traza=traza)
    except ErrorAgro as error:
        print(f'RECHAZADA: {nombre}', file=sys.stderr)
        print(error.mostrar(fuente), file=sys.stderr)
        return 1
    ast = construir_ast(arbol)
    acciones = sum(len(r.acciones) for r in ast.reglas)
    print(f'ACEPTADA: {nombre} es sintácticamente válida ({_cantidad(len(ast.reglas), "regla", "reglas")}, '
          f'{_cantidad(acciones, "acción", "acciones")}, {_cantidad(len(tokens) - 1, "token", "tokens")}).')
    if traza is not None:
        print('\nTraza del parser LL(1) (cima de la pila a la derecha):')
        ancho_pila = min(60, max(len(f[0]) for f in traza))
        ancho_entrada = min(48, max(len(f[1]) for f in traza))
        print(f'  {"Paso":>4}  {"Pila":<{ancho_pila}}  {"Entrada":<{ancho_entrada}}  Acción')
        for n, (pila, entrada, accion) in enumerate(traza, 1):
            print(f'  {n:>4}  {pila:<{ancho_pila}}  {entrada:<{ancho_entrada}}  {accion}')
    if args.derivacion:
        producciones, formas = derivacion_izquierda(arbol)
        print('\nDerivación por la izquierda (terminales como categorías de token):')
        print(f'  {" ".join(formas[0])}')
        for p, forma in zip(producciones, formas[1:]):
            print(f'  ⇒ {" ".join(forma) or EPS}   [{p.numero}]')
    if args.arbol:
        print('\nÁrbol sintáctico concreto:')
        print(arbol.texto(unicode))
    if args.ast:
        print('\nÁrbol de sintaxis abstracta (AST):')
        print(texto_ast(ast, unicode))
    try:
        if args.dot_arbol:
            Path(args.dot_arbol).write_text(arbol.dot() + '\n', encoding='utf-8')
        if args.dot_ast:
            Path(args.dot_ast).write_text(dot_ast(ast) + '\n', encoding='utf-8')
    except OSError as error:
        print(f'Error de escritura: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
