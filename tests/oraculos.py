"""Oráculos independientes para pruebas diferenciales (solo se usan en las pruebas).

* ``reconoce_earley``: reconocedor de Earley, válido para cualquier GLC, incluso
  ambigua o recursiva por la izquierda. Permite comparar el parser LL(1) de G2
  con la gramática inicial G0 sin usar la tabla LL(1).
* ``generar``: produce oraciones aleatorias (secuencias de tipos de token) de
  una gramática, con profundidad acotada.
* ``mutar``: aplica una edición aleatoria (borrar, insertar o reemplazar un token).
* ``a_texto``: asigna lexemas a una secuencia de tipos para obtener texto fuente.
"""
import random

from agroreglas.gramatica import EPS
from agroreglas.ll1 import calcular_anulables


def reconoce_earley(g, tipos):
    """True si la secuencia de tipos de token pertenece a L(g)."""
    anulables = calcular_anulables(g)
    inicio = ('S′', (g.inicial,), 0, 0)
    n = len(tipos)
    conjuntos = [set() for _ in range(n + 1)]
    conjuntos[0].add(inicio)
    for i in range(n + 1):
        agenda = list(conjuntos[i])
        while agenda:
            izquierda, derecha, punto, origen = agenda.pop()
            nuevos = []
            if punto < len(derecha):
                simbolo = derecha[punto]
                if g.es_no_terminal(simbolo):                       # predicción
                    nuevos += [(simbolo, p.derecha, 0, i) for p in g.alternativas(simbolo)]
                    if simbolo in anulables:                        # corrección de Aycock y Horspool
                        nuevos.append((izquierda, derecha, punto + 1, origen))
                elif i < n and tipos[i] == simbolo:                 # lectura
                    conjuntos[i + 1].add((izquierda, derecha, punto + 1, origen))
            else:                                                   # compleción
                nuevos += [(iz, de, pu + 1, orig) for (iz, de, pu, orig) in list(conjuntos[origen])
                           if pu < len(de) and de[pu] == izquierda]
            for item in nuevos:
                if item not in conjuntos[i]:
                    conjuntos[i].add(item)
                    agenda.append(item)
    return ('S′', (g.inicial,), 1, 0) in conjuntos[n]


def _alturas(g):
    """Altura mínima de derivación de cada no terminal (para cortar la recursión)."""
    altura = {a: float('inf') for a in g.no_terminales}
    cambio = True
    while cambio:
        cambio = False
        for p in g.producciones:
            h = 1 + max((altura[s] for s in p.derecha if g.es_no_terminal(s)), default=0)
            if h < altura[p.izquierda]:
                altura[p.izquierda] = h
                cambio = True
    return altura


def generar(g, rng, profundidad_maxima=7):
    """Oración aleatoria de L(g) como lista de tipos de token."""
    altura = _alturas(g)

    def costo(p):
        return max((altura[s] for s in p.derecha if g.es_no_terminal(s)), default=0)

    salida = []
    pila = [(g.inicial, 0)]
    while pila:
        simbolo, nivel = pila.pop()
        if not g.es_no_terminal(simbolo):
            salida.append(simbolo)
            continue
        alternativas = g.alternativas(simbolo)
        if nivel >= profundidad_maxima:
            minimo = min(costo(p) for p in alternativas)
            alternativas = [p for p in alternativas if costo(p) == minimo]
        p = rng.choice(alternativas)
        pila.extend((s, nivel + 1) for s in reversed(p.derecha))
    return salida


def mutar(tipos, terminales, rng):
    tipos = list(tipos)
    operacion = rng.choice(['borrar', 'insertar', 'reemplazar'])
    posicion = rng.randrange(len(tipos) + (operacion == 'insertar'))
    if operacion == 'borrar' and tipos:
        del tipos[posicion]
    elif operacion == 'insertar':
        tipos.insert(posicion, rng.choice(terminales))
    elif tipos:
        tipos[posicion] = rng.choice(terminales)
    return tipos


LEXEMAS = {
    'ID': ['humedad', 'lluvia', 'viento', 'temperatura', 'regar', 'activar', 'sector_norte', 'bomba', 'valvula_1'],
    'NUM': ['0', '5', '15', '30', '40', '120'],
    'OP_REL': ['<', '<=', '>', '>=', '==', '!='],
    'PUNTO_COMA': [';'], 'PARENT_IZQ': ['('], 'PARENT_DER': [')'],
}


def a_texto(tipos, rng):
    return ' '.join(rng.choice(LEXEMAS[t]) if t in LEXEMAS else t for t in tipos if t != EPS)


def nuevo_rng(semilla=1148):
    return random.Random(semilla)
