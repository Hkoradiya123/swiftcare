FROM python:3.12-slim

WORKDIR /app

COPY swiftcare-contracts /contracts
RUN pip install --no-cache-dir /contracts

COPY swiftcare-notify/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY swiftcare-notify/ .

CMD ["python", "-m", "app.main"]
