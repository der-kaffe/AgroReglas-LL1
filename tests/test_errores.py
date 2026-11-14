"""Calidad de los mensajes de error: ubicación, símbolo encontrado, esperados y puntero."""
import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

from agroreglas import ErrorAgro, ErrorSintactico, analizar


def error_de(texto):
    try:
        analizar(texto)
    except ErrorAgro as error:
        return error
    raise AssertionError(f'Se esperaba un error para {texto!r}')


class Mensajes(unittest.TestCase):
    def test_contiene_ubicacion_encontrado_y_esperados(self):
        error = error_de('WHEN humedad < THEN regar sector_norte;')
        texto = str(error)
        for fragmento in ['Error sintáctico', 'línea 1', 'columna 16', 'posición 15',
                          'la palabra reservada THEN', "después del operador '<'"]:
            self.assertIn(fragmento, texto)
        self.assertEqual(error.esperados, ('NUM', 'TRUE', 'FALSE'))
        self.assertEqual(error.encontrado, 'THEN')
        self.assertEqual(error.contexto, 'Valor')

    def test_puntero_bajo_el_simbolo(self):
        fuente = 'WHEN humedad < 30\n  THEN regar;'
        lineas = error_de(fuente).mostrar(fuente).splitlines()
        self.assertEqual(lineas[-2], '   2 |   THEN regar;')
        self.assertEqual(lineas[-1], '     |             ^')

    def test_puntero_con_tabulaciones(self):
        fuente = 'WHEN\thumedad\t<\tTHEN a b;'
        lineas = error_de(fuente).mostrar(fuente).splitlines()
        self.assertEqual(lineas[-1].index('^') - lineas[-2].index('W'), 15)   # columna 16

    def test_esperados_por_punto_de_la_gramatica(self):
        casos = {
            'WHEN': ('ID', 'NOT', 'PARENT_IZQ'),
            'WHEN h': ('OP_REL',),
            'WHEN h <': ('NUM', 'TRUE', 'FALSE'),
            'WHEN h < 1': ('THEN', 'AND', 'OR'),
            'WHEN (h < 1': ('AND', 'OR', 'PARENT_DER'),
            'WHEN h < 1 THEN': ('ID',),
            'WHEN h < 1 THEN a': ('ID',),
            'WHEN h < 1 THEN a b': ('AND', 'DURING', 'PUNTO_COMA'),
            'WHEN h < 1 THEN a b DURING': ('NUM',),
            'WHEN h < 1 THEN a b DURING 5': ('AND', 'PUNTO_COMA'),
            'WHEN h < 1 THEN a b; x': ('WHEN', 'EOF'),
        }
        for entrada, esperados in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(error_de(entrada).esperados, esperados)

    def test_mensajes_contextuales(self):
        casos = {
            '': 'la entrada está vacía',
            'WHEN h < 1 THEN a b; x': 'contenido sobrante',
            'WHEN h < 1) THEN a b;': "sin '(' de apertura",
            'WHEN ((h < 1) THEN a b;': "El '(' abierto en línea 1, columna 6 sigue sin cerrar",
            'WHEN h < 1 THEN a;': "el objetivo de la acción 'a'",
            'WHEN h < 1 THEN a b DURING x;': 'la duración en minutos',
            'WHEN h < 1 THEN a b': 'regla incompleta',
            'WHEN h < 1 THEN a b AND': 'el verbo de una acción',
            'WHEN h < 1 regar x;': 'THEN, AND u OR',
        }
        for entrada, fragmento in casos.items():
            with self.subTest(entrada=entrada):
                self.assertIn(fragmento, str(error_de(entrada)))

    def test_solo_se_informa_el_primer_error_sintactico(self):
        error = error_de('WHEN h < THEN a b;\nWHEN x THEN ;')
        self.assertIsInstance(error, ErrorSintactico)
        self.assertEqual((error.linea, error.columna), (1, 10))

    def test_el_lexico_completo_precede_al_parser(self):
        """Como en el notebook, se tokeniza toda la entrada antes de analizarla: un error
        léxico de la línea 2 se informa aunque la línea 1 tenga un error sintáctico."""
        error = error_de('WHEN h < THEN a b;\nWHEN x = 1 THEN a b;')
        self.assertEqual((type(error).__name__, error.linea, error.columna), ('ErrorLexico', 2, 8))


if __name__ == '__main__':
    unittest.main()
