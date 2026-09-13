FROM python:3.12-slim

WORKDIR /app

COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install --no-cache-dir -r frontend/requirements.txt

COPY frontend frontend

WORKDIR /app/frontend

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
