"""Árbol sintáctico concreto (árbol de derivación) y su presentación.

El parser construye un ``Nodo`` por cada símbolo de cada producción aplicada:
los nodos internos son no terminales, las hojas son terminales (con su token) o
ε. Los recorridos son iterativos para no depender del límite de recursión de
Python con entradas largas o muy anidadas.
"""
from .gramatica import EPS


class Nodo:
    __slots__ = ('simbolo', 'token', 'hijos', 'produccion')

    def __init__(self, simbolo):
        self.simbolo = simbolo
        self.token = None        # Token consumido (solo hojas terminales)
        self.hijos = []
        self.produccion = None   # Produccion aplicada (solo nodos internos)

    def etiqueta(self):
        if self.token is not None:
            return f"{self.simbolo} '{self.token.lexema}'" if self.token.lexema else self.simbolo
        return self.simbolo

    def preorden(self):
        pila = [self]
        while pila:
            nodo = pila.pop()
            yield nodo
            pila.extend(reversed(nodo.hijos))

    def frontera(self):
        """Tokens de las hojas, de izquierda a derecha (sin ε)."""
        return [n.token for n in self.preorden() if n.token is not None]

    def texto(self, unicode=True):
        return renderizar(self, lambda n: n.hijos, Nodo.etiqueta, unicode)

    def dot(self, titulo='Árbol sintáctico concreto'):
        def forma(n):
            if n.simbolo == EPS:
                return 'shape=plaintext, fontcolor="#777777"'
            if n.token is not None:
                return 'shape=box, style="rounded,filled", fillcolor="#e8f1e4"'
            return 'shape=ellipse'
        return a_dot(self, lambda n: n.hijos, Nodo.etiqueta, forma, titulo)


def renderizar(raiz, hijos_de, etiqueta_de, unicode=True):
    """Texto jerárquico con ramas (├── └──, o +-- `-- en modo ASCII)."""
    rama, ultima, vertical, vacio = (('├── ', '└── ', '│   ', '    ') if unicode
                                     else ('+-- ', '`-- ', '|   ', '    '))
    lineas = []
    pila = [(raiz, '', None)]
    while pila:
        nodo, prefijo, es_ultimo = pila.pop()
        if es_ultimo is None:
            lineas.append(etiqueta_de(nodo))
            prefijo_hijos = ''
        else:
            lineas.append(prefijo + (ultima if es_ultimo else rama) + etiqueta_de(nodo))
            prefijo_hijos = prefijo + (vacio if es_ultimo else vertical)
        hijos = hijos_de(nodo)
        for i in range(len(hijos) - 1, -1, -1):
            pila.append((hijos[i], prefijo_hijos, i == len(hijos) - 1))
    return '\n'.join(lineas)


def _escapar_dot(texto):
    return texto.replace('\\', '\\\\').replace('"', '\\"')


def a_dot(raiz, hijos_de, etiqueta_de, forma_de, titulo):
    """Descripción Graphviz (DOT) del árbol; se dibuja con ``dot -Tpng``."""
    lineas = ['digraph arbol {',
              f'  label="{_escapar_dot(titulo)}"; labelloc=t; fontname="Helvetica";',
              '  node [fontname="Helvetica", fontsize=11]; edge [arrowhead=none];']
    # Un solo recorrido: hijos_de puede crear nodos de presentación nuevos en cada llamada.
    aristas = []
    pila = [(raiz, None)]
    contador = 0
    while pila:
        nodo, padre = pila.pop()
        nombre = f'n{contador}'
        contador += 1
        lineas.append(f'  {nombre} [label="{_escapar_dot(etiqueta_de(nodo))}", {forma_de(nodo)}];')
        if padre is not None:
            aristas.append(f'  {padre} -> {nombre};')
        pila.extend((hijo, nombre) for hijo in reversed(hijos_de(nodo)))
    lineas.extend(aristas)
    lineas.append('}')
    return '\n'.join(lineas)
