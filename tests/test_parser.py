"""Parser LL(1): casos documentados, consumo completo y pruebas diferenciales."""
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]

from agroreglas import ErrorAgro, ErrorLexico, ErrorSintactico, analizar, analizar_tokens, tokenizar
from agroreglas.gramatica import G0, G1, GRAMATICA
from casos import CASOS, ejecutar
from oraculos import a_texto, generar, mutar, nuevo_rng, reconoce_earley
from test_lexico import cargar_lexer_docente, en_subconjunto_compartido


N_ORACIONES_G0 = 300
N_MUTACIONES_INMEDIATA = 600
N_DIFERENCIALES = 1200


def muestras_diferenciales(cantidad=N_DIFERENCIALES, semilla=1148):
    """Secuencias de tipos: una de cada cuatro es una oración de G0; las demás, mutaciones."""
    rng = nuevo_rng(semilla)
    muestras = []
    for k in range(cantidad):
        base = generar(G0, rng)
        muestras.append(base if k % 4 == 0 else mutar(base, GRAMATICA.terminales, rng))
    return muestras, rng


def veredicto(funcion, *args, **kwargs):
    """(True, None) si acepta; (False, (tipo, línea, columna)) si rechaza."""
    try:
        funcion(*args, **kwargs)
        return True, None
    except ErrorAgro as error:
        return False, (type(error).__name__, error.linea, error.columna)


class CasosDocumentados(unittest.TestCase):
    def test_cantidad_minima_por_categoria(self):
        cantidad = Counter(c.categoria for c in CASOS)
        self.assertGreaterEqual(cantidad['válida'], 10)
        self.assertGreaterEqual(cantidad['inválida'], 10)
        self.assertGreaterEqual(cantidad['límite'], 5)
        self.assertEqual(len({c.id for c in CASOS}), len(CASOS))

    def test_cada_caso_con_su_oraculo(self):
        for caso in CASOS:
            with self.subTest(caso=caso.id):
                fila = ejecutar(caso)
                self.assertEqual(fila['obtenido'], caso.esperado, fila['mensaje'])
                if caso.esperado == 'RECHAZA':
                    self.assertEqual(fila['error_obtenido'], caso.error)
                    self.assertEqual(fila['ubicacion_obtenida'], f'{caso.linea}:{caso.columna}')
                    self.assertIn(caso.fragmento, fila['mensaje'])
                self.assertTrue(fila['coincide'])


class ConsumoCompleto(unittest.TestCase):
    REGLA = 'WHEN humedad < 30 THEN regar sector_sur;'

    def test_rechaza_cualquier_sobrante(self):
        for sobrante in ['basura', ';', ')', '30', 'TRUE', 'AND', 'THEN', 'DURING 5']:
            with self.subTest(sobrante=sobrante):
                with self.assertRaises(ErrorSintactico) as contexto:
                    analizar(f'{self.REGLA} {sobrante}')
                self.assertEqual(contexto.exception.columna, len(self.REGLA) + 2)
                self.assertIn('contenido sobrante', str(contexto.exception))

    def test_segunda_regla_truncada(self):
        for resto, columna in [('WHEN', 46), ('WHEN lluvia', 53), ('WHEN lluvia ==', 56),
                               ('WHEN lluvia == TRUE THEN', 66), ('WHEN lluvia == TRUE THEN cerrar v', 75)]:
            with self.subTest(resto=resto):
                with self.assertRaises(ErrorSintactico) as contexto:
                    analizar(f'{self.REGLA} {resto}')
                self.assertEqual(contexto.exception.columna, columna)
                self.assertEqual(contexto.exception.encontrado, '')       # fin de la entrada

    def test_toda_entrada_aceptada_consume_todos_los_tokens(self):
        for caso in CASOS:
            if caso.esperado == 'ACEPTA':
                with self.subTest(caso=caso.id):
                    tokens = tokenizar(caso.entrada)
                    self.assertEqual(analizar_tokens(tokens).frontera(), tokens[:-1])


