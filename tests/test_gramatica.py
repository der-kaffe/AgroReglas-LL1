"""Análisis formal: componentes de G, FIRST, FOLLOW, SELECT, tabla LL(1) y transformaciones.

Los oráculos de este archivo se escribieron a mano (cálculo del informe) y se
contrastan con los algoritmos de agroreglas/ll1.py.
"""
import sys
import unittest
from itertools import combinations
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

from agroreglas.gramatica import EOF, EPS, G0, G1, GRAMATICA, Gramatica
from agroreglas.ll1 import ANALISIS, analizar_gramatica

N_ESPERADO = ['Programa', 'Resto', 'Regla', 'Condicion', 'ColaOr', 'Conjuncion', 'ColaAnd', 'Factor',
              'Comparacion', 'Valor', 'Acciones', 'ColaAcciones', 'Accion', 'Duracion']
T_ESPERADO = ['WHEN', 'THEN', 'ID', 'OP_REL', 'NUM', 'TRUE', 'FALSE', 'NOT', 'AND', 'OR',
              'PARENT_IZQ', 'PARENT_DER', 'DURING', 'PUNTO_COMA']
CONDICION = {'ID', 'NOT', 'PARENT_IZQ'}

FIRST_ESPERADO = {
    'Programa': {'WHEN'}, 'Resto': {'WHEN', EPS}, 'Regla': {'WHEN'},
    'Condicion': CONDICION, 'ColaOr': {'OR', EPS}, 'Conjuncion': CONDICION, 'ColaAnd': {'AND', EPS},
    'Factor': CONDICION, 'Comparacion': {'ID'}, 'Valor': {'NUM', 'TRUE', 'FALSE'},
    'Acciones': {'ID'}, 'ColaAcciones': {'AND', EPS}, 'Accion': {'ID'}, 'Duracion': {'DURING', EPS},
}
FIN_CONDICION = {'THEN', 'PARENT_DER'}
FOLLOW_ESPERADO = {
    'Programa': {EOF}, 'Resto': {EOF}, 'Regla': {'WHEN', EOF},
    'Condicion': FIN_CONDICION, 'ColaOr': FIN_CONDICION,
    'Conjuncion': FIN_CONDICION | {'OR'}, 'ColaAnd': FIN_CONDICION | {'OR'},
    'Factor': FIN_CONDICION | {'OR', 'AND'}, 'Comparacion': FIN_CONDICION | {'OR', 'AND'},
    'Valor': FIN_CONDICION | {'OR', 'AND'},
    'Acciones': {'PUNTO_COMA'}, 'ColaAcciones': {'PUNTO_COMA'},
    'Accion': {'AND', 'PUNTO_COMA'}, 'Duracion': {'AND', 'PUNTO_COMA'},
}
SELECT_ESPERADO = {
    1: {'WHEN'}, 2: {'WHEN'}, 3: {EOF}, 4: {'WHEN'}, 5: CONDICION, 6: {'OR'}, 7: FIN_CONDICION,
    8: CONDICION, 9: {'AND'}, 10: FIN_CONDICION | {'OR'}, 11: {'NOT'}, 12: {'PARENT_IZQ'}, 13: {'ID'},
    14: {'ID'}, 15: {'NUM'}, 16: {'TRUE'}, 17: {'FALSE'}, 18: {'ID'}, 19: {'AND'}, 20: {'PUNTO_COMA'},
    21: {'ID'}, 22: {'DURING'}, 23: {'AND', 'PUNTO_COMA'},
}
TABLA_ESPERADA = {(GRAMATICA.produccion(n).izquierda, t): n
                  for n, terminales in SELECT_ESPERADO.items() for t in terminales}


class ComponentesDeG(unittest.TestCase):
    def test_N_T_S_y_P(self):
        self.assertEqual(GRAMATICA.no_terminales, N_ESPERADO)
        self.assertEqual(GRAMATICA.terminales, T_ESPERADO)
        self.assertEqual(GRAMATICA.inicial, 'Programa')
        self.assertEqual(len(GRAMATICA.producciones), 23)
        self.assertNotIn(EOF, GRAMATICA.terminales)
        self.assertNotIn(EPS, GRAMATICA.terminales)

    def test_producciones_numeradas(self):
        self.assertEqual(str(GRAMATICA.produccion(4)), 'Regla → WHEN Condicion THEN Acciones PUNTO_COMA')
        self.assertEqual(str(GRAMATICA.produccion(21)), 'Accion → ID ID Duracion')
        self.assertEqual(str(GRAMATICA.produccion(22)), 'Duracion → DURING NUM')
        self.assertEqual(str(GRAMATICA.produccion(23)), 'Duracion → ε')


class FirstFollow(unittest.TestCase):
    def test_anulables(self):
        self.assertEqual(ANALISIS.anulables, {'Resto', 'ColaOr', 'ColaAnd', 'ColaAcciones', 'Duracion'})

    def test_first_de_todos_los_no_terminales(self):
        self.assertEqual(ANALISIS.first, FIRST_ESPERADO)

    def test_follow_de_todos_los_no_terminales(self):
        self.assertEqual(ANALISIS.follow, FOLLOW_ESPERADO)

    def test_conjuntos_de_seleccion(self):
        self.assertEqual(ANALISIS.seleccion, SELECT_ESPERADO)


