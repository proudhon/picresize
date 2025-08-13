FROM python:3.12-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
  imagemagick \
  unzip \
  zip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN chmod +x process.sh

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Gunicorn port
EXPOSE 8000

# Start Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8004", "--timeout", "600", "app:app"]

