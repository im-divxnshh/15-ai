FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home nova
COPY backend/main.py ./
COPY backend/app ./app
COPY backend/scripts ./scripts
RUN mkdir -p /app/data && chown -R nova:nova /app
USER nova
EXPOSE 8000
# Redis elects one worker across replicas; files and history use managed storage.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
