"""Coherencia entre código y resultados entregados (resultados/ debe estar al día)."""
import json
import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

from agroreglas.ll1 import ANALISIS
from casos import CASOS, ejecutar

RESULTADOS = Path(__file__).resolve().parents[1] / 'resultados'


class ResultadosAlDia(unittest.TestCase):
    def test_analisis_json_coincide_con_el_codigo(self):
        datos = json.loads((RESULTADOS / 'analisis.json').read_text(encoding='utf-8'))
        g = ANALISIS.gramatica
        self.assertEqual(datos['no_terminales'], g.no_terminales)
        self.assertEqual(datos['terminales'], g.terminales)
        self.assertEqual(len(datos['producciones']), len(g.producciones))
        for a in g.no_terminales:
            self.assertEqual(datos['FIRST'][a], ANALISIS.ordenar(ANALISIS.first[a]))
            self.assertEqual(datos['FOLLOW'][a], ANALISIS.ordenar(ANALISIS.follow[a]))
            self.assertEqual(datos['tabla'][a], {t: ANALISIS.tabla[a, t].numero for t in ANALISIS.fila(a)})
        self.assertEqual(datos['conflictos'], [])

    def test_pruebas_json_coincide_con_una_nueva_ejecucion(self):
        guardadas = json.loads((RESULTADOS / 'pruebas.json').read_text(encoding='utf-8'))
        self.assertEqual([f['id'] for f in guardadas], [c.id for c in CASOS])
        for guardada, caso in zip(guardadas, CASOS):
            with self.subTest(caso=caso.id):
                actual = ejecutar(caso)
                for campo in ('entrada', 'obtenido', 'ubicacion_obtenida', 'mensaje', 'detalle', 'coincide'):
                    self.assertEqual(guardada[campo], actual[campo], campo)


if __name__ == '__main__':
    unittest.main()
