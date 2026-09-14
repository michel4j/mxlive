FROM python:3.13-alpine

MAINTAINER Kathryn Janzen <kathryn.janzen@lightsource.ca>

ADD . /mxlive

RUN apk add --no-cache --virtual .build-deps bash gcc linux-headers musl-dev postgresql-dev libpq libffi-dev \
    apache2-ssl apache2-mod-wsgi certbot-apache openssl openssl-dev python3-dev xvfb-run wkhtmltopdf

RUN set -ex && /usr/bin/pip3 install --upgrade pip && /usr/bin/pip3 install --no-cache-dir -r /requirements.txt


COPY deploy/run-server.sh /run-server.sh
COPY deploy/wait-for-it.sh /wait-for-it.sh
RUN chmod -v +x /run-server.sh /wait-for-it.sh

COPY deploy/mxlive.conf /etc/apache2/conf.d/zzzmxlive.conf

RUN /usr/bin/python3 /mxlive/manage.py collectassets --noinput
RUN /usr/bin/python3 /mxlive/manage.py collectstatic --noinput

CMD /run-server.sh


# =========================================================
# STAGE 1: The Builder (Heavy, contains compilers and source code)
# =========================================================
FROM python:3.13-slim AS builder
ENV DEBIAN_FRONTEND=noninteractive
COPY pyproject.toml /
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    unzip \
    tar

# Build  virtual environment
RUN python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip uv && \
    UV_PROJECT_ENVIRONMENT=/venv  /venv/bin/uv sync

# =========================================================
# STAGE 2: The Final Runtime (Lean, clean, and fast)
# =========================================================
FROM python:3.13-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    apache2 \
    libapache2-mod-wsgi-py3 \
    && rm -rf /var/lib/apt/lists/*

# Pluck ONLY the finished, compiled work straight out of Stage 1
COPY --from=builder /venv /venv
COPY --from=builder /usr/local/lib/ /usr/local/lib/

# Add package and utility scripts
COPY . /mxlive
COPY deploy/run-server.sh /run-server.sh
COPY deploy/wait-for-it.sh /wait-for-it.sh


# Post-installation configurations and directory setup
RUN mkdir -p /mxlive/local && \
    chmod +x /run-server.sh /wait-for-it.sh && \
    # Clear default Debian site config and link your custom config
    rm -f /etc/apache2/sites-enabled/000-default.conf && \
    cp /mxlive/deploy/mxlive.conf /etc/apache2/sites-enabled/ && \
    # Adjust shebang in management script to point to the venv
    sed -i -E 's@#!/usr/bin/env python.*@#!/venv/bin/python3@' /mxlive/manage.py

# Run framework tasks and redirect logs to console
RUN /venv/bin/python3 /mxlive/manage.py collectassets --noinput && \
    /venv/bin/python3 /mxlive/manage.py collectstatic --noinput && \
    rm -rf /mxlive/deploy && \
    ln -sf /proc/self/fd/1 /var/log/apache2/access.log && \
    ln -sf /proc/self/fd/2 /var/log/apache2/error.log

EXPOSE 80
VOLUME ["/users", "/archive", "/cache"]
CMD ["/run-server.sh"]
