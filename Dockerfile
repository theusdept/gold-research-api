FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python modules
COPY main.py .
COPY visa_idx_client.py .
COPY visa_idx_sync.py .

EXPOSE 8000

CMD ["python", "main.py"]

