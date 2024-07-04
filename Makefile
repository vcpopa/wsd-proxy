# Command-line arguments with default values
PROXIES ?= 0
BASE_PORT ?= 3001
GENERATE_DATA ?= 0
RESPONSE_SEQUENCE ?=

# Define the virtual environment directory
VENV_DIR = venv

# Define the Docker image file path
DOCKER_IMAGE_PATH = ./proxy-server/wsd-proxy-test.tar

# Define the Python script for generating test data
GENERATE_DATA_SCRIPT = utils/generate_test_data.py

# Define the main Python script and its arguments
MAIN_SCRIPT = src/main.py
INPUT_FILE = data/input.txt
ADDRESSES_FILE = data/addresses.txt
OUTPUT_FILE = data/output.txt

# Define the shell scripts that need to be executable
SHELL_SCRIPTS = ./utils/start_proxies.sh

.PHONY: all setup venv install_requirements run_proxies generate_data run_main create_data_dir chmod_files

all: setup venv install_requirements create_data_dir chmod_files run_proxies generate_data run_main

setup:
	@echo "Setting up the environment..."

venv:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV_DIR)

install_requirements: venv
	@echo "Installing requirements..."
	$(VENV_DIR)/bin/pip install -r requirements.txt

create_data_dir:
	@echo "Creating data directory if it doesn't exist..."
	@mkdir -p data

chmod_files:
	@echo "Changing permissions of necessary files to make them executable..."
	@chmod +x $(SHELL_SCRIPTS)

run_proxies: chmod_files
ifeq ($(PROXIES), 0)
	@echo "No proxies starting..."
else ifeq ($(shell [ $(PROXIES) -le 20 ] && echo 0 || echo 1), 0)
	@echo "Loading Docker image and running proxies..."
	docker load --input $(DOCKER_IMAGE_PATH)
ifeq ($(strip $(RESPONSE_SEQUENCE)),)
	$(SHELL_SCRIPTS) --num-containers $(PROXIES) --base-port $(BASE_PORT)
else
	$(SHELL_SCRIPTS) --num-containers $(PROXIES) --base-port $(BASE_PORT) --response-sequence "$(RESPONSE_SEQUENCE)"
endif
else
	$(error "You can't run more than 20 proxies at a time")
endif

generate_data:
ifeq ($(GENERATE_DATA), 0)
	@echo "No data generated..."
else ifeq ($(shell [ $(GENERATE_DATA) -le 1000000 ] && echo 0 || echo 1), 0)
	@echo "Generating test data..."
	$(VENV_DIR)/bin/python $(GENERATE_DATA_SCRIPT) $(GENERATE_DATA)
else
	$(error "You can't generate more than 1 million data points at a time")
endif

run_main:
	@echo "Running main Python script..."
	$(VENV_DIR)/bin/python $(MAIN_SCRIPT) $(INPUT_FILE) $(ADDRESSES_FILE) $(OUTPUT_FILE)

