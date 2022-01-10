FROM ubuntu:latest

# Stop any questions when installing packages
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y python3-dev python3 python3-pip git jq awscli

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

RUN pip install --upgrade pip
ADD ./requirements.txt ./
RUN pip install -r requirements.txt

ADD ./tests ./tests
