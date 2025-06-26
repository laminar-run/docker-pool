#!/bin/bash
set -e

echo "Installing additional tools and packages..."

# Install Python packages
pip3 install --user \
    requests \
    numpy \
    pandas

# Install Node.js packages globally
npm install -g \
    lodash \
    axios \
    moment

# Install Ruby gems
gem install \
    json \
    httparty \
    colorize

# Create Go workspace
mkdir -p /home/executor/go/{bin,src,pkg}

# Install common Go tools
export GOPATH=/home/executor/go
export PATH=$PATH:/home/executor/go/bin

# Note: Go modules will be handled per-project basis

# Install Rust tools (as root, then change ownership)
/root/.cargo/bin/cargo install --root /usr/local \
    ripgrep \
    fd-find

echo "Tool installation completed successfully!"