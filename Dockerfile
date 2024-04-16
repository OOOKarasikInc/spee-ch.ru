FROM python:3.12-slim
RUN apt-get update && apt-get -y install libpq-dev gcc iputils-ping
COPY . .
RUN pip install -r requirements.txt

EXPOSE 8000
ENTRYPOINT ./entrypoint.sh
