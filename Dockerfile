FROM python:3.11-slim

# Instala dependências do sistema necessárias
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libpoppler-cpp-dev \
    tesseract-ocr

# Define diretório de trabalho
WORKDIR /app

# Copia primeiro o requirements.txt para instalar as dependências
COPY requirements.txt .

# Instala pacotes Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante da aplicação
COPY . .

# Comando de inicialização
CMD ["python", "main_verificador_com_interface.py"]