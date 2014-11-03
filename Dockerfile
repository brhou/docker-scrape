############################################################
# Dockerfile to build docker scrape for docker interview
# Based on Ubuntu
############################################################

# Base image ubuntu, specify 14.04
FROM ubuntu:14.04

MAINTAINER Brian Hou

# update the repo
RUN apt-get update

# get rabbitmq and git
RUN apt-get install -y rabbitmq-server git

# Install pip's dependency: setuptools:
RUN apt-get install -y python python-dev python-distribute python-pip

# Expose internet port
EXPOSE 80

# Expose rabbitmq admin
EXPOSE 15672

# Expose ampq default
EXPOSE 5672

# Enable rabbitmq admin
RUN rabbitmq-plugins enable rabbitmq_management

# hack to enable running worker as ROOT
ENV C_FORCE_ROOT true

# make the directory where the code goes
RUN mkdir -p /root/git

WORKDIR /root/git

RUN git clone https://github.com/brhou/docker-scrape.git

WORKDIR docker-scrape

# dependency for pip package cryptography
RUN apt-get install -y libffi-dev libssl-dev

RUN pip install -r requirements.txt

# this has to be run since
#RUN rabbitmq-server -detached