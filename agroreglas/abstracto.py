"""Árbol de sintaxis abstracta (AST) obtenido desde el árbol concreto.

Se usa una definición dirigida por la sintaxis S-atribuida: cada producción
tiene una regla semántica (``REGLAS_SEMANTICAS``) que calcula el valor del nodo
a partir de los valores de sus hijos. El recorrido es postorden iterativo.

El AST elimina lo que solo sirve para reconocer: palabras clave, paréntesis,
';', las colas ColaOr/ColaAnd/ColaAcciones/Resto y las hojas ε. Las colas,
recursivas por la derecha en la gramática, se pliegan a la izquierda:
``a OR b OR c`` produce OR(OR(a, b), c). Como AND y OR son asociativos, esa
convención no cambia el significado, pero deja una estructura única.
La agrupación de los paréntesis queda expresada en la forma del árbol.
"""
from dataclasses import dataclass, field

from .arbol import a_dot, renderizar
from .gramatica import GRAMATICA


@dataclass
class Programa:
    reglas: list


@dataclass
class Regla:
    condicion: object
    acciones: list
    linea: int | None = None


@dataclass
class OperacionLogica:
    operador: str        # 'AND' u 'OR'
    izquierda: object
    derecha: object


@dataclass
class Negacion:
    operando: object


@dataclass
class Comparacion:
    sensor: str
    operador: str        # <, <=, >, >=, ==, !=
    valor: object        # int o bool


@dataclass
class Accion:
    verbo: str
    objetivo: str
    duracion: int | None = None   # minutos (extensión DURING) o None


def texto_valor(valor):
    if isinstance(valor, bool):
        return 'TRUE' if valor else 'FALSE'
    return str(valor)


def _plegar(operador, primero, cola_invertida):
    """Asociatividad izquierda: ((x1 op x2) op x3) ..."""
    resultado = primero
    for operando in reversed(cola_invertida):
        resultado = OperacionLogica(operador, resultado, operando)
    return resultado


def _agregar(lista, elemento):
    """Las colas acumulan sus elementos en orden inverso (agregar al final es O(1))."""
    lista.append(elemento)
    return lista


def _linea(token):
    return token.linea


# Regla semántica por número de producción; h es la lista de valores de los hijos
# (tokens para las hojas terminales y None para ε).
REGLAS_SEMANTICAS = {
    1: lambda h: Programa([h[0]] + h[1][::-1]),                    # Programa → Regla Resto
    2: lambda h: _agregar(h[1], h[0]),                             # Resto → Regla Resto
    3: lambda h: [],                                               # Resto → ε
    4: lambda h: Regla(h[1], h[3], _linea(h[0])),                  # Regla → WHEN Condicion THEN Acciones ;
    5: lambda h: _plegar('OR', h[0], h[1]),                        # Condicion → Conjuncion ColaOr
    6: lambda h: _agregar(h[2], h[1]),                             # ColaOr → OR Conjuncion ColaOr
    7: lambda h: [],                                               # ColaOr → ε
    8: lambda h: _plegar('AND', h[0], h[1]),                       # Conjuncion → Factor ColaAnd
    9: lambda h: _agregar(h[2], h[1]),                             # ColaAnd → AND Factor ColaAnd
    10: lambda h: [],                                              # ColaAnd → ε
    11: lambda h: Negacion(h[1]),                                  # Factor → NOT Factor
    12: lambda h: h[1],                                            # Factor → ( Condicion )
    13: lambda h: h[0],                                            # Factor → Comparacion
    14: lambda h: Comparacion(h[0].lexema, h[1].lexema, h[2]),     # Comparacion → ID OP_REL Valor
    15: lambda h: int(h[0].lexema),                                # Valor → NUM
    16: lambda h: True,                                            # Valor → TRUE
    17: lambda h: False,                                           # Valor → FALSE
    18: lambda h: [h[0]] + h[1][::-1],                             # Acciones → Accion ColaAcciones
    19: lambda h: _agregar(h[2], h[1]),                            # ColaAcciones → AND Accion ColaAcciones
    20: lambda h: [],                                              # ColaAcciones → ε
    21: lambda h: Accion(h[0].lexema, h[1].lexema, h[2]),          # Accion → ID ID Duracion
    22: lambda h: int(h[1].lexema),                                # Duracion → DURING NUM
    23: lambda h: None,                                            # Duracion → ε
}
assert set(REGLAS_SEMANTICAS) == {p.numero for p in GRAMATICA.producciones}


