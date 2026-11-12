"""Private Cloudflare R2 objects using S3 SigV4; no public bucket URLs."""
import hashlib
import hmac
import os
from datetime import datetime,timezone
from urllib.parse import quote
import httpx
from . import jobstore as db

REQUIRED=('R2_ACCOUNT_ID','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET')
def ready():return os.getenv('FILE_STORAGE_BACKEND','r2')=='r2' and all(os.getenv(k) for k in REQUIRED)

def request(method,object_key,data=b''):
    if not ready():raise db.StorageUnavailable('Configure private R2 bucket credentials')
    db.assert_lease()
    host=os.environ['R2_ACCOUNT_ID']+'.r2.cloudflarestorage.com'
    path='/'+quote(os.environ['R2_BUCKET'],safe='')+'/'+quote(object_key,safe='/')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');day=stamp[:8]
    digest=hashlib.sha256(data).hexdigest()
    headers={'host':host,'x-amz-content-sha256':digest,'x-amz-date':stamp}
    signed=';'.join(sorted(headers));canonical=''.join(k+':'+headers[k]+'\n' for k in sorted(headers))
    scope=day+'/auto/s3/aws4_request'
    message='\n'.join([method,path,'',canonical,signed,digest])
    signing='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(message.encode()).hexdigest()
    secret=('AWS4'+os.environ['R2_SECRET_ACCESS_KEY']).encode()
    for part in (day,'auto','s3','aws4_request'):secret=hmac.new(secret,part.encode(),hashlib.sha256).digest()
    signature=hmac.new(secret,signing.encode(),hashlib.sha256).hexdigest()
    headers['Authorization']='AWS4-HMAC-SHA256 Credential='+os.environ['R2_ACCESS_KEY_ID']+'/'+scope+', SignedHeaders='+signed+', Signature='+signature
    try:
        with httpx.Client(timeout=20) as client:response=client.request(method,'https://'+host+path,headers=headers,content=data)
        if method=='DELETE' and response.status_code==404:return b''
        if response.status_code==404:raise FileNotFoundError('File object not found')
        if response.status_code>=300:raise db.StorageUnavailable(f'R2 request failed (HTTP {response.status_code})')
        return response.content
    except (db.StorageUnavailable,FileNotFoundError):raise
    except Exception as error:raise db.StorageUnavailable(f'R2 unavailable ({type(error).__name__})') from None

def put(key,data):request('PUT',key,data)
def get(key):return request('GET',key)
def delete(key):request('DELETE',key)
