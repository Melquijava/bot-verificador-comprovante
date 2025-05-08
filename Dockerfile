FROM python:3.11-slim

# Instala dependências do sistema, incluindo o idioma "por" do Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    libpoppler-cpp-dev \
    poppler-utils

# Cria diretório de trabalho e copia apenas o requirements primeiro
WORKDIR /app
COPY requirements.txt .

# Instala dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Agora copia o restante do projeto
COPY . .

CMD ["python", "main_verificador_com_interface.py"]
