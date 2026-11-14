"""Analizador léxico de AgroReglas, basado en el notebook docente.

Base: función ``analizador_lexico`` de ``documentacion/anlizador_lexico1.ipynb``
(copia byte a byte del archivo entregado por el docente). Se conservan sus
categorías, el orden de las alternativas, los patrones de OP_REL, PUNTO_COMA,
PARENT_IZQ, PARENT_DER e ID, el descarte de blancos, la conversión de palabras
reservadas con ``upper()`` (sin distinguir mayúsculas) y la preservación del
lexema original.

Modificaciones respecto del notebook (también listadas en el informe):
  M1  DURING se agrega a las palabras reservadas (extensión del dominio).
  M2  Cada token registra línea, columna (desde 1) y posición (desde 0).
  M3  Se agrega al final el token sintético EOF (el marcador $ del análisis LL(1)).
  M4  ESPACIO acepta también el retorno de carro \\r (archivos con fin de línea CRLF).
  M5  NUM se restringe a dígitos ASCII [0-9]; el patrón \\d original acepta además
      dígitos Unicode como '٣'. En entradas ASCII ambos patrones coinciden.
  M6  El error léxico es ErrorLexico (subclase de ValueError, igual que el original)
      con ubicación y una sugerencia cuando el símbolo es un error típico.
  M7  ``analizador_lexico`` mantiene la interfaz original [(TIPO, lexema), ...] sin
      EOF, para comparar directamente con la función del notebook.
"""
import re
from dataclasses import dataclass

from .errores import ErrorLexico

EOF = 'EOF'

PALABRAS_RESERVADAS = frozenset({
    'WHEN', 'THEN', 'AND', 'OR', 'NOT', 'TRUE', 'FALSE',  # originales del notebook
    'DURING',                                             # M1
})

# Mismo orden que el notebook: NUM antes que ID; OP_REL con los operadores
# de dos caracteres antes que los de uno (coincidencia más larga).
ESPECIFICACION_TOKENS = [
    ('NUM',        r'[0-9]+'),                 # M5 (original: \d+)
    ('OP_REL',     r'>=|<=|==|!=|>|<'),
    ('PUNTO_COMA', r';'),
    ('PARENT_IZQ', r'\('),
    ('PARENT_DER', r'\)'),
    ('ID',         r'[A-Za-z_][A-Za-z0-9_]*'),
    ('ESPACIO',    r'[ \t\r\n]+'),            # M4 (original: [ \t\n]+)
    ('ERROR',      r'.'),
]

PATRON = re.compile('|'.join(f'(?P<{nombre}>{expresion})'
                             for nombre, expresion in ESPECIFICACION_TOKENS))


@dataclass(frozen=True, slots=True)
class Token:
    tipo: str      # categoría: WHEN, ID, NUM, OP_REL, ..., EOF
    lexema: str    # texto original ('' para EOF)
    linea: int     # desde 1
    columna: int   # desde 1
    posicion: int  # desde 0


def _mostrar_caracter(caracter):
    if caracter.isprintable() and not caracter.isspace():
        return f"'{caracter}'"
    return f'U+{ord(caracter):04X}'


def _sugerencia(caracter):
    """Pista para errores léxicos frecuentes (M6)."""
    if caracter == '=':
        return " ¿Quiso escribir '=='? El '=' aislado no es un operador de AgroReglas."
    if caracter == '!':
        return " ¿Quiso escribir '!='?"
    if caracter == ',':
        return ' Las acciones se separan con AND, no con comas.'
    if caracter == '.':
        return ' Solo se admiten números enteros (sin punto decimal).'
    if caracter in '+-':
        return ' Los números son enteros sin signo.'
    if caracter in '#/':
        return ' AgroReglas no admite comentarios.'
    if caracter in '"\'':
        return ' AgroReglas no tiene cadenas de texto.'
    if caracter.isdigit():
        return ' Solo se admiten los dígitos ASCII 0-9.'
    if caracter.isalpha():
        return " Los identificadores solo admiten letras ASCII (sin tildes ni ñ), dígitos y '_'."
    return ''


def tokenizar(fuente):
    """Convierte el texto en una lista de Token terminada en un único EOF."""
    tokens = []
    linea, columna = 1, 1
    for coincidencia in PATRON.finditer(fuente):
        tipo, lexema = coincidencia.lastgroup, coincidencia.group()
        if tipo == 'ERROR':
            raise ErrorLexico(
                f'símbolo no reconocido {_mostrar_caracter(lexema)}.{_sugerencia(lexema)}',
                linea, columna, coincidencia.start(), encontrado=lexema)
        if tipo != 'ESPACIO':
            if tipo == 'ID' and lexema.upper() in PALABRAS_RESERVADAS:
                tipo = lexema.upper()
            tokens.append(Token(tipo, lexema, linea, columna, coincidencia.start()))
        saltos = lexema.count('\n')
        if saltos:
            linea += saltos
            columna = len(lexema) - lexema.rfind('\n')
        else:
            columna += len(lexema)
    tokens.append(Token(EOF, '', linea, columna, len(fuente)))
    return tokens


def analizador_lexico(cadena):
    """Interfaz del notebook docente: [(TIPO_TOKEN, lexema), ...] sin EOF (M7)."""
    return [(token.tipo, token.lexema) for token in tokenizar(cadena) if token.tipo != EOF]
