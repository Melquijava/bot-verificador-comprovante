FROM python:3.11-slim

# Instala dependências nativas e idiomas do Tesseract (incluindo "por")
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    libpoppler-cpp-dev \
    poppler-utils \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY . .

CMD ["python", "main_verificador_com_interface.py"]