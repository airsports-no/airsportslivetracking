FROM ubuntu:18.04
ENV PYTHONUNBUFFERED 1

###### SETUP BASE INFRASTRUCTURE ######
RUN apt-get update && apt-get install -y python3.6 python3-pip curl build-essential vim libproj-dev proj-data proj-bin libgeos-dev libgdal-dev
RUN curl -sL https://deb.nodesource.com/setup_10.x -o nodesource_setup.sh && bash nodesource_setup.sh && apt-get update && apt-get install -y nodejs && rm nodesource_setup.sh


###### INSTALL PYTHON PACKAGES ######
ENV LC_CTYPE C.UTF-8
ENV LC_ALL C.UTF-8
ENV LANGUAGE C.UTF-8
ENV LANG C.UTF-8
RUN pip3 install cython numpy
COPY requirements.txt /
RUN pip3 install -Ur /requirements.txt


###### SETUP APPLICATION INFRASTRUCTURE ######
COPY config /config
COPY config/gunicorn.sh /
RUN chmod 755 /gunicorn.sh


###### INSTALL JAVASCRIPT PACKAGES ######
COPY package*.json /
RUN npm install


###### INSTALL APPLICATION ######
COPY reactjs /reactjs
RUN cd / && npm run webpack
COPY src /src
WORKDIR /src

###### LABEL THE CURRENT IMAGE ######
ARG GIT_COMMIT_HASH
LABEL GIT_COMMIT_HASH=$GIT_COMMIT_HASH
