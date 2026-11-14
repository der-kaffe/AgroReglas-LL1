"""AgroReglas: reconocimiento sintáctico de reglas de riego agrícola (INFO1148).

Uso como biblioteca:
    from agroreglas import analizar, construir_ast, texto_ast
    arbol = analizar('WHEN humedad < 30 THEN regar sector_norte DURING 15;')
    print(arbol.texto())                     # árbol concreto (derivación)
    print(texto_ast(construir_ast(arbol)))   # AST

El paquete solo reconoce la sintaxis y construye árboles: no ejecuta reglas,
no valida semántica y no controla equipos reales.
"""
from .abstracto import construir_ast, formula, texto_ast
from .errores import ErrorAgro, ErrorLexico, ErrorSintactico
from .gramatica import GRAMATICA
from .ll1 import ANALISIS
from .lexico import Token, analizador_lexico, tokenizar
from .parser import analizar, analizar_tokens, derivacion_izquierda