class InterfazDeTokens(unittest.TestCase):
    def test_tokens_del_lexer_docente(self):
        """El parser acepta directamente la salida [(TIPO, lexema)] de la función del notebook."""
        docente, _ = cargar_lexer_docente()
        comparados = 0
        for caso in CASOS:
            if not en_subconjunto_compartido(caso.entrada):
                continue
            try:
                pares = docente(caso.entrada)
            except ValueError:
                continue                                   # error léxico: no llega al parser
            with self.subTest(caso=caso.id):
                aceptado, _ = veredicto(analizar_tokens, pares)
                self.assertEqual(aceptado, caso.esperado == 'ACEPTA')
                comparados += 1
        self.assertEqual(comparados, 38)   # 42 del subconjunto − 4 con error léxico

    def test_error_con_tokens_sin_posicion_indica_numero_de_token(self):
        with self.assertRaises(ErrorSintactico) as contexto:
            analizar_tokens([('WHEN', 'WHEN'), ('ID', 'h'), ('OP_REL', '<'), ('THEN', 'THEN')])
        self.assertIn('token n.º 4', str(contexto.exception))

    def test_secuencias_mal_formadas(self):
        with self.assertRaises(ValueError):
            analizar_tokens([('DESCONOCIDO', 'x')])
        with self.assertRaises(ValueError):
            analizar_tokens([('WHEN', 'WHEN'), ('EOF', ''), ('ID', 'h')])


class DeteccionInmediata(unittest.TestCase):
    def test_no_cambia_el_lenguaje_ni_la_posicion_del_error(self):
        rng = nuevo_rng(7)
        entradas = [c.entrada for c in CASOS]
        for _ in range(N_MUTACIONES_INMEDIATA):
            entradas.append(a_texto(mutar(generar(GRAMATICA, rng), GRAMATICA.terminales, rng), rng))
        for texto in entradas:
            with self.subTest(texto=texto[:60]):
                self.assertEqual(veredicto(analizar, texto, deteccion_inmediata=True),
                                 veredicto(analizar, texto, deteccion_inmediata=False))

    def test_esperados_exactos_frente_a_la_fila_de_la_tabla(self):
        texto = 'WHEN humedad < 30 regar sector_sur;'
        with self.assertRaises(ErrorSintactico) as inmediato:
            analizar(texto)
        with self.assertRaises(ErrorSintactico) as fila:
            analizar(texto, deteccion_inmediata=False)
        self.assertEqual(inmediato.exception.esperados, ('THEN', 'AND', 'OR'))
        self.assertEqual(fila.exception.esperados, ('THEN', 'AND', 'OR', 'PARENT_DER'))


class Diferencial(unittest.TestCase):
    """Compara el parser LL(1) (G2) con un reconocedor de Earley sobre G0, G1 y G2."""

    def test_oraciones_aleatorias_de_G0_son_aceptadas(self):
        rng = nuevo_rng(1)
        for _ in range(N_ORACIONES_G0):
            tipos = generar(G0, rng)
            with self.subTest(tipos=' '.join(tipos)[:80]):
                self.assertEqual(veredicto(analizar, a_texto(tipos, rng)), (True, None))

    def test_mutaciones_contra_earley(self):
        muestras, rng = muestras_diferenciales()
        resumen = Counter()
        for tipos in muestras:
            aceptado, _ = veredicto(analizar, a_texto(tipos, rng))
            esperado = reconoce_earley(G0, tipos)
            self.assertEqual(aceptado, esperado, ' '.join(tipos))
            self.assertEqual(reconoce_earley(G1, tipos), esperado)
            self.assertEqual(reconoce_earley(GRAMATICA, tipos), esperado)
            resumen[aceptado] += 1
        self.assertGreater(resumen[True], 200)
        self.assertGreater(resumen[False], 200)

    def test_errores_lexicos_no_llegan_al_parser(self):
        self.assertEqual(veredicto(analizar, 'WHEN h = 1 THEN a b;'), (False, ('ErrorLexico', 1, 8)))
        self.assertTrue(issubclass(ErrorLexico, ValueError))


if __name__ == '__main__':
    unittest.main()
