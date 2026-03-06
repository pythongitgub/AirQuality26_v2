import sys, json
from pathlib import Path
p = Path(sys.argv[1])
nb = json.loads(p.read_text(encoding='utf-8'))
for i,c in enumerate(nb.get('cells', [])):
    if 'outputs' not in c and c.get('cell_type')=='code':
        raise SystemExit(f'Cell {i} missing outputs')
    if 'id' not in c:
        raise SystemExit(f'Cell {i} missing id')
print('OK', p)
