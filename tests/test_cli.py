"""Interfaz de consola: salidas y códigos de salida (0 válida, 1 rechazada, 2 uso/lectura)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def cli(*argumentos, entrada=None):
    return subprocess.run([sys.executable, '-m', 'agroreglas', *argumentos], cwd=RAIZ, input=entrada,
                          capture_output=True, text=True, encoding='utf-8')


class CodigosDeSalida(unittest.TestCase):
    def test_ejemplos_validos_retornan_0(self):
        archivos = sorted((RAIZ / 'ejemplos' / 'validos').glob('*.agro')) + [RAIZ / 'ejemplos' / 'riego.agro']
        self.assertGreaterEqual(len(archivos), 5)
        for archivo in archivos:
            with self.subTest(archivo=archivo.name):
                resultado = cli(str(archivo))
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertIn('ACEPTADA', resultado.stdout)
                self.assertEqual(resultado.stderr, '')

    def test_ejemplos_invalidos_retornan_1(self):
        archivos = sorted((RAIZ / 'ejemplos' / 'invalidos').glob('*.agro')) + [RAIZ / 'ejemplos' / 'error.agro']
        self.assertGreaterEqual(len(archivos), 5)
        for archivo in archivos:
            with self.subTest(archivo=archivo.name):
                resultado = cli(str(archivo))
                self.assertEqual(resultado.returncode, 1)
                self.assertIn('RECHAZADA', resultado.stderr)
                self.assertRegex(resultado.stderr, r'Error (léxico|sintáctico) en línea \d+, columna \d+')
                self.assertIn('^', resultado.stderr)
                self.assertEqual(resultado.stdout, '')

    def test_errores_de_uso_y_lectura_retornan_2(self):
        self.assertEqual(cli('no_existe.agro').returncode, 2)
        self.assertEqual(cli().returncode, 2)
        self.assertEqual(cli('--opcion-inexistente', 'x').returncode, 2)
        with tempfile.TemporaryDirectory() as carpeta:
            binario = Path(carpeta) / 'latin1.agro'
            binario.write_bytes('WHEN año'.encode('latin-1'))
            resultado = cli(str(binario))
            self.assertEqual(resultado.returncode, 2)
            self.assertIn('Error de lectura', resultado.stderr)

    def test_texto_directo_y_entrada_estandar(self):
        self.assertEqual(cli('-e', 'WHEN h < 1 THEN a b;').returncode, 0)
        self.assertEqual(cli('-e', 'WHEN h < THEN a b;').returncode, 1)
        self.assertEqual(cli('-', entrada='WHEN h < 1 THEN a b DURING 3;\n').returncode, 0)

    def test_archivo_con_bom_utf8(self):
        with tempfile.TemporaryDirectory() as carpeta:
            archivo = Path(carpeta) / 'bom.agro'
            archivo.write_bytes(b'\xef\xbb\xbfWHEN h < 1 THEN a b;\r\n')
            self.assertEqual(cli(str(archivo)).returncode, 0)


class Opciones(unittest.TestCase):
    def test_salidas_detalladas(self):
        resultado = cli('ejemplos/riego.agro', '--tokens', '--arbol', '--ast', '--derivacion', '--traza')
        self.assertEqual(resultado.returncode, 0)
        for seccion in ['Tokens (línea:columna', 'Árbol sintáctico concreto:', 'Árbol de sintaxis abstracta',
                        'Derivación por la izquierda', 'Traza del parser LL(1)', 'M[Duracion, DURING] = (22)',
                        'DURING: 15 min', 'aceptar']:
            self.assertIn(seccion, resultado.stdout)

    def test_analisis_de_la_gramatica(self):
        resultado = cli('--analisis')
        self.assertEqual(resultado.returncode, 0)
        self.assertIn('|P| = 23', resultado.stdout)
        self.assertIn('Conflictos: 0 -> la gramática es LL(1)', resultado.stdout)
        self.assertIn('Duracion      FIRST = {DURING, ε}  FOLLOW = {AND, PUNTO_COMA}', resultado.stdout)

    def test_exportacion_graphviz(self):
        with tempfile.TemporaryDirectory() as carpeta:
            arbol, ast = Path(carpeta) / 'arbol.dot', Path(carpeta) / 'ast.dot'
            resultado = cli('ejemplos/riego.agro', '--dot-arbol', str(arbol), '--dot-ast', str(ast))
            self.assertEqual(resultado.returncode, 0)
            self.assertTrue(arbol.read_text(encoding='utf-8').startswith('digraph'))
            self.assertIn('DURING: 15 min', ast.read_text(encoding='utf-8'))

    def test_modo_ascii(self):
        resultado = cli('-e', 'WHEN h < 1 THEN a b;', '--arbol', '--ascii')
        self.assertIn('`-- Resto', resultado.stdout)
        self.assertNotIn('└', resultado.stdout)


if __name__ == '__main__':
    unittest.main()
