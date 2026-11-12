"""Export the active API contract without starting workers or exposing env values."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import app

target=Path(__file__).resolve().parents[2]/'docs/openapi.json'
target.parent.mkdir(exist_ok=True)
contract=app.openapi()
target.write_text(json.dumps(contract,indent=2)+'\n')
print(f'Exported {len(contract["paths"])} paths to docs/openapi.json')
