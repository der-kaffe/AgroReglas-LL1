"""Ejecuta documentacion/AgroReglas.ipynb con un kernel de Jupyter y guarda las salidas.

    python3 herramientas/ejecutar_notebook.py

Requiere (solo para esta tarea opcional): pip install nbclient nbformat ipykernel
Equivale a: jupyter nbconvert --to notebook --execute --inplace documentacion/AgroReglas.ipynb
"""
import sys
from pathlib import Path

try:
    import nbformat
    from nbclient import NotebookClient
except ImportError:
    sys.exit('Instale nbclient, nbformat e ipykernel para ejecutar el notebook.')

RUTA = Path(__file__).resolve().parents[1] / 'documentacion' / 'AgroReglas.ipynb'
notebook = nbformat.read(RUTA, as_version=4)
NotebookClient(notebook, timeout=180, kernel_name='python3',
               resources={'metadata': {'path': str(RUTA.parent)}}).execute()
nbformat.write(notebook, RUTA)
errores = [o for c in notebook.cells if c.cell_type == 'code' for o in c.get('outputs', [])
           if o.output_type == 'error']
celdas = [c.execution_count for c in notebook.cells if c.cell_type == 'code']
print(f'{RUTA.name}: {len(celdas)} celdas de código ejecutadas, {len(errores)} errores.')
sys.exit(1 if errores else 0)
