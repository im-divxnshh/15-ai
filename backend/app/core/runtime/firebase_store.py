"""Shared Firebase Admin app for token verification and Firestore."""
import json
import os
import threading
import time
from functools import lru_cache
from .jobstore import StorageUnavailable
_lock=threading.Lock()
_auth_lock=threading.Lock()
_retry_at=0
_auth_error=None
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
def ensure_credentials(app):
    """Reject a bad key before gRPC starts its own repeated metadata retries."""
    global _retry_at,_auth_error
    from google.auth.transport.requests import Request
    with _auth_lock:
        if _auth_error and time.monotonic()<_retry_at:
            raise StorageUnavailable(_auth_error)
        try:
            credential=app.credential.get_credential()
            if not credential.valid:
                request=Request()
                def bounded_request(*args,**kwargs):
                    kwargs['timeout']=8
                    return request(*args,**kwargs)
                credential.refresh(bounded_request)
            _auth_error=None;_retry_at=0
        except Exception as error:
            data=next((arg for arg in error.args if isinstance(arg,dict)),{})
            description=str(data.get('error_description') or '').lower()
            if 'invalid jwt signature' in description:
                _auth_error='Firebase rejected the service-account key (Invalid JWT Signature). Generate a new private key in Firebase Console, import it into backend/.env, and restart the backend.'
            else:
                _auth_error=f'Firebase authentication unavailable ({type(error).__name__}); check the service-account key and connection.'
            _retry_at=time.monotonic()+60
            raise StorageUnavailable(_auth_error) from None

@lru_cache(maxsize=1)
def _firestore_client():
    from firebase_admin import firestore
    return firestore.client(app=admin_app())

def client():
    ensure_credentials(admin_app())
    return _firestore_client()
