# Tabla LL(1) de AgroReglas

Cada número es una producción de `resultados/gramatica.txt`; las celdas vacías son ERROR.

| No terminal | WHEN | THEN | ID | OP_REL | NUM | TRUE | FALSE | NOT | AND | OR | PARENT_IZQ | PARENT_DER | DURING | PUNTO_COMA | EOF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Programa | 1 |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Resto | 2 |   |   |   |   |   |   |   |   |   |   |   |   |   | 3 |
| Regla | 4 |   |   |   |   |   |   |   |   |   |   |   |   |   |   |
| Condicion |   |   | 5 |   |   |   |   | 5 |   |   | 5 |   |   |   |   |
| ColaOr |   | 7 |   |   |   |   |   |   |   | 6 |   | 7 |   |   |   |
| Conjuncion |   |   | 8 |   |   |   |   | 8 |   |   | 8 |   |   |   |   |
| ColaAnd |   | 10 |   |   |   |   |   |   | 9 | 10 |   | 10 |   |   |   |
| Factor |   |   | 13 |   |   |   |   | 11 |   |   | 12 |   |   |   |   |
| Comparacion |   |   | 14 |   |   |   |   |   |   |   |   |   |   |   |   |
| Valor |   |   |   |   | 15 | 16 | 17 |   |   |   |   |   |   |   |   |
| Acciones |   |   | 18 |   |   |   |   |   |   |   |   |   |   |   |   |
| ColaAcciones |   |   |   |   |   |   |   |   | 19 |   |   |   |   | 20 |   |
| Accion |   |   | 21 |   |   |   |   |   |   |   |   |   |   |   |   |
| Duracion |   |   |   |   |   |   |   |   | 23 |   |   |   | 22 | 23 |   |
