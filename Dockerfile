FROM python:3.8-slim-buster

WORKDIR /app

COPY cleanup_script.py ./

RUN pip install requests python-dateutil

ENTRYPOINT ["python", "/app/cleanup_script.py"]