def construir_ast(raiz):
    """Evalúa las reglas semánticas en postorden iterativo y devuelve un Programa."""
    valores = {}
    pila = [(raiz, False)]
    while pila:
        nodo, visitado = pila.pop()
        if nodo.produccion is None:                  # hoja: token o ε
            valores[id(nodo)] = nodo.token
            continue
        if not visitado:
            pila.append((nodo, True))
            pila.extend((hijo, False) for hijo in nodo.hijos)
            continue
        hijos = [valores.pop(id(hijo)) for hijo in nodo.hijos]
        valores[id(nodo)] = REGLAS_SEMANTICAS[nodo.produccion.numero](hijos)
    return valores[id(raiz)]


# ---------------------------------------------------------------- presentación
@dataclass
class _Grupo:
    """Nodo de presentación sin significado propio (Condición, Acciones)."""
    nombre: str
    hijos: list = field(default_factory=list)


def _hijos(nodo):
    if isinstance(nodo, Programa):
        return nodo.reglas
    if isinstance(nodo, Regla):
        return [_Grupo('Condición', [nodo.condicion]), _Grupo('Acciones', nodo.acciones)]
    if isinstance(nodo, _Grupo):
        return nodo.hijos
    if isinstance(nodo, OperacionLogica):
        return [nodo.izquierda, nodo.derecha]
    if isinstance(nodo, Negacion):
        return [nodo.operando]
    if isinstance(nodo, Accion):
        hojas = [_Grupo(f'verbo: {nodo.verbo}'), _Grupo(f'objetivo: {nodo.objetivo}')]
        if nodo.duracion is not None:
            hojas.append(_Grupo(f'DURING: {nodo.duracion} min'))
        return hojas
    return []


def _etiqueta(nodo):
    if isinstance(nodo, Programa):
        return f'Programa ({len(nodo.reglas)} regla{"s" if len(nodo.reglas) != 1 else ""})'
    if isinstance(nodo, Regla):
        return f'Regla (línea {nodo.linea})' if nodo.linea is not None else 'Regla'
    if isinstance(nodo, _Grupo):
        return nodo.nombre
    if isinstance(nodo, OperacionLogica):
        return nodo.operador
    if isinstance(nodo, Negacion):
        return 'NOT'
    if isinstance(nodo, Comparacion):
        return f'{nodo.sensor} {nodo.operador} {texto_valor(nodo.valor)}'
    if isinstance(nodo, Accion):
        return 'Acción'
    return str(nodo)


def _forma(nodo):
    if isinstance(nodo, (OperacionLogica, Negacion)):
        return 'shape=circle, style=filled, fillcolor="#fde9c9"'
    if isinstance(nodo, Comparacion):
        return 'shape=box, style="rounded,filled", fillcolor="#e8f1e4"'
    if isinstance(nodo, _Grupo) and not nodo.hijos:
        return 'shape=box, style="rounded,filled", fillcolor="#e3ecf7"'
    return 'shape=ellipse'


def texto_ast(nodo, unicode=True):
    return renderizar(nodo, _hijos, _etiqueta, unicode)


def dot_ast(nodo, titulo='AST de AgroReglas'):
    return a_dot(nodo, _hijos, _etiqueta, _forma, titulo)


def formula(expresion):
    """Condición en notación prefija: AND(humedad < 30, NOT(lluvia == TRUE)). Iterativa."""
    salida, pila = [], [expresion]
    while pila:
        x = pila.pop()
        if isinstance(x, str):
            salida.append(x)
        elif isinstance(x, Comparacion):
            salida.append(f'{x.sensor} {x.operador} {texto_valor(x.valor)}')
        elif isinstance(x, Negacion):
            pila.extend([')', x.operando, 'NOT('])
        else:
            pila.extend([')', x.derecha, ', ', x.izquierda, f'{x.operador}('])
    return ''.join(salida)
