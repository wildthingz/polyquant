FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
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
    unzip \
    openssh-server \
    gdb \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# Configure SSH for CLion
RUN mkdir /var/run/sshd
RUN echo 'root:root' | chpasswd
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

# Install ONNX Runtime (C++ API)
WORKDIR /tmp
RUN wget https://github.com/microsoft/onnxruntime/releases/download/v1.17.1/onnxruntime-linux-x64-1.17.1.tgz \
    && tar -xzf onnxruntime-linux-x64-1.17.1.tgz \
    && mv onnxruntime-linux-x64-1.17.1 /opt/onnxruntime \
    && cp -r /opt/onnxruntime/include/* /usr/local/include/ \
    && cp -r /opt/onnxruntime/lib/* /usr/local/lib/ \
    && ldconfig \
    && rm -rf /tmp/*

# Install IBKR TWS API (Version 9.76.01)
WORKDIR /tmp
RUN wget https://interactivebrokers.github.io/downloads/twsapi_macunix.976.01.zip \
    && unzip twsapi_macunix.976.01.zip \
    && mkdir -p /opt/twsapi \
    && cp -r IBJts/source/cppclient/client/* /opt/twsapi/ \
    && rm -rf /tmp/*

# Set Default Environment Variables
ENV DB_HOST=db
ENV DB_PORT=5432
ENV DB_NAME=polyquant
ENV DB_USER=polyquant_user
ENV DB_PASSWORD=password123
ENV IBKR_HOST=ib_gateway

# Set up work directory
WORKDIR /app

# Expose SSH port
EXPOSE 22

# Start SSH server
CMD ["/usr/sbin/sshd", "-D"]
