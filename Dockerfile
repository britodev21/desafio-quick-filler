# ---------------------------------------------------------------------------
# Estágio 1: build do front
# ---------------------------------------------------------------------------
FROM node:22-alpine AS front

WORKDIR /front

# package.json e lock primeiro, sozinhos: enquanto as dependências não mudam,
# o Docker reaproveita a camada do npm ci e o build não reinstala nada.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# ---------------------------------------------------------------------------
# Estágio 2: backend + o front já buildado
# ---------------------------------------------------------------------------
FROM python:3.13-slim

# tesseract-ocr-por é o pacote de idioma: sem ele o tesseract instala só o
# inglês e a leitura de documento em português sai errada.
# O rm do lists/ apaga o índice do apt, que não serve pra nada em runtime.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        tesseract-ocr \
        tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Mesma ideia do npm ci: requirements sozinho antes do código, pra mudança em
# arquivo .py não invalidar a camada do pip.
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

# O FastAPI serve daqui; o caminho tem que bater com o DIRETORIO_FRONT.
COPY --from=front /front/dist frontend/dist

# Roda como usuário sem privilégio. Os diretórios são criados e entregues
# antes, porque a aplicação escreve neles e o root já não estaria disponível.
RUN useradd --create-home aplicacao \
    && mkdir -p uploads planilhas \
    && chown -R aplicacao:aplicacao /app
USER aplicacao

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
