"""Parser predictivo LL(1) dirigido por tabla, implementado a mano.

Algoritmo (pila explícita, sin recursión ni retroceso):
  1. La pila comienza con [EOF, Programa] (cima a la derecha).
  2. Si la cima es un terminal: debe coincidir con el token actual; se desapila
     y se consume el token. Si no coincide, error.
  3. Si la cima es un no terminal A: se consulta M[A, a] con el token actual a.
     Celda vacía: error. Si hay producción A → X1..Xk, se desapila A, se crean
     los hijos del árbol y se apilan Xk..X1 (X1 queda en la cima). Si es A → ε,
     se desapila A sin consumir entrada.
  4. Se acepta cuando se consume EOF y la pila queda vacía: así se garantiza que
     toda la entrada fue consumida (no hay contenido sobrante).

Detección inmediata (opcional, activada por defecto): antes de aplicar una
producción ε se comprueba que el token actual sea *viable* con la pila real
(FIRST de los símbolos de la pila hasta el primero no anulable). La celda
M[A, a] para A → ε usa FOLLOW(A), que es una aproximación más amplia; con la
comprobación el error se informa antes de desapilar símbolos y la lista de
esperados es exacta. No cambia el lenguaje aceptado ni el token del error:
solo mejora el diagnóstico (lo verifican las pruebas).
"""
from .arbol import Nodo
from .errores import ErrorSintactico
from .gramatica import EOF, EPS, GRAMATICA
from .ll1 import ANALISIS
from .lexico import Token, tokenizar

DESCRIPCION_TERMINAL = {
    'ID': 'un identificador',
    'NUM': 'un número entero',
    'OP_REL': 'un operador relacional (<, <=, >, >=, ==, !=)',
    'PUNTO_COMA': "';'",
    'PARENT_IZQ': "'('",
    'PARENT_DER': "')'",
    EOF: 'el fin de la entrada',
}


def describir_esperado(terminal):
    return DESCRIPCION_TERMINAL.get(terminal, terminal)


def describir_token(token):
    tipo, lexema = token.tipo, token.lexema
    if tipo == EOF:
        return 'el fin de la entrada'
    if tipo == 'ID':
        return f"el identificador '{lexema}'"
    if tipo == 'NUM':
        return f'el número {lexema}'
    if tipo == 'OP_REL':
        return f"el operador '{lexema}'"
    if tipo in ('PUNTO_COMA', 'PARENT_IZQ', 'PARENT_DER'):
        return f"el símbolo '{lexema}'"
    escrito = '' if lexema == tipo else f" (escrita '{lexema}')"
    return f'la palabra reservada {tipo}{escrito}'


def _lista(elementos):
    elementos = list(elementos)
    if len(elementos) == 1:
        return elementos[0]
    conjuncion = ' u ' if elementos[-1][:1] in 'oO' else ' o '   # "AND u OR"
    return ', '.join(elementos[:-1]) + conjuncion + elementos[-1]


def _frase_esperados(esperados, previo):
    conjunto = set(esperados)
    if conjunto == {'ID', 'NOT', 'PARENT_IZQ'}:
        return "una condición (un sensor, NOT o '(')"
    if conjunto == {'NUM', 'TRUE', 'FALSE'}:
        return 'un valor (número entero, TRUE o FALSE)'
    if conjunto == {'ID'} and previo is not None:
        if previo.tipo == 'ID':
            return f"el objetivo de la acción '{previo.lexema}' (un identificador)"
        if previo.tipo in ('THEN', 'AND'):
            return 'el verbo de una acción (un identificador)'
        if previo.tipo == 'WHEN':
            return 'el sensor de la comparación (un identificador)'
    if conjunto == {'NUM'} and previo is not None and previo.tipo == 'DURING':
        return 'la duración en minutos (un número entero)'
    return _lista(describir_esperado(t) for t in esperados)


def _frase_previo(previo):
    if previo is None:
        return 'al comienzo de la entrada'
    if previo.tipo == 'OP_REL':
        return f"después del operador '{previo.lexema}'"
    if previo.tipo == 'NUM':
        return f'después del número {previo.lexema}'
    if previo.tipo == 'ID':
        return f"después de '{previo.lexema}'"
    if previo.tipo in ('PUNTO_COMA', 'PARENT_IZQ', 'PARENT_DER'):
        return f"después de '{previo.lexema}'"
    return f'después de {previo.tipo}'


def _normalizar(tokens):
    """Acepta Token posicionados o pares (TIPO, lexema) del lexer docente."""
    normalizados = []
    for indice, token in enumerate(tokens):
        if isinstance(token, Token):
            normalizados.append(token)
        else:
            tipo, lexema = token
            normalizados.append(Token(tipo, lexema, None, None, None))
        if normalizados[-1].tipo not in ANALISIS.columnas:
            raise ValueError(f'Tipo de token desconocido en la posición {indice}: {normalizados[-1].tipo!r}')
    if not normalizados or normalizados[-1].tipo != EOF:
        ultimo = normalizados[-1] if normalizados else None
        if ultimo is not None and ultimo.linea is not None:
            normalizados.append(Token(EOF, '', ultimo.linea, ultimo.columna + len(ultimo.lexema),
                                      ultimo.posicion + len(ultimo.lexema)))
        else:
            normalizados.append(Token(EOF, '', None, None, None))
    if any(t.tipo == EOF for t in normalizados[:-1]):
        raise ValueError('EOF solo puede aparecer al final de la secuencia de tokens.')
    return normalizados


