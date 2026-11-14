"""Gramáticas libres de contexto de AgroReglas.

``GRAMATICA`` es la gramática final G2 y la única fuente de verdad: de ella se
calculan FIRST, FOLLOW, la tabla LL(1), el parser, las tablas del informe y los
archivos de ``resultados/``. ``G0`` y ``G1`` son las versiones previas que se
analizan en el informe para justificar las transformaciones.

Notación del texto: una línea por no terminal, ``->`` separa lados, ``|`` separa
alternativas y ``ε`` denota la cadena vacía. Los símbolos que aparecen a la
izquierda de alguna línea son no terminales; los demás son terminales (tipos de
token). EOF no pertenece a T: es el marcador de fin ($) que agrega el análisis.
"""
from dataclasses import dataclass

EPS = 'ε'
EOF = 'EOF'

# Orden canónico de terminales para tablas, mensajes y archivos.
ORDEN_TERMINALES = ['WHEN', 'THEN', 'ID', 'OP_REL', 'NUM', 'TRUE', 'FALSE', 'NOT',
                    'AND', 'OR', 'PARENT_IZQ', 'PARENT_DER', 'DURING', 'PUNTO_COMA']


@dataclass(frozen=True)
class Produccion:
    numero: int
    izquierda: str
    derecha: tuple  # () representa ε

    def __str__(self):
        return f'{self.izquierda} → {" ".join(self.derecha) if self.derecha else EPS}'


class Gramatica:
    """G = (N, T, P, S) construida desde texto; numera las producciones desde 1."""

    def __init__(self, nombre, texto):
        self.nombre = nombre
        reglas = []
        for numero_linea, linea in enumerate(texto.strip().splitlines(), 1):
            if not linea.strip():
                continue
            if '->' not in linea:
                raise ValueError(f'Línea {numero_linea} de la gramática sin "->": {linea!r}')
            izquierda, derecha = (parte.strip() for parte in linea.split('->', 1))
            for alternativa in derecha.split('|'):
                simbolos = tuple(alternativa.split())
                reglas.append((izquierda, () if simbolos == (EPS,) else simbolos))
        self.producciones = [Produccion(i, izq, der) for i, (izq, der) in enumerate(reglas, 1)]
        self.no_terminales = list(dict.fromkeys(p.izquierda for p in self.producciones))
        self._conjunto_nt = frozenset(self.no_terminales)
        self.inicial = self.no_terminales[0]
        usados = {s for p in self.producciones for s in p.derecha}
        if EPS in usados:
            raise ValueError('ε solo puede aparecer como alternativa completa.')
        otros = usados - self._conjunto_nt
        self.terminales = ([t for t in ORDEN_TERMINALES if t in otros]
                           + sorted(otros - set(ORDEN_TERMINALES)))

    def es_no_terminal(self, simbolo):
        return simbolo in self._conjunto_nt

    def alternativas(self, no_terminal):
        return [p for p in self.producciones if p.izquierda == no_terminal]

    def produccion(self, numero):
        return self.producciones[numero - 1]

    def texto(self):
        """Producciones agrupadas por no terminal, en el formato de entrada."""
        ancho = max(len(nt) for nt in self.no_terminales)
        return '\n'.join(
            f'{nt:<{ancho}} -> ' + ' | '.join(' '.join(p.derecha) or EPS for p in self.alternativas(nt))
            for nt in self.no_terminales)


# G2: gramática final (LL(1)), 23 producciones.
TEXTO_G2 = """
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
"""

# G0: primera formulación "natural". Ambigua, con recursión izquierda y prefijos comunes.
TEXTO_G0 = """
Programa    -> Regla Programa | Regla
Regla       -> WHEN Condicion THEN Acciones PUNTO_COMA
Condicion   -> Condicion OR Condicion | Condicion AND Condicion | NOT Condicion | PARENT_IZQ Condicion PARENT_DER | Comparacion
Comparacion -> ID OP_REL Valor
Valor       -> NUM | TRUE | FALSE
Acciones    -> Acciones AND Accion | Accion
Accion      -> ID ID | ID ID DURING NUM
"""

# G1: niveles de precedencia (no ambigua), aún con recursión izquierda y prefijos comunes.
TEXTO_G1 = """
Programa    -> Regla Programa | Regla
Regla       -> WHEN Condicion THEN Acciones PUNTO_COMA
Condicion   -> Condicion OR Conjuncion | Conjuncion
Conjuncion  -> Conjuncion AND Factor | Factor
Factor      -> NOT Factor | PARENT_IZQ Condicion PARENT_DER | Comparacion
Comparacion -> ID OP_REL Valor
Valor       -> NUM | TRUE | FALSE
Acciones    -> Acciones AND Accion | Accion
Accion      -> ID ID | ID ID DURING NUM
"""

GRAMATICA = Gramatica('G2 (final)', TEXTO_G2)
G0 = Gramatica('G0 (inicial)', TEXTO_G0)
G1 = Gramatica('G1 (precedencia)', TEXTO_G1)
