# Docker Setup for GAVEL C Autograders
## Overview
The C autograder environment is executed inside Docker to ensure a consistent Linux-based runtime. This is necessary because Gradescope-style C autograders are typically developed for Ubuntu and may not run correctly on Windows due to differences in compilers, shells, and system dependencies.

Java autograders continue to run directly through Maven on the host machine.

## Prerequisites
Windows Requirements
Windows 10 or Windows 11
Administrator privileges
Hardware virtualization enabled in BIOS
WSL2 support enabled
## Installing Docker Desktop
### 1. Download Docker Desktop
Download Docker Desktop from:

https://www.docker.com/products/docker-desktop/

Run the installer and accept the default settings.

### 2. Enable WSL2
Open PowerShell as Administrator and run:

wsl --install
Restart your computer when prompted.

Verify the installation:

wsl --status
Expected output:

Default Version: 2
### 3. Start Docker Desktop
Launch Docker Desktop and wait until the Docker Engine starts.

Verify installation:

docker version
Expected output:

Client:
 Version: xx.xx

Server:
 Engine:
  Version: xx.xx
### 4. Verify Docker Functionality
Run:

docker run hello-world
Expected output:

Hello from Docker!
## Building the Docker Image
Navigate to the directory containing:

Dockerfile
main.py
requirements.txt
Build the image:

docker build -t gavel-c-runtime .
Expected output:

Successfully tagged gavel-c-runtime:latest
Verify the image exists:

docker images
Expected output:

REPOSITORY       TAG       IMAGE ID
gavel-c-runtime  latest    xxxxxxxx
## Example Dockerfile
A typical Dockerfile for the C autograders might look similar to:

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    make \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work/autograder

COPY requirements.txt .

RUN pip3 install --break-system-packages -r requirements.txt

CMD ["python3", "main.py"]
Rebuild the image whenever the Dockerfile changes:

docker build -t gavel-c-runtime .
## Workspace Layout
Each submission is executed inside an isolated temporary workspace.

Example:

worker_root/
├── autograder/
│   ├── main.py
│   ├── config.json
│   └── ...
├── submission/
│   └── student files
└── results/
When mounted into Docker:

/work
├── autograder
├── submission
└── results
## How GAVEL Executes the Container
GAVEL launches the container using:

docker_cmd = [
    "docker",
    "run",
    "--rm",
    "--mount",
    f"type=bind,source={Path(worker_root).resolve()},target=/work",
    "-w",
    "/work/autograder",
    "gavel-c-runtime",
    "python3",
    "main.py",
]
This process:

Creates a temporary worker directory.
Mounts the worker directory into the container at /work.
Executes the autograder.
Writes results into:
/work/results/results.json
Automatically removes the container when execution completes.
## Testing the Image
Verify Python is available:

docker run --rm gavel-c-runtime python3 --version
Expected output:

Python 3.x.x
### Open an Interactive Shell
docker run -it --rm gavel-c-runtime bash
Useful checks:

gcc --version
python3 --version
pwd
## Updating the Image
After modifying the Dockerfile:

docker build -t gavel-c-runtime .
Force a clean rebuild:

docker build --no-cache -t gavel-c-runtime .
## Common Issues
### Docker Desktop Not Running
Error:

Cannot connect to the Docker daemon
Solution:

Open Docker Desktop.
Wait for the Docker Engine to start.
Retry the command.
Docker Command Not Found
Error:

'docker' is not recognized as an internal or external command
Solution:

Reinstall Docker Desktop.
Restart the computer.
Verify installation:
docker --version
### WSL2 Not Installed
Error:

WSL 2 installation is incomplete
Solution:

wsl --install
Reboot when prompted.

### Image Not Found
Error:

Unable to find image 'gavel-c-runtime'
Solution:

Build the image first:

docker build -t gavel-c-runtime .
### results.json Not Produced
Verify:

worker_root/
├── autograder/
├── submission/
└── results/
Confirm the autograder writes output to:

results/results.json
inside the mounted workspace.

## Verification Checklist
Before running C autograders:

Docker Desktop installed
Docker Engine running
WSL2 enabled
docker version succeeds
docker run hello-world succeeds
docker images shows gavel-c-runtime
docker run --rm gavel-c-runtime python3 --version succeeds
Once all checks pass, GAVEL is ready to execute Gradescope-style C autograders in an isolated Linux environment.