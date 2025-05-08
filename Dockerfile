FROM python:3.11-slim

RUN apt-get update && apt-get install -y poppler-utils libpoppler-cpp-dev tesseract-ocr \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY requirements.txt .

CMD ["python", "main_verificador_com_interface.py"]
