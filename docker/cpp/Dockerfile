FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
# - build-essential, cmake, git: Build tools
# - libboost-all-dev: Networking & threading
# - libpq-dev, libpqxx-dev: PostgreSQL client
# - nlohmann-json3-dev: JSON parsing
# - libspdlog-dev: Logging
# - libgtest-dev: Testing
# - wget, ca-certificates: Downloading ONNX Runtime
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libboost-all-dev \
    libpq-dev \
    libpqxx-dev \
    nlohmann-json3-dev \
    libspdlog-dev \
    libgtest-dev \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install ONNX Runtime (C++ API)
WORKDIR /tmp
RUN wget https://github.com/microsoft/onnxruntime/releases/download/v1.17.1/onnxruntime-linux-x64-1.17.1.tgz \
    && tar -xzf onnxruntime-linux-x64-1.17.1.tgz \
    && mv onnxruntime-linux-x64-1.17.1 /opt/onnxruntime \
    && cp -r /opt/onnxruntime/include/* /usr/local/include/ \
    && cp -r /opt/onnxruntime/lib/* /usr/local/lib/ \
    && ldconfig \
    && rm -rf /tmp/*

# Set up work directory
WORKDIR /app

# Default command (can be overridden in docker-compose)
CMD ["/bin/bash"]
