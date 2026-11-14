"""Analizador léxico: compatibilidad con el notebook docente, posiciones y errores."""
import hashlib
import json
import random
import re
import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

from agroreglas import ErrorLexico, analizador_lexico, tokenizar
from casos import CASOS

RAIZ = Path(__file__).resolve().parents[1]
NOTEBOOK_DOCENTE = RAIZ / 'documentacion' / 'anlizador_lexico1.ipynb'
MD5_NOTEBOOK_DOCENTE = 'fc3e227269108415964d70f13c9df58b'   # archivo entregado por el docente


def cargar_lexer_docente():
    """Ejecuta la primera celda del notebook original y devuelve su función."""
    datos = json.loads(NOTEBOOK_DOCENTE.read_text(encoding='utf-8'))
    espacio = {}
    exec(''.join(datos['cells'][0]['source']), espacio)
    return espacio['analizador_lexico'], datos


def en_subconjunto_compartido(texto):
    """Entradas donde ambos lexers deben coincidir: ASCII, sin \\r y sin la palabra DURING."""
    return (texto.isascii() and '\r' not in texto
            and not re.search(r'(?<![A-Za-z0-9_])during(?![A-Za-z0-9_])', texto, re.IGNORECASE))


N_CADENAS_ALEATORIAS = 3000
PIEZAS = ['WHEN', 'then', 'And', 'or', 'NOT', 'TRUE', 'false', 'humedad', 'x1', '_s', 'durin',
          '30', '007', '<', '<=', '>', '>=', '==', '!=', '=', '!', ';', '(', ')', ' ', '\t', '\n',
          '@', '.', '-', ',', 'a', '9']


def cadenas_aleatorias(cantidad=N_CADENAS_ALEATORIAS, semilla=1148):
    """Cadenas aleatorias del subconjunto compartido (deterministas por la semilla)."""
    rng = random.Random(semilla)
    cadenas = (''.join(rng.choice(PIEZAS) for _ in range(rng.randint(0, 12))) for _ in range(cantidad))
    return [c for c in cadenas if en_subconjunto_compartido(c)]


def comparar(docente, texto):
    """(salida_docente, salida_nuestra) o ('ValueError', 'ValueError')."""
    try:
        esperado = docente(texto)
    except ValueError:
        esperado = 'ValueError'
    try:
        obtenido = analizador_lexico(texto)
    except ValueError:
        obtenido = 'ValueError'
    return esperado, obtenido


class CompatibilidadNotebook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docente, cls.datos = cargar_lexer_docente()
        cls.docente = staticmethod(docente)

    def test_notebook_docente_preservado(self):
        self.assertEqual(hashlib.md5(NOTEBOOK_DOCENTE.read_bytes()).hexdigest(), MD5_NOTEBOOK_DOCENTE)

    def test_salida_registrada_en_el_notebook(self):
        """La salida guardada por el docente (celda 2) coincide con la nuestra."""
        celda = self.datos['cells'][1]
        entrada = re.search(r'entrada = "(.*)"', ''.join(celda['source'])).group(1)
        salida_docente = ''.join(celda['outputs'][0]['text']).splitlines()
        self.assertEqual([str(t) for t in analizador_lexico(entrada)], salida_docente)

    def test_casos_documentados_del_subconjunto(self):
        comparados = 0
        for caso in CASOS:
            if en_subconjunto_compartido(caso.entrada):
                with self.subTest(caso=caso.id):
                    esperado, obtenido = comparar(self.docente, caso.entrada)
                    self.assertEqual(esperado, obtenido)
                    comparados += 1
        self.assertEqual(comparados, 42)   # 59 casos − 13 con DURING − 2 con \r − 2 no ASCII

    def test_cadenas_aleatorias_del_subconjunto(self):
        cadenas = cadenas_aleatorias()
        for texto in cadenas:
            esperado, obtenido = comparar(self.docente, texto)
            self.assertEqual(esperado, obtenido, repr(texto))
        self.assertGreater(len(cadenas), 2900)

    def test_diferencias_documentadas(self):
        # M1: DURING es reservada (en el notebook era un identificador).
        self.assertEqual(self.docente('DURING'), [('ID', 'DURING')])
        self.assertEqual(analizador_lexico('DURING'), [('DURING', 'DURING')])
        # M4: \r es un blanco (el notebook lo rechaza).
        with self.assertRaises(ValueError):
            self.docente('WHEN\r\n')
        self.assertEqual(analizador_lexico('WHEN\r\n'), [('WHEN', 'WHEN')])
        # M5: solo dígitos ASCII (el notebook acepta dígitos Unicode con \d).
        self.assertEqual(self.docente('٣'), [('NUM', '٣')])
        with self.assertRaises(ErrorLexico):
            analizador_lexico('٣')


