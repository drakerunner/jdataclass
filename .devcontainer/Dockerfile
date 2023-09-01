FROM mcr.microsoft.com/vscode/devcontainers/python:0-3.11-bullseye

RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

USER vscode
RUN pipx install poetry
