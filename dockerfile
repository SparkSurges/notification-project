FROM python:3.11-bullseye

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Set PYTHONUNBUFFERED to ensure that Python outputs are not buffered
ENV PYTHONUNBUFFERED 1

COPY . .

CMD ["python3", "service.py"]
