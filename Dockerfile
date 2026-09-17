
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY *.py ./

EXPOSE 6000

CMD ["python", "servidor.py"]
