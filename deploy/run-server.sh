#!/bin/bash

set -ex
APP_DIRECTORY="/mxlive"
export SERVER_NAME=${SERVER_NAME:-$(hostname -f)}

# Wait for Database
/wait-for-it.sh database:5432 -t 60

# Clear runtime contexts
rm -rf /var/run/apache2/* /tmp/apache2*


# create key if none present
CERT_KEY=${CERT_PATH}/privkey.pem
if [ ! -f $CERT_KEY ]; then
    export CERT_PATH = '/certs'
    CERT_KEY=${CERT_PATH}/privkey.pem
    mkdir -p ${CERT_PATH}
    openssl req -x509 -nodes -newkey rsa:2048 -keyout ${CERT_KEY} -out ${CERT_PATH}/fullchain.pem -subj '/CN=${SERVER_NAME}'
fi


# Make sure the local directory is a Python package
if [ ! -f ${APP_DIRECTORY}/local/__init__.py ]; then
    touch ${APP_DIRECTORY}/local/__init__.py
fi

# Modify the 'www-data' user (Debian)
if [ -z "$APACHE_UID" ]; then
    echo "Default Apache UID will be used!"
else
    usermod --non-unique --uid "${APACHE_UID}" www-data
fi

# check of database exists and initialize it if not
for trial in {1..5}; do
    echo "Migrating database tables ... (attempt $trial)"
    /venv/bin/python3 ${APP_DIRECTORY}/manage.py migrate --noinput && break
    sleep 5
done

# Initialize Media Directory
MEDIA_ROOT="${APP_DIRECTORY}/local/media"
if [ ! -d "${MEDIA_ROOT}" ]; then
  mkdir -p "${MEDIA_ROOT}"
fi

# Update ownership to 'www-data' (Debian)
if [ ! -f "${MEDIA_ROOT}/.init" ]; then
    chown -R www-data:www-data "${MEDIA_ROOT}"
    touch "${MEDIA_ROOT}/.init"
fi

# Create log directory if missing
LOG_DIRECTORY="${APP_DIRECTORY}/local/logs"
if [ ! -d "${LOG_DIRECTORY}" ]; then
    mkdir -p "${LOG_DIRECTORY}"
fi

# Launch Debian's apache2 binary using its standard environment variables
# Debian's Apache requires variables like APACHE_RUN_DIR to be sourced first.
source /etc/apache2/envvars
exec /usr/sbin/apache2 -DFOREGROUND -e debug

