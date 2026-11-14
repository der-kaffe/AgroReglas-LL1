"""Árbol concreto, derivación por la izquierda y AST (precedencia, agrupación y DURING)."""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

from agroreglas import analizar, construir_ast, derivacion_izquierda, formula, texto_ast, tokenizar
from agroreglas.abstracto import Accion, Comparacion, dot_ast
from agroreglas.gramatica import EPS, GRAMATICA
from casos import CASOS, EJEMPLO_PRINCIPAL


def ast_de(texto):
    return construir_ast(analizar(texto))


def condicion(texto_condicion):
    return formula(ast_de(f'WHEN {texto_condicion} THEN x y;').reglas[0].condicion)


class ArbolConcreto(unittest.TestCase):
    def test_cada_nodo_interno_aplica_una_produccion_de_G(self):
        for caso in CASOS:
            if caso.esperado != 'ACEPTA':
                continue
            with self.subTest(caso=caso.id):
                arbol = analizar(caso.entrada)
                for nodo in arbol.preorden():
                    if nodo.produccion is None:
                        continue
                    self.assertIn(nodo.produccion, GRAMATICA.producciones)
                    self.assertEqual(nodo.simbolo, nodo.produccion.izquierda)
                    hijos = tuple(h.simbolo for h in nodo.hijos)
                    self.assertEqual(hijos, nodo.produccion.derecha or (EPS,))

    def test_frontera_igual_a_la_entrada(self):
        tokens = tokenizar(EJEMPLO_PRINCIPAL)
        self.assertEqual(analizar(EJEMPLO_PRINCIPAL).frontera(), tokens[:-1])

    def test_precedencia_visible_en_el_arbol_concreto(self):
        """En 'a OR b AND c' el AND queda dentro del segundo operando del OR."""
        arbol = analizar('WHEN a == 1 OR b == 2 AND c == 3 THEN x y;')
        condicion_ = arbol.hijos[0].hijos[1]
        cola_or = condicion_.hijos[1]
        self.assertEqual([h.simbolo for h in cola_or.hijos], ['OR', 'Conjuncion', 'ColaOr'])
        cola_and = cola_or.hijos[1].hijos[1]
        self.assertEqual([h.simbolo for h in cola_and.hijos], ['AND', 'Factor', 'ColaAnd'])
        self.assertEqual(condicion_.hijos[0].hijos[1].hijos[0].simbolo, EPS)   # primer nivel sin AND

    def test_durante_en_el_arbol_concreto(self):
        arbol = analizar('WHEN h < 1 THEN regar norte DURING 15 AND activar alarma;')
        duraciones = [n for n in arbol.preorden() if n.simbolo == 'Duracion']
        self.assertEqual([n.produccion.numero for n in duraciones], [22, 23])
        self.assertEqual([h.etiqueta() for h in duraciones[0].hijos], ["DURING 'DURING'", "NUM '15'"])

    def test_derivacion_por_la_izquierda(self):
        arbol = analizar('WHEN humedad < 30 THEN regar sector_sur DURING 15;')
        producciones, formas = derivacion_izquierda(arbol)
        self.assertEqual(formas[0], ['Programa'])
        self.assertEqual(formas[-1], [t.tipo for t in tokenizar('WHEN h < 1 THEN a b DURING 2;')[:-1]])
        self.assertEqual([p.numero for p in producciones], [1, 4, 5, 8, 13, 14, 15, 10, 7, 18, 21, 22, 20, 3])
        self.assertEqual(len(formas), len(producciones) + 1)

    def test_presentacion_texto_y_dot(self):
        arbol = analizar('WHEN h < 1 THEN a b;')
        self.assertIn('└── Resto', arbol.texto())
        self.assertIn('`-- Resto', arbol.texto(unicode=False))
        dot = arbol.dot()
        self.assertTrue(dot.startswith('digraph'))
        self.assertEqual(dot.count('label="') - 1, sum(1 for _ in arbol.preorden()))