def _viables(pila):
    """Terminales que pueden continuar la entrada con esta pila (cima al final)."""
    resultado = set()
    for nodo in reversed(pila):
        simbolo = nodo.simbolo
        if not GRAMATICA.es_no_terminal(simbolo):
            resultado.add(simbolo)
            return resultado
        resultado |= ANALISIS.first[simbolo] - {EPS}
        if simbolo not in ANALISIS.anulables:
            return resultado
    return resultado


def _error(tokens, i, pila, esperados, parentesis):
    actual = tokens[i]
    previo = tokens[i - 1] if i > 0 else None
    cima = pila[-1].simbolo
    esperados = ANALISIS.ordenar(esperados)
    encontrado = describir_token(actual)
    if actual.tipo == EOF and i == 0:
        mensaje = 'la entrada está vacía: se esperaba al menos una regla que comience con WHEN.'
    elif cima == 'Resto':
        mensaje = ('contenido sobrante después del fin de la regla: se esperaba WHEN (una nueva regla) '
                   f'o el fin de la entrada, pero se encontró {encontrado}.')
    elif actual.tipo == 'PARENT_DER' and not parentesis:
        mensaje = (f"paréntesis de cierre ')' sin '(' de apertura; se esperaba "
                   f'{_frase_esperados(esperados, previo)} {_frase_previo(previo)}.')
    else:
        mensaje = (f'se esperaba {_frase_esperados(esperados, previo)} {_frase_previo(previo)}, '
                   f'pero se encontró {encontrado}.')
        if actual.tipo == EOF:
            mensaje = mensaje[:-1] + ' (regla incompleta).'
    if 'PARENT_DER' in esperados and parentesis:
        abierto = parentesis[-1]
        donde = (f'en línea {abierto.linea}, columna {abierto.columna}' if abierto.linea is not None
                 else 'antes')
        mensaje += f" El '(' abierto {donde} sigue sin cerrar."
    linea, columna, posicion = actual.linea, actual.columna, actual.posicion
    if actual.tipo == EOF and previo is not None and previo.linea is not None:
        # Fin de entrada: se señala justo después del último token, no tras los blancos finales.
        linea, columna = previo.linea, previo.columna + len(previo.lexema)
        posicion = previo.posicion + len(previo.lexema)
    raise ErrorSintactico(mensaje, linea, columna, posicion,
                          encontrado=actual.lexema, esperados=esperados, contexto=cima,
                          longitud=len(actual.lexema), indice=i)


def _texto_pila(pila):
    return ' '.join(n.simbolo for n in pila)


def _texto_entrada(tokens, i, maximo=8):
    resto = [t.tipo for t in tokens[i:]]
    if len(resto) > maximo:
        resto = resto[:maximo - 1] + ['…', resto[-1]]
    return ' '.join(resto)


def analizar_tokens(tokens, *, traza=None, deteccion_inmediata=True):
    """Reconoce una secuencia de tokens y devuelve la raíz del árbol concreto.

    ``traza``: lista opcional donde se agregan tuplas (pila, entrada, acción).
    Lanza ErrorSintactico ante el primer error (no hay recuperación).
    """
    tokens = _normalizar(tokens)
    raiz = Nodo(GRAMATICA.inicial)
    pila = [Nodo(EOF), raiz]
    parentesis = []    # tokens '(' aún abiertos, para los mensajes de error
    i = 0
    while pila:
        cima = pila[-1]
        actual = tokens[i]
        if not GRAMATICA.es_no_terminal(cima.simbolo):          # terminal o EOF
            if cima.simbolo != actual.tipo:
                _error(tokens, i, pila, [cima.simbolo], parentesis)
            if traza is not None:
                traza.append((_texto_pila(pila), _texto_entrada(tokens, i),
                              f'coincidir {actual.tipo}'))
            pila.pop()
            cima.token = actual
            if actual.tipo == 'PARENT_IZQ':
                parentesis.append(actual)
            elif actual.tipo == 'PARENT_DER':
                parentesis.pop()
            if actual.tipo != EOF:
                i += 1
            continue
        produccion = ANALISIS.tabla.get((cima.simbolo, actual.tipo))
        if produccion is None:
            esperados = _viables(pila) if deteccion_inmediata else ANALISIS.fila(cima.simbolo)
            _error(tokens, i, pila, esperados, parentesis)
        if deteccion_inmediata and not produccion.derecha:
            viables = _viables(pila)
            if actual.tipo not in viables:
                _error(tokens, i, pila, viables, parentesis)
        if traza is not None:
            celda = f'M[{cima.simbolo}, {actual.tipo}] = ({produccion.numero}) {produccion}'
            traza.append((_texto_pila(pila), _texto_entrada(tokens, i), celda))
        pila.pop()
        cima.produccion = produccion
        if produccion.derecha:
            cima.hijos = [Nodo(simbolo) for simbolo in produccion.derecha]
            pila.extend(reversed(cima.hijos))
        else:
            cima.hijos = [Nodo(EPS)]
    if traza is not None:
        traza.append(('', '', 'aceptar'))
    return raiz


def analizar(fuente, **opciones):
    """Texto → árbol concreto. Lanza ErrorLexico o ErrorSintactico."""
    return analizar_tokens(tokenizar(fuente), **opciones)


def derivacion_izquierda(raiz):
    """Producciones en el orden de la derivación por la izquierda (preorden) y formas sentenciales."""
    producciones = [n.produccion for n in raiz.preorden() if n.produccion is not None]
    formas = [[raiz.simbolo]]
    forma = [raiz.simbolo]
    for p in producciones:
        k = next(j for j, s in enumerate(forma) if GRAMATICA.es_no_terminal(s))
        if forma[k] != p.izquierda:
            raise AssertionError('La derivación no es por la izquierda.')
        forma = forma[:k] + list(p.derecha) + forma[k + 1:]
        formas.append(forma)
    return producciones, formas
