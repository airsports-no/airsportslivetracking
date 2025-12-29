# Stage 1: Build frontend assets
FROM node:24-bookworm-slim AS frontend_builder
WORKDIR /app
COPY reactjs /app/reactjs
WORKDIR /app/reactjs
RUN npm ci
RUN npm run webpack

COPY react_vite /app/react_vite
WORKDIR /app/react_vite
RUN npm ci
RUN npm run build
# Remove node_modules to keep the final image small when copying the folder
RUN rm -rf node_modules

# Stage 2: Build python dependencies
# FROM python:3.12-slim-bookworm AS python_builder
# ENV PYTHONUNBUFFERED=1
# RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
#     --mount=type=cache,target=/var/lib/apt,sharing=locked \
#     apt-get update && apt-get -y install --no-install-recommends \
#     build-essential \
#     cmake \
#     # libproj-dev \
#     proj-data proj-bin \
#     # libgdal-dev \
#     # libgeos-dev \
#     default-libmysqlclient-dev \
#     pkg-config
# COPY requirements.txt /
# RUN --mount=type=cache,target=/root/.cache/pip \
#     pip wheel --wheel-dir /wheels cython shapely -r /requirements.txt

# Stage 3: Setup runtime environment
FROM python:3.12-slim-bookworm AS tracker_base
ENV PYTHONUNBUFFERED=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

###### SETUP BASE INFRASTRUCTURE ######
RUN ln -snf /usr/share/zoneinfo/UTC /etc/localtime && echo UTC > /etc/timezone && \
    apt-get update \
    && apt-get -y install --no-install-recommends \
    gdal-bin proj-data proj-bin default-libmysqlclient-dev \
    libcliquer1 libgslcblas0 latexmk texlive \
    texlive-latex-base texlive-latex-extra \
    texlive-latex-recommended ca-certificates gnupg \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system django \
    && adduser --system --ingroup django -u 200 django

###### INSTALL PYTHON PACKAGES ######
COPY requirements.txt /

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install cython shapely default-libmysqlclient-dev pkg-config -r /requirements.txt

###### SETUP APPLICATION INFRASTRUCTURE ######
# TODO: Required for a test, should be changed
COPY documentation /documentation
COPY config /config
COPY --chown=django:django wait-for-it.sh config/gunicorn.sh config/daphne.sh /
RUN chmod 755 /gunicorn.sh /wait-for-it.sh /daphne.sh


###### INSTALL APPLICATION ######
# Copy built assets and source code from builder stage
COPY --chown=django:django src /src
COPY --chown=django:django --from=frontend_builder /app/assets_vite /assets_vite
COPY --chown=django:django --from=frontend_builder /app/assets /assets

# Required for tests
COPY --chown=django:django data /data


RUN mkdir /logs
RUN chown django /logs
WORKDIR /src
# Force font cache generation
RUN python -c "import matplotlib"

# USER django
# RUN python3 manage.py collectstatic --noinput
