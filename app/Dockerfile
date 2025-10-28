FROM python:3.11-slim

WORKDIR /app

# Install networking utilities
RUN apt-get update && apt-get install -y iputils-ping dnsutils && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make run.sh executable
RUN chmod +x /app/run.sh

#EXPOSE 5000

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["bash", "run.sh"]
