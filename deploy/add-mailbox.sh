#!/usr/bin/env bash
# Добавить почтовый ящик на сервере
set -euo pipefail

DOMAIN="volkova.kz"
VMAIL_HOME="/var/mail/vhosts"
VMAIL_UID=5000
VMAIL_GID=5000

if [ $# -lt 2 ]; then
  echo "Использование: $0 <local-part> <password>"
  echo "Пример: $0 sales MySecurePass123"
  exit 1
fi

LOCAL="$1"
PASSWORD="$2"
EMAIL="${LOCAL}@${DOMAIN}"

HASHED_PASS=$(doveadm pw -s SHA512-CRYPT -p "${PASSWORD}")

mkdir -p "${VMAIL_HOME}/${DOMAIN}/${LOCAL}"
maildirmake.dovecot "${VMAIL_HOME}/${DOMAIN}/${LOCAL}"
chown -R vmail:vmail "${VMAIL_HOME}/${DOMAIN}/${LOCAL}"

echo "${EMAIL} ${DOMAIN}/${LOCAL}/" >> /etc/postfix/virtual_mailbox
postmap /etc/postfix/virtual_mailbox

echo "${EMAIL}:${HASHED_PASS}:${VMAIL_UID}:${VMAIL_GID}::${VMAIL_HOME}/${DOMAIN}/${LOCAL}::userdb_mail=maildir:${VMAIL_HOME}/${DOMAIN}/${LOCAL}" >> /etc/dovecot/users

systemctl reload postfix dovecot
echo "Создан ящик: ${EMAIL}"
