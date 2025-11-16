FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . /app

# Use a non-root user? For simplicity we run as default user here

ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
