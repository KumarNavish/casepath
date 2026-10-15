from pathlib import Path
p=Path(__file__).resolve().parent.parent/'coordinator/final_reconcile.py'
exec(compile(p.read_text(),str(p),'exec'))
