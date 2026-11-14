"""Errores de AgroReglas con ubicación precisa y presentación con puntero.

Convenciones de ubicación (iguales en léxico, parser, CLI, pruebas e informe):
  * línea y columna se cuentan desde 1;
  * posición es el desplazamiento absoluto en el texto, contado desde 0;
  * una tabulación cuenta como una columna.
Si los tokens no provienen de texto (por ejemplo, pares (TIPO, lexema) del
lexer docente), no hay línea/columna y se informa el número de token.
"""


class ErrorAgro(ValueError):
    """Base de los errores de análisis. Hereda de ValueError, como el lexer docente."""

    tipo = 'Error'

    def __init__(self, mensaje, linea=None, columna=None, posicion=None, *,
                 encontrado=None, esperados=(), contexto=None, longitud=1, indice=None):
        self.mensaje = mensaje
        self.linea = linea
        self.columna = columna
        self.posicion = posicion
        self.encontrado = encontrado      # lexema encontrado ('' para fin de entrada)
        self.esperados = tuple(esperados)  # categorías de token aceptables en ese punto
        self.contexto = contexto          # símbolo de la cima de la pila (solo sintácticos)
        self.longitud = max(1, longitud)
        self.indice = indice              # índice del token (desde 0) si no hay posición
        super().__init__(f'{self.tipo} {self.ubicacion()}: {mensaje}')

    def ubicacion(self):
        if self.linea is None:
            if self.indice is None:
                return 'sin ubicación'
            return f'en el token n.º {self.indice + 1}'
        return f'en línea {self.linea}, columna {self.columna} (posición {self.posicion})'

    def mostrar(self, fuente=None):
        """Texto completo: mensaje, esperados, contexto y la línea con un puntero ^."""
        partes = [str(self)]
        if self.esperados:
            partes.append('  Esperados: ' + ', '.join(self.esperados))
        if self.contexto:
            partes.append(f'  Cima de la pila: {self.contexto}')
        if fuente is not None and self.linea is not None:
            lineas = fuente.split('\n')
            texto = lineas[self.linea - 1] if self.linea <= len(lineas) else ''
            texto = texto.rstrip('\r').replace('\t', ' ')
            margen = f'{self.linea:>4} | '
            disponible = max(1, len(texto) - (self.columna - 1))
            puntero = '^' * min(self.longitud, disponible)
            partes.append(margen + texto)
            partes.append(' ' * (len(margen) - 2) + '| ' + ' ' * (self.columna - 1) + puntero)
        return '\n'.join(partes)


class ErrorLexico(ErrorAgro):
    """Carácter que no pertenece a ninguna categoría de token."""

    tipo = 'Error léxico'


class ErrorSintactico(ErrorAgro):
    """Secuencia de tokens que no respeta la gramática."""

    tipo = 'Error sintáctico'

