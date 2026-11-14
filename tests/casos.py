"""Batería documentada de entradas con oráculos explícitos.

Cada caso fija, antes de ejecutar el parser:
  * el veredicto esperado (ACEPTA / RECHAZA);
  * para los rechazos, el tipo de error (léxico / sintáctico), la línea y la
    columna del símbolo culpable (calculadas a mano) y un fragmento que el
    mensaje debe contener.
Los mismos casos alimentan las pruebas automáticas, resultados/pruebas.csv,
resultados/pruebas.json y las tablas del informe.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Caso:
    id: str
    categoria: str               # 'válida', 'inválida' o 'límite'
    entrada: str
    esperado: str                # 'ACEPTA' o 'RECHAZA'
    observacion: str
    error: str | None = None     # 'léxico' o 'sintáctico'
    linea: int | None = None
    columna: int | None = None
    fragmento: str | None = None
    resumen: str | None = None   # descripción para entradas demasiado largas


def V(id, entrada, obs, resumen=None):
    return Caso(id, 'válida', entrada, 'ACEPTA', obs, resumen=resumen)


def I(id, entrada, obs, error, linea, columna, fragmento, categoria='inválida', resumen=None):
    return Caso(id, categoria, entrada, 'RECHAZA', obs, error, linea, columna, fragmento, resumen)


def L_ok(id, entrada, obs, resumen=None):
    return Caso(id, 'límite', entrada, 'ACEPTA', obs, resumen=resumen)


def L_err(id, entrada, obs, error, linea, columna, fragmento, resumen=None):
    return I(id, entrada, obs, error, linea, columna, fragmento, 'límite', resumen)


EJEMPLO_PRINCIPAL = ('WHEN humedad < 30 AND NOT (lluvia == TRUE OR viento > 40)\n'
                     'THEN regar sector_norte DURING 15 AND activar alarma;')

CASOS = [
    # ------------------------------------------------------------------ válidas
    V('V01', 'WHEN humedad < 30 THEN regar sector_norte;', 'Regla mínima: una comparación y una acción'),
    V('V02', 'WHEN temperatura >= 35 THEN abrir valvula_1;', 'Operador >= de dos caracteres'),
    V('V03', 'WHEN lluvia == TRUE THEN cerrar valvula_1;', 'Valor booleano TRUE'),
    V('V04', 'WHEN lluvia != FALSE THEN activar alarma;', 'Operador != y valor FALSE'),
    V('V05', 'WHEN humedad <= 20 AND temperatura > 25 THEN regar sector_sur;', 'Conjunción AND'),
    V('V06', 'WHEN humedad < 20 OR temperatura > 35 THEN regar sector_sur;', 'Disyunción OR'),
    V('V07', 'WHEN NOT lluvia == TRUE THEN regar sector_sur;', 'Negación de una comparación'),
    V('V08', 'WHEN (humedad < 20 OR temperatura > 35) AND lluvia == FALSE THEN regar sector_sur;',
      'Paréntesis: el OR se agrupa antes que el AND'),
    V('V09', 'WHEN humedad < 30 THEN regar sector_sur DURING 10;', 'Extensión DURING'),
    V('V10', 'WHEN humedad < 30 THEN regar sector_sur DURING 10 AND activar bomba;',
      'Dos acciones; DURING solo en la primera'),
    V('V11', 'WHEN humedad < 25 THEN regar invernadero DURING 20;\nWHEN viento > 60 THEN cerrar compuertas;',
      'Dos reglas en líneas distintas'),
    V('V12', EJEMPLO_PRINCIPAL, 'Ejemplo del enunciado: NOT, paréntesis, OR, AND, DURING y dos acciones'),
    V('V13', 'when Lluvia == true then cerrar Valvula during 2;',
      'Reservadas en minúsculas; los identificadores conservan su escritura'),
    V('V14', 'WHEN radiacion > 800 AND humedad < 40 THEN abrir valvula_1 DURING 5 '
             'AND abrir valvula_2 DURING 5 AND registrar evento;', 'Tres acciones, dos con duración'),
    V('V15', 'WHEN NOT (humedad < 30 AND NOT lluvia == TRUE) OR nivel_tanque <= 10 '
             'THEN activar bomba_pozo DURING 30;', 'NOT sobre un grupo, NOT anidado y OR posterior'),
    V('V16', 'WHEN viento > 50 OR granizo == TRUE OR helada == TRUE THEN cerrar invernadero;',
      'OR repetido (asociatividad izquierda en el AST)'),
    # ---------------------------------------------------------------- inválidas
    I('I01', 'WHEN humedad < 30 regar sector_sur;', 'Falta THEN', 'sintáctico', 1, 19, 'THEN'),
    I('I02', 'WHEN humedad < THEN regar sector_sur;', 'Falta el valor después del operador',
      'sintáctico', 1, 16, "un valor (número entero, TRUE o FALSE) después del operador '<'"),
    I('I03', 'WHEN humedad 30 THEN regar sector_sur;', 'Falta el operador relacional',
      'sintáctico', 1, 14, 'operador relacional'),
    I('I04', 'WHEN humedad < 30 THEN regar sector_sur', "Falta ';' final",
      'sintáctico', 1, 40, 'fin de la entrada'),
    I('I05', 'WHEN humedad < 30 THEN regar;', 'Acción sin objetivo',
      'sintáctico', 1, 29, "objetivo de la acción 'regar'"),
    I('I06', 'WHEN (humedad < 30 THEN regar sector_sur;', 'Paréntesis sin cerrar',
      'sintáctico', 1, 20, "El '(' abierto en línea 1, columna 6 sigue sin cerrar"),
    I('I07', 'WHEN humedad < 30) THEN regar sector_sur;', 'Paréntesis de cierre sin apertura',
      'sintáctico', 1, 18, "sin '(' de apertura"),
    I('I08', 'WHEN humedad < 30 OR THEN regar sector_sur;', 'OR sin operando derecho',
      'sintáctico', 1, 22, 'después de OR'),
    I('I09', 'WHEN NOT THEN regar sector_sur;', 'NOT sin operando', 'sintáctico', 1, 10, 'después de NOT'),
    I('I10', 'WHEN humedad < 30 THEN regar sector_sur DURING TRUE;', 'DURING con un booleano',
      'sintáctico', 1, 48, 'duración en minutos'),
    I('I11', 'WHEN humedad < 30 THEN regar sector_sur DURING;', 'DURING sin minutos',
      'sintáctico', 1, 47, 'duración en minutos'),
    I('I12', 'WHEN humedad < 30 THEN regar sector_sur DURING 10 DURING 5;', 'DURING repetido en una acción',
      'sintáctico', 1, 51, "AND o ';'"),
    I('I13', 'WHEN humedad < 30 THEN DURING 10 regar sector_sur;', 'DURING antes de la acción',
      'sintáctico', 1, 24, 'verbo de una acción'),
    I('I14', 'WHEN humedad < 30 THEN regar sector_sur AND;', 'AND sin segunda acción',
      'sintáctico', 1, 44, 'verbo de una acción'),
    I('I15', 'humedad < 30 THEN regar sector_sur;', 'La regla no comienza con WHEN',
      'sintáctico', 1, 1, 'se esperaba WHEN'),
    I('I16', 'WHEN 30 > humedad THEN regar sector_sur;', 'Número a la izquierda de la comparación',
      'sintáctico', 1, 6, 'una condición'),
    I('I17', 'WHEN humedad < sensor_b THEN regar sector_sur;', 'Identificador como valor (excluido)',
      'sintáctico', 1, 16, "el identificador 'sensor_b'"),
    I('I18', 'WHEN humedad < 30 THEN regar sector_sur WHEN lluvia == TRUE THEN cerrar valvula_1;',
      "Falta ';' entre dos reglas", 'sintáctico', 1, 41, 'la palabra reservada WHEN'),
    I('I19', 'WHEN humedad = 30 THEN regar sector_sur;', "'=' en lugar de '=='",
      'léxico', 1, 14, "¿Quiso escribir '=='?"),
    I('I20', 'WHEN humedad < 30 THEN regar sector_sur, activar bomba;', 'Coma entre acciones',
      'léxico', 1, 40, 'separan con AND'),
    I('I21', 'WHEN () THEN regar sector_sur;', 'Paréntesis vacíos', 'sintáctico', 1, 7, 'una condición'),
    I('I22', 'WHEN when > 1 THEN regar sector_sur;', 'Palabra reservada usada como sensor',
      'sintáctico', 1, 6, "palabra reservada WHEN (escrita 'when')"),
    # ------------------------------------------------------------- casos límite
    L_err('L01', '', 'Entrada vacía', 'sintáctico', 1, 1, 'la entrada está vacía', resumen='(cadena vacía)'),
    L_err('L02', ' \t\r\n  ', 'Solo blancos, incluido CRLF', 'sintáctico', 2, 3, 'la entrada está vacía'),
    L_err('L03', 'WHEN', 'Regla truncada después de WHEN', 'sintáctico', 1, 5, 'regla incompleta'),
    L_err('L04', 'WHEN humedad < 30', 'Regla truncada después de la condición',
          'sintáctico', 1, 18, 'regla incompleta'),
    L_err('L05', 'WHEN humedad < 30 THEN regar sector_sur; basura', 'Contenido sobrante tras una regla válida',
          'sintáctico', 1, 42, 'contenido sobrante'),
    L_err('L06', 'WHEN humedad < 30 THEN regar sector_sur;;', "';' sobrante (sentencia vacía)",
          'sintáctico', 1, 41, 'contenido sobrante'),
    L_ok('L07', 'WHEN(humedad<30)THEN regar sector_sur DURING 0;', 'Sin espacios entre tokens; DURING 0'),
    L_ok('L08', 'WHEN _h <= 0 THEN regar _sur_2;', "Identificadores con '_' y dígitos; valor 0"),
    L_ok('L09', 'WHEN caudal > ' + '9' * 200 + ' THEN cerrar valvula_1;', 'Número de 200 dígitos',
         resumen='WHEN caudal > 99…9 (200 dígitos) THEN cerrar valvula_1;'),
    L_ok('L10', 'WHEN ' + 'NOT ' * 200 + 'lluvia == TRUE THEN regar sector_sur;', '200 NOT anidados',
         resumen='WHEN NOT NOT … (200 veces) lluvia == TRUE THEN regar sector_sur;'),
    L_ok('L11', 'WHEN ' + '(' * 100 + 'humedad < 30' + ')' * 100 + ' THEN regar sector_sur;',
         '100 niveles de paréntesis', resumen='WHEN ((( … humedad < 30 … ))) (100 niveles) THEN regar sector_sur;'),
    L_ok('L12', 'WHEN ' + ' AND '.join(f's{i} > {i}' for i in range(500)) + ' THEN regar sector_sur;',
         '500 comparaciones unidas por 499 AND',
         resumen='WHEN s0 > 0 AND s1 > 1 AND … AND s499 > 499 THEN regar sector_sur;'),
    L_ok('L13', 'WHEN humedad < 30 THEN regar sector_sur;\r\n' * 1000, '1000 reglas con fin de línea CRLF',
         resumen='WHEN humedad < 30 THEN regar sector_sur;\\r\\n repetida 1000 veces'),
    L_ok('L14', 'WHEN\thumedad\n<\n30\nTHEN regar\tsector_sur;', 'Tabulaciones y saltos de línea entre tokens'),
    L_err('L15', 'WHEN humedad < -1 THEN regar sector_sur;', 'Número negativo', 'léxico', 1, 16, 'sin signo'),
    L_err('L16', 'WHEN humedad < 1.5 THEN regar sector_sur;', 'Número decimal', 'léxico', 1, 17, 'enteros'),
    L_err('L17', 'WHEN humedad < 30abc THEN regar sector_sur;', "'30abc' se separa en NUM e ID",
          'sintáctico', 1, 18, "el identificador 'abc'"),
    L_err('L18', 'WHEN año > 1 THEN regar sector_sur;', "Letra 'ñ' fuera del alfabeto", 'léxico', 1, 7, 'ASCII'),
    L_err('L19', 'WHEN humedad < 30 THEN regar sector_sur;\nWHEN viento > THEN cerrar compuertas;',
          'Error en la segunda línea', 'sintáctico', 2, 15, 'un valor'),
    L_err('L20', 'WHEN humedad < ٣ THEN regar sector_sur;', 'Dígito no ASCII (modificación M5)',
          'léxico', 1, 16, 'dígitos ASCII'),
    L_ok('L21', 'WHEN lluvia > TRUE THEN encender lluvia DURING 0;',
         'Sintaxis válida aunque sin sentido: no hay análisis semántico'),
]


def mostrar_entrada(caso, maximo=None):
    """Representación visible de la entrada (\\n, \\r y \\t escapados)."""
    if caso.resumen:
        return caso.resumen
    texto = caso.entrada.replace('\r', '\\r').replace('\n', '\\n').replace('\t', '\\t')
    if maximo and len(texto) > maximo:
        texto = texto[:maximo - 1] + '…'
    return texto


def ejecutar(caso):
    """Ejecuta un caso y devuelve una fila con lo esperado y lo obtenido."""
    from agroreglas import ErrorLexico, ErrorSintactico, analizar, construir_ast, formula
    fila = {
        'id': caso.id, 'categoria': caso.categoria, 'entrada': caso.entrada,
        'entrada_mostrada': mostrar_entrada(caso), 'esperado': caso.esperado,
        'error_esperado': caso.error or '',
        'ubicacion_esperada': f'{caso.linea}:{caso.columna}' if caso.linea else '',
        'observacion': caso.observacion,
    }
    try:
        arbol = analizar(caso.entrada)
    except (ErrorLexico, ErrorSintactico) as error:
        tipo = 'léxico' if isinstance(error, ErrorLexico) else 'sintáctico'
        fila.update(obtenido='RECHAZA', error_obtenido=tipo,
                    ubicacion_obtenida=f'{error.linea}:{error.columna}',
                    esperados=' '.join(error.esperados), mensaje=str(error), detalle='')
        fila['coincide'] = (caso.esperado == 'RECHAZA' and caso.error == tipo
                            and (caso.linea, caso.columna) == (error.linea, error.columna)
                            and caso.fragmento in str(error))
        return fila
    ast = construir_ast(arbol)
    acciones = sum(len(r.acciones) for r in ast.reglas)
    condicion = formula(ast.reglas[0].condicion)
    if len(condicion) > 120:
        condicion = condicion[:119] + '…'
    fila.update(obtenido='ACEPTA', error_obtenido='', ubicacion_obtenida='', esperados='', mensaje='',
                detalle=(f'{len(ast.reglas)} {"regla" if len(ast.reglas) == 1 else "reglas"}, '
                         f'{acciones} {"acción" if acciones == 1 else "acciones"}; 1.ª condición: {condicion}'))
    fila['coincide'] = caso.esperado == 'ACEPTA'
    return fila
