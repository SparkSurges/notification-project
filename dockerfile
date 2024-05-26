FROM python:3.11-bullseye

WORKDIR /app

COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run service.py when the container launches
CMD ["python", "service.py"]