class AST(unittest.TestCase):
    def test_NOT_mayor_que_AND_mayor_que_OR(self):
        casos = {
            'a == 1 OR b == 2 AND NOT c == 3': 'OR(a == 1, AND(b == 2, NOT(c == 3)))',
            'NOT a == 1 AND b == 2': 'AND(NOT(a == 1), b == 2)',
            'a == 1 AND b == 2 OR c == 3 AND d == 4': 'OR(AND(a == 1, b == 2), AND(c == 3, d == 4))',
            'NOT a == 1 OR b == 2': 'OR(NOT(a == 1), b == 2)',
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(condicion(entrada), esperado)

    def test_parentesis_modifican_la_agrupacion(self):
        casos = {
            '(a == 1 OR b == 2) AND c == 3': 'AND(OR(a == 1, b == 2), c == 3)',
            'NOT (a == 1 AND b == 2)': 'NOT(AND(a == 1, b == 2))',
            'a == 1 AND (b == 2 OR c == 3)': 'AND(a == 1, OR(b == 2, c == 3))',
            '((a == 1))': 'a == 1',
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(condicion(entrada), esperado)

    def test_conectores_repetidos_asocian_a_la_izquierda(self):
        self.assertEqual(condicion('a == 1 OR b == 2 OR c == 3'), 'OR(OR(a == 1, b == 2), c == 3)')
        self.assertEqual(condicion('a == 1 AND b == 2 AND c == 3'), 'AND(AND(a == 1, b == 2), c == 3)')
        self.assertEqual(condicion('NOT NOT a == 1'), 'NOT(NOT(a == 1))')

    def test_ejemplo_principal(self):
        programa = ast_de(EJEMPLO_PRINCIPAL)
        regla = programa.reglas[0]
        self.assertEqual(formula(regla.condicion), 'AND(humedad < 30, NOT(OR(lluvia == TRUE, viento > 40)))')
        self.assertEqual(regla.acciones, [Accion('regar', 'sector_norte', 15), Accion('activar', 'alarma', None)])
        self.assertEqual(regla.linea, 1)

    def test_extension_DURING(self):
        acciones = ast_de('WHEN h < 1 THEN a b DURING 0 AND c d AND e f DURING 120;').reglas[0].acciones
        self.assertEqual([a.duracion for a in acciones], [0, None, 120])
        self.assertIn('DURING: 120 min', texto_ast(ast_de('WHEN h < 1 THEN e f DURING 120;')))

    def test_varias_reglas_y_acciones(self):
        programa = ast_de('WHEN h < 1 THEN a b;\nWHEN h > 9 THEN c d AND e f AND g h;')
        self.assertEqual([r.linea for r in programa.reglas], [1, 2])
        self.assertEqual([len(r.acciones) for r in programa.reglas], [1, 3])
        self.assertEqual([a.verbo for a in programa.reglas[1].acciones], ['c', 'e', 'g'])

    def test_valores_y_lexemas(self):
        regla = ast_de('when Lluvia == true then cerrar Valvula during 2;').reglas[0]
        self.assertEqual(regla.condicion, Comparacion('Lluvia', '==', True))
        self.assertEqual(regla.acciones[0], Accion('cerrar', 'Valvula', 2))
        self.assertEqual(ast_de('WHEN h != FALSE THEN a b;').reglas[0].condicion.valor, False)
        self.assertEqual(ast_de('WHEN h >= 007 THEN a b;').reglas[0].condicion.valor, 7)

    def test_entradas_grandes_sin_recursion(self):
        for caso in CASOS:
            if caso.id in ('L10', 'L11', 'L12', 'L13'):
                with self.subTest(caso=caso.id):
                    programa = ast_de(caso.entrada)
                    self.assertTrue(texto_ast(programa))
                    self.assertTrue(formula(programa.reglas[0].condicion))
        self.assertEqual(len(ast_de(next(c for c in CASOS if c.id == 'L13').entrada).reglas), 1000)

    @unittest.skipUnless(shutil.which('dot'), 'Graphviz no instalado (opcional)')
    def test_graphviz_dibuja_el_ast(self):
        resultado = subprocess.run(['dot', '-Tsvg'], input=dot_ast(ast_de(EJEMPLO_PRINCIPAL)),
                                   capture_output=True, text=True, check=True)
        self.assertIn('<svg', resultado.stdout)


if __name__ == '__main__':
    unittest.main()