class TablaLL1(unittest.TestCase):
    def test_tabla_completa(self):
        self.assertEqual({k: p.numero for k, p in ANALISIS.tabla.items()}, TABLA_ESPERADA)
        self.assertEqual(len(ANALISIS.tabla), 31)
        celdas = len(GRAMATICA.no_terminales) * len(ANALISIS.columnas)
        self.assertEqual(celdas - len(ANALISIS.tabla), 179)   # celdas de error

    def test_sin_conflictos_y_seleccion_disjunta(self):
        self.assertTrue(ANALISIS.es_ll1)
        for a in GRAMATICA.no_terminales:
            for p, q in combinations(GRAMATICA.alternativas(a), 2):
                with self.subTest(p=p.numero, q=q.numero):
                    self.assertFalse(ANALISIS.seleccion[p.numero] & ANALISIS.seleccion[q.numero])

    def test_decisiones_de_la_extension_DURING(self):
        tabla = ANALISIS.tabla
        self.assertEqual(tabla['Duracion', 'DURING'].numero, 22)
        self.assertEqual(tabla['Duracion', 'AND'].numero, 23)
        self.assertEqual(tabla['Duracion', 'PUNTO_COMA'].numero, 23)
        self.assertNotIn(('Duracion', EOF), tabla)
        self.assertNotIn(('Duracion', 'NUM'), tabla)

    def test_AND_sobrecargado_sin_conflicto(self):
        """AND aparece en tres filas distintas, cada una con una sola producción."""
        filas = {a: tabla.numero for (a, t), tabla in ANALISIS.tabla.items() if t == 'AND'}
        self.assertEqual(filas, {'ColaAnd': 9, 'ColaAcciones': 19, 'Duracion': 23})
        self.assertNotIn('AND', FOLLOW_ESPERADO['Condicion'])   # la condición termina antes de THEN

    def test_decisiones_de_precedencia(self):
        tabla = ANALISIS.tabla
        self.assertEqual(tabla['ColaAnd', 'OR'].numero, 10)    # ante OR, ColaAnd cierra el nivel AND
        self.assertEqual(tabla['ColaAnd', 'AND'].numero, 9)
        self.assertEqual(tabla['Factor', 'NOT'].numero, 11)
        self.assertEqual(tabla['Factor', 'PARENT_IZQ'].numero, 12)
        self.assertNotIn(('Programa', EOF), tabla)              # el programa vacío no es válido


class Transformaciones(unittest.TestCase):
    def test_gramatica_final_sin_recursion_ni_prefijos(self):
        self.assertEqual(ANALISIS.recursion_directa, [])
        self.assertEqual(ANALISIS.recursion_indirecta, {})
        self.assertEqual(ANALISIS.prefijos, [])
        self.assertEqual(ANALISIS.grafo_izquierdo, {
            'Programa': ['Regla'], 'Resto': ['Regla'], 'Regla': [], 'Condicion': ['Conjuncion'],
            'ColaOr': [], 'Conjuncion': ['Factor'], 'ColaAnd': [], 'Factor': ['Comparacion'],
            'Comparacion': [], 'Valor': [], 'Acciones': ['Accion'], 'ColaAcciones': [], 'Accion': [],
            'Duracion': []})

    def test_G0_ambigua_recursiva_y_sin_factorizar(self):
        a = analizar_gramatica(G0)
        self.assertEqual(a.recursion_directa, ['Condicion', 'Acciones'])
        self.assertEqual([(x[0], x[3]) for x in a.prefijos],
                         [('Programa', ('Regla',)), ('Condicion', ('Condicion',)), ('Accion', ('ID', 'ID'))])
        self.assertEqual(len(a.conflictos), 6)
        self.assertIn(('Condicion', 'ID'), [(c.no_terminal, c.terminal) for c in a.conflictos])

    def test_G1_con_precedencia_aun_no_es_LL1(self):
        a = analizar_gramatica(G1)
        self.assertEqual(a.recursion_directa, ['Condicion', 'Conjuncion', 'Acciones'])
        self.assertEqual([(x[0], x[3]) for x in a.prefijos], [('Programa', ('Regla',)), ('Accion', ('ID', 'ID'))])
        self.assertEqual(len(a.conflictos), 9)

    def test_detecta_recursion_izquierda_indirecta(self):
        """Gramática de libro: S → A a | b ; A → A c | S d | ε (Aho et al., eliminación de recursión izquierda)."""
        g = Gramatica('indirecta', 'S -> A a | b\nA -> A c | S d | ε')
        a = analizar_gramatica(g)
        self.assertEqual(a.recursion_directa, ['A'])
        self.assertEqual(a.recursion_indirecta, {'S': ['S', 'A', 'S'], 'A': ['A', 'S', 'A']})
        self.assertFalse(a.es_ll1)

    def test_detecta_conflicto_en_gramatica_ambigua(self):
        a = analizar_gramatica(Gramatica('ambigua', 'E -> E + E | id'))
        self.assertEqual([(c.no_terminal, c.terminal, c.producciones) for c in a.conflictos],
                         [('E', 'id', (1, 2))])

    def test_puntos_fijos_terminan(self):
        self.assertLessEqual(ANALISIS.pasadas_first, len(GRAMATICA.no_terminales) + 1)
        self.assertLessEqual(ANALISIS.pasadas_follow, len(GRAMATICA.no_terminales) + 1)


if __name__ == '__main__':
    unittest.main()
