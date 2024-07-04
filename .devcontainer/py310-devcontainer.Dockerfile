FROM --platform=linux/amd64 python:3.10-slim-buster

RUN pip3 install --upgrade pip

COPY requirements.txt .
COPY testing_requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r testing_requirements.txt

# Clean up
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*