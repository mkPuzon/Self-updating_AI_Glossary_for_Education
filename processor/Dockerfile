FROM python:3.12-slim
WORKDIR /app
COPY processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY processor/ ./processor/
COPY shared/ ./shared/
ENV PYTHONPATH=/app:/app/processor
CMD ["python", "processor/main.py"]
