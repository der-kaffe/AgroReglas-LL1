"""Algoritmos propios del análisis LL(1) (sin bibliotecas de parsers).

Todos operan sobre cualquier ``Gramatica``: así se analizan la gramática final
G2 y las versiones previas G0 y G1 con el mismo código.

* Anulables, FIRST y FOLLOW: iteración hasta punto fijo. Los conjuntos solo
  crecen y están acotados por los símbolos finitos de la gramática, por lo que
  el cálculo termina.
* SELECT(A → α) = FIRST(α) − {ε}, más FOLLOW(A) si α es anulable.
* Tabla: M[A, a] = A → α para cada a ∈ SELECT(A → α). Una celda con dos
  producciones es un conflicto: la gramática no es LL(1).
* Recursión izquierda: grafo de esquina izquierda (A → B si existe A → α B β
  con α anulable); A es recursivo por la izquierda si alcanza a A en ese grafo.
* Prefijos comunes: pares de alternativas de un mismo no terminal que comparten
  su primer símbolo (requieren factorización por la izquierda).
"""
from collections import defaultdict, deque
from dataclasses import dataclass

from .gramatica import EOF, EPS, GRAMATICA


def calcular_anulables(g):
    anulables = set()
    cambio = True
    while cambio:
        cambio = False
        for p in g.producciones:
            if p.izquierda not in anulables and all(s in anulables for s in p.derecha):
                anulables.add(p.izquierda)
                cambio = True
    return anulables


def first_secuencia(secuencia, first, g):
    """FIRST de una secuencia de símbolos; incluye ε si toda la secuencia es anulable."""
    resultado = set()
    for simbolo in secuencia:
        conjunto = first[simbolo] if g.es_no_terminal(simbolo) else {simbolo}
        resultado |= conjunto - {EPS}
        if EPS not in conjunto:
            return resultado
    resultado.add(EPS)
    return resultado


def calcular_first(g):
    """Devuelve (FIRST, número de pasadas hasta el punto fijo)."""
    first = {a: set() for a in g.no_terminales}
    pasadas, cambio = 0, True
    while cambio:
        cambio, pasadas = False, pasadas + 1
        for p in g.producciones:
            nuevo = first_secuencia(p.derecha, first, g)
            if not nuevo <= first[p.izquierda]:
                first[p.izquierda] |= nuevo
                cambio = True
    return first, pasadas


def calcular_follow(g, first):
    """Devuelve (FOLLOW, número de pasadas). FOLLOW(S) contiene EOF ($)."""
    follow = {a: set() for a in g.no_terminales}
    follow[g.inicial].add(EOF)
    pasadas, cambio = 0, True
    while cambio:
        cambio, pasadas = False, pasadas + 1
        for p in g.producciones:
            for i, simbolo in enumerate(p.derecha):
                if not g.es_no_terminal(simbolo):
                    continue
                resto = first_secuencia(p.derecha[i + 1:], first, g)
                nuevo = resto - {EPS}
                if EPS in resto:                  # β anulable (o vacía): hereda FOLLOW(A)
                    nuevo |= follow[p.izquierda]
                if not nuevo <= follow[simbolo]:
                    follow[simbolo] |= nuevo
                    cambio = True
    return follow, pasadas


def conjunto_seleccion(p, first, follow, g):
    inicio = first_secuencia(p.derecha, first, g)
    seleccion = inicio - {EPS}
    if EPS in inicio:
        seleccion |= follow[p.izquierda]
    return seleccion


@dataclass(frozen=True)
class Conflicto:
    no_terminal: str
    terminal: str
    producciones: tuple  # números de las producciones que compiten por la celda


def construir_tabla(g, seleccion):
    """Tabla dispersa {(A, a): Produccion} y lista de conflictos."""
    celdas = defaultdict(list)
    for p in g.producciones:
        for terminal in seleccion[p.numero]:
            celdas[p.izquierda, terminal].append(p)
    orden = {s: i for i, s in enumerate(g.no_terminales + g.terminales + [EOF])}
    conflictos = [Conflicto(a, t, tuple(q.numero for q in ps))
                  for (a, t), ps in celdas.items() if len(ps) > 1]
    conflictos.sort(key=lambda c: (orden[c.no_terminal], orden[c.terminal]))
    tabla = {clave: ps[0] for clave, ps in celdas.items()}
    return tabla, conflictos


