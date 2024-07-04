#!/bin/bash

# Default values
NUM_CONTAINERS=20
BASE_PORT=3001
RESPONSE_SEQUENCE=""

# Function to display usage
usage() {
    echo "Usage: $0 --num-containers <number_of_containers> --base-port <base_port> [--response-sequence <response_sequence>]"
    echo "  --num-containers     Number of proxy containers to start (default: 20)"
    echo "  --base-port          Base port number to start assigning ports from (default: 3001)"
    echo "  --response-sequence  Response sequence to be set in the environment variable RESPONSE_SEQUENCE"
    exit 1
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --num-containers)
            NUM_CONTAINERS="$2"
            shift 2
            ;;
        --base-port)
            BASE_PORT="$2"
            shift 2
            ;;
        --response-sequence)
            RESPONSE_SEQUENCE="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

# Clear addresses.txt if it already exists
> ./data/addresses.txt

# Start or restart the containers
for i in $(seq 1 $NUM_CONTAINERS); do
    PORT=$((BASE_PORT + i - 1))
    CONTAINER_NAME="proxy${i}"

    # Check if the container exists and stop it if it does
    if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
        docker stop "${CONTAINER_NAME}"
        docker rm "${CONTAINER_NAME}"
        echo "Stopped and removed existing container ${CONTAINER_NAME}"
    fi

    # Start the container
    if [[ -z "$RESPONSE_SEQUENCE" ]]; then
        docker run -d --name "${CONTAINER_NAME}" -p "${PORT}:3000" wsd-proxy-test:latest
    else
        docker run -d --name "${CONTAINER_NAME}" -p "${PORT}:3000" -e RESPONSE_SEQUENCE="${RESPONSE_SEQUENCE}" wsd-proxy-test:latest
    fi

    # Get the proxy address and write to addresses.txt
    PROXY_ADDRESS="http://localhost:${PORT}"
    echo "${PROXY_ADDRESS}" >> ./data/addresses.txt
    echo "Started container ${CONTAINER_NAME} on port ${PORT}"
done

echo "Proxy containers started. Proxy addresses written to data/addresses.txt"
