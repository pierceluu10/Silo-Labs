from __future__ import annotations

import modal

image = (
    modal.Image.from_registry("python:3.12-slim")
    .apt_install("build-essential", "cmake", "git", "ninja-build",
                 "gcc-arm-none-eabi", "libnewlib-arm-none-eabi",
                 "libstdc++-arm-none-eabi-newlib", "curl", "ca-certificates")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g @wokwi/cli",
        "git clone --depth=1 --branch 2.1.0 https://github.com/raspberrypi/pico-sdk.git /opt/pico-sdk",
        "cd /opt/pico-sdk && git submodule update --init --recursive",
    )
    .pip_install_from_requirements("requirements.txt")
    .env({"PICO_SDK_PATH": "/opt/pico-sdk"})
    .add_local_python_source("app")
    .add_local_dir("knowledge_data", remote_path="/root/knowledge_data")
)

app = modal.App("silo-labs", image=image)


@app.function(
    secrets=[modal.Secret.from_name("silo-anthropic")],
    timeout=300,
    memory=2048,
)
@modal.asgi_app()
def fastapi_app():
    from app.main import app as fastapi
    return fastapi