def grafo_esquina_izquierda(g, anulables):
    grafo = {a: [] for a in g.no_terminales}
    for p in g.producciones:
        for simbolo in p.derecha:
            if not g.es_no_terminal(simbolo):
                break
            if simbolo not in grafo[p.izquierda]:
                grafo[p.izquierda].append(simbolo)
            if simbolo not in anulables:
                break
    return grafo


def recursion_izquierda(g, grafo):
    """Devuelve (directa, indirecta). indirecta = {A: ciclo [A, B, ..., A] de largo ≥ 2}."""
    directa = [a for a in g.no_terminales if a in grafo[a]]
    indirecta = {}
    for a in g.no_terminales:
        padres = {}
        cola = deque()
        for b in grafo[a]:
            if b != a and b not in padres:
                padres[b] = a
                cola.append(b)
        while cola:
            actual = cola.popleft()
            if actual == a:
                ciclo = [a]
                nodo = padres[a]
                while nodo != a:
                    ciclo.append(nodo)
                    nodo = padres[nodo]
                indirecta[a] = [a] + ciclo[:0:-1] + [a]
                break
            for siguiente in grafo[actual]:
                if siguiente not in padres:
                    padres[siguiente] = actual
                    cola.append(siguiente)
    return directa, indirecta


def prefijos_comunes(g):
    """[(A, n.º producción, n.º producción, prefijo común)] entre alternativas de A."""
    hallazgos = []
    for a in g.no_terminales:
        alternativas = g.alternativas(a)
        for i, p in enumerate(alternativas):
            for q in alternativas[i + 1:]:
                k = 0
                while k < min(len(p.derecha), len(q.derecha)) and p.derecha[k] == q.derecha[k]:
                    k += 1
                if k:
                    hallazgos.append((a, p.numero, q.numero, p.derecha[:k]))
    return hallazgos


@dataclass
class AnalisisLL1:
    gramatica: object
    anulables: set
    first: dict
    follow: dict
    seleccion: dict          # n.º de producción -> conjunto SELECT
    tabla: dict              # (A, a) -> Produccion
    conflictos: list
    grafo_izquierdo: dict
    recursion_directa: list
    recursion_indirecta: dict
    prefijos: list
    pasadas_first: int
    pasadas_follow: int

    @property
    def es_ll1(self):
        return not self.conflictos

    @property
    def columnas(self):
        """Terminales en orden canónico más EOF: columnas de la tabla."""
        return self.gramatica.terminales + [EOF]

    def ordenar(self, simbolos):
        """Ordena según las columnas de la tabla, luego ε y luego los no terminales."""
        indice = {s: i for i, s in enumerate(self.columnas + [EPS] + self.gramatica.no_terminales)}
        return sorted(simbolos, key=lambda s: indice.get(s, len(indice)))

    def fila(self, no_terminal):
        """Terminales con entrada definida en la fila de A (los demás son ERROR)."""
        return self.ordenar(t for (a, t) in self.tabla if a == no_terminal)


def analizar_gramatica(g):
    anulables = calcular_anulables(g)
    first, pasadas_first = calcular_first(g)
    follow, pasadas_follow = calcular_follow(g, first)
    seleccion = {p.numero: conjunto_seleccion(p, first, follow, g) for p in g.producciones}
    tabla, conflictos = construir_tabla(g, seleccion)
    grafo = grafo_esquina_izquierda(g, anulables)
    directa, indirecta = recursion_izquierda(g, grafo)
    return AnalisisLL1(g, anulables, first, follow, seleccion, tabla, conflictos, grafo,
                       directa, indirecta, prefijos_comunes(g), pasadas_first, pasadas_follow)


# Análisis de la gramática final, calculado una sola vez al importar el módulo.
ANALISIS = analizar_gramatica(GRAMATICA)
if not ANALISIS.es_ll1:
    raise RuntimeError(f'La gramática final no es LL(1): {ANALISIS.conflictos}')
