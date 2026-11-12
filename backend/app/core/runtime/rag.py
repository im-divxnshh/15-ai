"""Neon chunks with provenance and stable local token-overlap embeddings.

Groq is the only AI provider. Feature-hash vectors are lexical, not semantic.
Only the current Firestore file generation participates in retrieval.
"""
import hashlib
import math
import os
import re
from contextlib import contextmanager
from functools import lru_cache
from . import jobstore as db
DIMENSIONS=384
MODEL='local-token-hash-v1-384'
def embedding(text):
    vector=[0.]*DIMENSIONS
    for token in re.findall(r'\w+',text.casefold()):
        digest=hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4],'big')%DIMENSIONS]+=1. if digest[4]&1 else -1.
    norm=math.sqrt(sum(v*v for v in vector));return [v/norm for v in vector] if norm else vector

def literal(vector): return '['+','.join(str(v) for v in vector)+']'
@contextmanager
def connect():
    import psycopg
    if not os.getenv('NEON_URL'): raise db.StorageUnavailable('NEON_URL is not configured')
    try:
        with psycopg.connect(os.environ['NEON_URL'],sslmode='require',connect_timeout=10) as connection:
            connection.execute("SET LOCAL statement_timeout = '10s'")
            yield connection
    except db.StorageUnavailable: raise
    except Exception as error: raise db.StorageUnavailable(f'Neon RAG unavailable ({type(error).__name__})') from None

@lru_cache(maxsize=1)
def init():
    with connect() as connection:
        connection.execute('SELECT pg_advisory_xact_lock(15842001)')
        connection.execute('CREATE EXTENSION IF NOT EXISTS vector')
        connection.execute("""CREATE TABLE IF NOT EXISTS nova_chunks (
          user_id TEXT NOT NULL, source_id TEXT NOT NULL, generation TEXT NOT NULL,
          position INTEGER NOT NULL, filename TEXT NOT NULL, content TEXT NOT NULL,
          embedding vector(384) NOT NULL, model TEXT NOT NULL,
          PRIMARY KEY(user_id,source_id,generation,position))""")
        connection.execute('CREATE INDEX IF NOT EXISTS nova_chunks_owner ON nova_chunks(user_id,source_id,generation)')
def replace(user,source,generation,filename,text):
    init()
    chunks=[text[start:start+3200] for start in range(0,len(text),2800) if text[start:start+3200].strip()]
    with connect() as connection:
        connection.execute('DELETE FROM nova_chunks WHERE user_id=%s AND source_id=%s AND generation=%s',(user,source,generation))
        with connection.cursor() as cursor:
            cursor.executemany('INSERT INTO nova_chunks VALUES(%s,%s,%s,%s,%s,%s,%s::vector,%s)',[(user,source,generation,i,filename,chunk,literal(embedding(chunk)),MODEL) for i,chunk in enumerate(chunks)])
    return len(chunks)
def delete(user,source,generation=None):
    init()
    with connect() as connection:
        connection.execute('DELETE FROM nova_chunks WHERE user_id=%s AND source_id=%s'+(' AND generation=%s' if generation else ''),(user,source,generation) if generation else (user,source))
def search(user,query,k=6):
    from . import repository as repo
    files=[r for r in repo.list_for(user,'file',100000) if r.get('indexed') and r.get('generation')]
    if not files: return []
    init()
    sources=[r['id'] for r in files];generations=[r['generation'] for r in files];vector=literal(embedding(query))
    with connect() as connection:
        rows=connection.execute("""SELECT source_id,generation,position,filename,content,1-(embedding <=> %s::vector) AS score
          FROM nova_chunks WHERE user_id=%s AND (source_id,generation) IN
          (SELECT * FROM unnest(%s::text[],%s::text[])) AND model=%s
          ORDER BY embedding <=> %s::vector LIMIT %s""",(vector,user,sources,generations,MODEL,vector,k)).fetchall()
    return [{'id':f'{source}:{generation}:{position}','content':content,'source_file':filename,'source_id':source,'generation':generation,'chunk_index':position,'kind':'file','score':max(0.,float(score)),'embedding_model':MODEL} for source,generation,position,filename,content,score in rows if score is not None and score>0]
