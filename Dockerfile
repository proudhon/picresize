FROM python:3.12-slim

# System deps (ImageMagick + zip tools)
RUN apt-get update && apt-get install -y \
  imagemagick unzip zip \
  && rm -rf /var/lib/apt/lists/*

# Optional: relax IM policy if present (IM6/IM7 paths)
RUN sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-6/policy.xml || true
RUN sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-7/policy.xml || true

WORKDIR /app

# Copy app and install deps
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

# Copy source
COPY app app
COPY process.sh process.sh
RUN chmod +x process.sh

# Ensure expected folders exist
RUN mkdir -p originalzip original resized resizedzip

EXPOSE 8080

# Use a single worker for WebSockets; you can scale via replicas instead
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
