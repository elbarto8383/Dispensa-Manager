ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip py3-virtualenv

WORKDIR /app
COPY dispensa_backend/ /app/

RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir flask flask-cors requests

CMD ["/app/venv/bin/python", "app.py"]
