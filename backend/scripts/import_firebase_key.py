"""Import a locally downloaded Firebase service-account JSON into backend/.env."""
import argparse
import json
from pathlib import Path
import sys

from dotenv import dotenv_values,set_key
from firebase_admin import credentials

BACKEND=Path(__file__).resolve().parents[1]


def import_key(keyfile,envfile,public_envfile=None):
    try:
        info=json.loads(Path(keyfile).expanduser().read_text())
    except (OSError,ValueError):
        raise ValueError('Cannot read the downloaded service-account JSON file. Check its local path.') from None
    required=('project_id','private_key','private_key_id','client_email','token_uri')
    if not isinstance(info,dict) or info.get('type')!='service_account' or any(not isinstance(info.get(k),str) or not info[k].strip() for k in required):
        raise ValueError('Use the service-account JSON downloaded from Firebase Project settings → Service accounts.')
    if info['token_uri']!='https://oauth2.googleapis.com/token':
        raise ValueError('The key must use the standard Google OAuth token endpoint.')
    values=dotenv_values(envfile)
    projects=[values.get('FIREBASE_PROJECT_ID')]
    if public_envfile:projects.append(dotenv_values(public_envfile).get('NEXT_PUBLIC_FIREBASE_PROJECT_ID'))
    if any(project and project!=info['project_id'] for project in projects):
        raise ValueError('This key belongs to a different project. Download a key from the Firebase project already configured in this app.')
    try:credentials.Certificate(info)
    except Exception:
        raise ValueError('The service-account private key is invalid. Use the original downloaded JSON without editing its fields.') from None
    set_key(str(envfile),'FIREBASE_CREDENTIALS',json.dumps(info,separators=(',',':')))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('keyfile',help='Path to the locally downloaded JSON; its contents are never printed')
    args=parser.parse_args()
    try:import_key(args.keyfile,BACKEND/'.env',BACKEND.parent/'frontend/.env.local')
    except ValueError as error:
        print(str(error),file=sys.stderr);return 1
    print('Imported the matching service-account key into backend/.env; other values were preserved.')
    print('Local JSON/key validation passed. Live Google acceptance still needs a connection check.')
    print('Restart the backend, then run backend/venv/bin/python scripts/check_connections.py.')
    return 0


if __name__=='__main__':sys.exit(main())
