# Use a lightweight Python base
FROM python:3.12-slim

# Install required system packages
RUN apt-get update && apt-get install -y \
  imagemagick \
  unzip \
  zip \
  && rm -rf /var/lib/apt/lists/*

# Attempt to allow ImageMagick read/write (ignore if file missing)
RUN sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-6/policy.xml || true
RUN sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-7/policy.xml || true

# Set working directory
WORKDIR /app

# Copy app files
COPY app.py process.sh requirements.txt ./
COPY templates ./templates

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Ensure folders exist
RUN mkdir -p ./originalzip ./original ./resized ./resizedzip

# Expose Flask port
EXPOSE 8080

# Run the Flask app
CMD ["python", "app.py"]
