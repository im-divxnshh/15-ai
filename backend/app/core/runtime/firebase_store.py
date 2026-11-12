"""Shared Firebase Admin app for token verification and Firestore."""
import json
import os
import threading
from functools import lru_cache
from .jobstore import StorageUnavailable
_lock=threading.Lock()
def admin_app():
    import firebase_admin
    from firebase_admin import credentials
    with _lock:
        try: return firebase_admin.get_app()
        except ValueError:
            try:
                info=json.loads(os.environ['FIREBASE_CREDENTIALS'])
                return firebase_admin.initialize_app(credentials.Certificate(info),{'projectId':os.environ['FIREBASE_PROJECT_ID']})
            except Exception as error: raise StorageUnavailable(f'Firebase configuration unavailable ({type(error).__name__})') from None
@lru_cache(maxsize=1)
def client():
    from firebase_admin import firestore
    return firestore.client(app=admin_app())
