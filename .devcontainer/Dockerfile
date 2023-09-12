FROM mcr.microsoft.com/vscode/devcontainers/python:0-3.11-bullseye

RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

USER vscode
RUN curl https://pyenv.run | bash
RUN pipx install poetry

RUN echo '' >> ~/.bashrc
RUN echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
RUN echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
RUN echo 'eval "$(pyenv init -)"' >> ~/.bashrc
