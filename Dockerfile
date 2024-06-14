FROM python:3.8-bullseye

# Stop any questions when installing packages
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y git jq awscli

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

RUN pip install --upgrade pip
RUN pip install pip-tools
ADD ./requirements.txt ./
RUN pip-sync requirements.txt

ADD ./tests ./tests
