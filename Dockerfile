FROM ubuntu:latest

RUN apt-get update
RUN apt-get install -y python3-dev python3 python3-pip curl unzip git jq

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \ 
    unzip awscliv2.zip && \
    ./aws/install

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

RUN pip install --upgrade pip
ADD ./requirements.txt ./
RUN pip install -r requirements.txt

ADD ./tests ./tests
