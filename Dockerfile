FROM python:3.10 as tracker_base
ENV PYTHONUNBUFFERED 1

###### SETUP BASE INFRASTRUCTURE ######
RUN ln -snf /usr/share/zoneinfo/UTC /etc/localtime && echo UTC > /etc/timezone &&\
    apt update && apt -y upgrade &&\
    apt -y install curl build-essential vim libproj-dev proj-data proj-bin libgeos-dev libgdal-dev redis-server daphne libcliquer1 libgslcblas0 libtbb2 latexmk texlive texlive-full libproj19
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && apt install -y nodejs
RUN npm install -g npm@9.3.1
RUN addgroup --system django \
    && adduser --system --ingroup django -u 200 django


RUN pip install -U pip
COPY opensky-api /opensky-api
###### INSTALL PYTHON PACKAGES ######
ENV LC_CTYPE C.UTF-8
ENV LC_ALL C.UTF-8
ENV LANGUAGE C.UTF-8
ENV LANG C.UTF-8
RUN pip install cython
COPY requirements.txt /
RUN pip install -Ur /requirements.txt
RUN pip install -e /opensky-api/python
RUN pip uninstall -y cartopy shapely
RUN pip install --no-binary :all: shapely
RUN pip install cartopy

#COPY django-rest-authemail /django-rest-authemail
#RUN pip3 install -U -e /django-rest-authemail

###### SETUP APPLICATION INFRASTRUCTURE ######
COPY documentation /documentation
COPY config /config
COPY --chown=django:django wait-for-it.sh config/gunicorn.sh config/daphne.sh /
RUN chmod 755 /gunicorn.sh /wait-for-it.sh /daphne.sh

COPY package* /
RUN npm install


###### INSTALL APPLICATION ######
COPY --chown=django:django reactjs /reactjs
#RUN cd / && npm run webpack
COPY --chown=django:django src /src

COPY --chown=django:django data /data



RUN mkdir /logs
RUN chown django /logs
# Need to download new version for Ubuntu 20.04
#COPY scip /scip
#RUN apt install /scip/SCIPOptSuite-7.0.2-Linux-ubuntu.deb
WORKDIR /src

###### LABEL THE CURRENT IMAGE ######
ARG GIT_COMMIT_HASH
LABEL GIT_COMMIT_HASH=$GIT_COMMIT_HASH

FROM tracker_base as tracker_init
CMD [ "bash", "-c", "python3 manage.py migrate && python3 manage.py initadmin && python3 manage.py createdefaultscores && redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD FLUSHALL" ]

FROM tracker_base as tracker_web
###### INSTALL JAVASCRIPT PACKAGES ######
WORKDIR /

RUN npm run webpack
WORKDIR /src
RUN python3 manage.py collectstatic --noinput
CMD [ "bash", "-c", "/gunicorn.sh" ]

FROM tracker_base as tracker_daphne
CMD [ "bash", "-c", "/daphne.sh" ]

FROM tracker_base as tracker_celery
CMD [ "bash", "-c", "celery -A live_tracking_map worker -l DEBUG -f /logs/celery.log" ]

FROM tracker_base as tracker_processor
CMD [ "bash", "-c", "python3 position_processor.py" ]

FROM tracker_base as opensky_consumer
COPY --chown=django:django aircraft_database /aircraft_database
CMD [ "bash", "-c", "python3 opensky_consumer.py $OPEN_SKY_USERNAME $OPEN_SKY_PASSWORD" ]

FROM tracker_base as ogn_consumer
CMD [ "bash", "-c", "python3 ogn_consumer.py" ]