class Tokens(unittest.TestCase):
    def test_posiciones_y_eof(self):
        tokens = tokenizar('WHEN h < 1\n  THEN a b;')
        self.assertEqual([(t.tipo, t.linea, t.columna, t.posicion) for t in tokens], [
            ('WHEN', 1, 1, 0), ('ID', 1, 6, 5), ('OP_REL', 1, 8, 7), ('NUM', 1, 10, 9),
            ('THEN', 2, 3, 13), ('ID', 2, 8, 18), ('ID', 2, 10, 20), ('PUNTO_COMA', 2, 11, 21),
            ('EOF', 2, 12, 22)])

    def test_crlf_cuenta_una_linea(self):
        tokens = tokenizar('WHEN\r\nTHEN')
        self.assertEqual([(t.tipo, t.linea, t.columna) for t in tokens],
                         [('WHEN', 1, 1), ('THEN', 2, 1), ('EOF', 2, 5)])

    def test_reservadas_sin_distinguir_mayusculas(self):
        tokens = tokenizar('when When wHeN during Humedad humedad')
        self.assertEqual([t.tipo for t in tokens[:-1]], ['WHEN', 'WHEN', 'WHEN', 'DURING', 'ID', 'ID'])
        self.assertEqual([t.lexema for t in tokens[:-1]], ['when', 'When', 'wHeN', 'during', 'Humedad', 'humedad'])

    def test_coincidencia_mas_larga_de_operadores(self):
        self.assertEqual(analizador_lexico('>= <= == != > <'),
                         [('OP_REL', x) for x in ['>=', '<=', '==', '!=', '>', '<']])
        self.assertEqual(analizador_lexico('>=<'), [('OP_REL', '>='), ('OP_REL', '<')])
        with self.assertRaises(ErrorLexico):
            analizador_lexico('>==')  # '>=' seguido de un '=' aislado

    def test_numero_pegado_a_letras(self):
        self.assertEqual(analizador_lexico('30abc'), [('NUM', '30'), ('ID', 'abc')])
        self.assertEqual(analizador_lexico('abc30'), [('ID', 'abc30')])

    def test_errores_lexicos_con_ubicacion_y_sugerencia(self):
        for texto, columna, sugerencia in [('a = 1', 3, "'=='"), ('a ! 1', 3, "'!='"), ('x, y', 2, 'AND'),
                                           ('1.5', 2, 'enteros'), ('-1', 1, 'sin signo'),
                                           ('# nota', 1, 'comentarios'), ('"x"', 1, 'cadenas'),
                                           ('riego_año', 8, 'ASCII')]:
            with self.subTest(texto=texto):
                with self.assertRaises(ErrorLexico) as contexto:
                    tokenizar(texto)
                self.assertEqual((contexto.exception.linea, contexto.exception.columna), (1, columna))
                self.assertIn(sugerencia, str(contexto.exception))
                self.assertIsInstance(contexto.exception, ValueError)

    def test_error_lexico_en_segunda_linea(self):
        with self.assertRaises(ErrorLexico) as contexto:
            tokenizar('WHEN\n  @')
        self.assertEqual((contexto.exception.linea, contexto.exception.columna, contexto.exception.posicion),
                         (2, 3, 7))


if __name__ == '__main__':
    unittest.main()
