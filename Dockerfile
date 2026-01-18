# Stage 1: Build frontend assets
FROM node:24-bookworm-slim AS frontend_builder
RUN apt update && apt install -y curl bash
COPY src /app/src

WORKDIR /app/src/static/css
RUN curl -sL daisyui.com/fast | bash

COPY react_vite /app/react_vite
WORKDIR /app/react_vite
RUN --mount=type=cache,target=/root/.npm npm ci
RUN npm run build

# Install tailwind and DaisyUI and build CSS
COPY src /app/src
COPY tailwind.config.js /app/
COPY package.json package-lock.json /app/
WORKDIR /app
RUN npm ci
WORKDIR /app/
RUN src/static/css/tailwindcss -i src/static/css/input.css -o src/static/css/output.css --minify

# Stage 2: Build python dependencies
FROM python:3.12-slim-bookworm AS python_builder
ENV PYTHONUNBUFFERED=1
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get -y install --no-install-recommends \
    build-essential \
    cmake \
    git \
    # libproj-dev \
    proj-data proj-bin \
    # libgdal-dev \
    # libgeos-dev \
    default-libmysqlclient-dev \
    pkg-config
COPY requirements.txt /
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir /wheels cython shapely -r /requirements.txt

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
    texlive-latex-base texlive-latex-extra lmodern  \
    texlive-latex-recommended ca-certificates gnupg \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system django \
    && adduser --system --ingroup django -u 200 django

###### INSTALL PYTHON PACKAGES ######
COPY --from=python_builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels
        
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
COPY --chown=django:django --from=frontend_builder /app/react_vite /react_vite
COPY --chown=django:django --from=frontend_builder /app/src/static/css/output.css /src/static/css

# Required for tests
COPY --chown=django:django data /data
WORKDIR /src



RUN mkdir /logs
RUN chown django /logs
WORKDIR /src
# Force font cache generation
RUN python -c "import matplotlib"

# USER django
# RUN python3 manage.py collectstatic --noinput
