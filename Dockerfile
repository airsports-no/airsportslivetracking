FROM python:3.12-slim-bookworm AS tracker_base
ENV PYTHONUNBUFFERED 1

###### SETUP BASE INFRASTRUCTURE ######
RUN apt-get update; apt-get install curl gpg -y; \
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg; \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list; \
    ln -snf /usr/share/zoneinfo/UTC /etc/localtime && echo UTC > /etc/timezone; \
    apt update && apt -y upgrade \
    && apt -y install build-essential \
    cmake vim libproj-dev proj-data proj-bin \
    libgdal-dev libgeos-dev redis-server daphne \
    libcliquer1 libgslcblas0 latexmk texlive \
    texlive-latex-base texlive-latex-extra \
    texlive-latex-recommended ca-certificates gnupg \
    nodejs \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*


RUN npm install -g npm@10.2.4
RUN addgroup --system django \
    && adduser --system --ingroup django -u 200 django


RUN pip --no-cache-dir install -U pip
###### INSTALL PYTHON PACKAGES ######
ENV LC_CTYPE C.UTF-8
ENV LC_ALL C.UTF-8
ENV LANGUAGE C.UTF-8
ENV LANG C.UTF-8
RUN pip --no-cache-dir install cython
COPY requirements.txt /
RUN pip --no-cache-dir install -Ur /requirements.txt

RUN pip --no-cache-dir uninstall -y shapely
RUN pip --no-cache-dir install --no-binary :all: shapely

###### SETUP APPLICATION INFRASTRUCTURE ######
# TODO: Required for a test, should be changed
COPY documentation /documentation
COPY config /config
COPY --chown=django:django wait-for-it.sh config/gunicorn.sh config/daphne.sh /
RUN chmod 755 /gunicorn.sh /wait-for-it.sh /daphne.sh

COPY package* /
RUN npm install && npm cache clean --force d# burde vært `npm ci` i stedet, men må ha package-lock.json/npm-shrinkwrap.json


###### INSTALL APPLICATION ######
COPY --chown=django:django reactjs /reactjs
COPY --chown=django:django src /src
# Required for tests
COPY --chown=django:django data /data


RUN mkdir /logs
RUN chown django /logs
RUN npm run webpack
WORKDIR /src
# Force font cache generation
RUN python -c "import matplotlib"
# RUN python3 manage.py collectstatic --noinput
