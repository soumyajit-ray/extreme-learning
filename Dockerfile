FROM python:3.9

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use shell form to allow environment variable expansion
CMD uvicorn main:app --host 0.0.0.0 --port $PORT