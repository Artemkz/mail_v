#!/usr/bin/env bash
# Добавить почтовый ящик на сервере
# Использование: add-mailbox.sh <local-part> <password> [domain]
set -euo pipefail

DOMAIN="${3:-volkova.kz}"
VMAIL_HOME="/var/mail/vhosts"
VMAIL_UID=5000
VMAIL_GID=5000

if [ $# -lt 2 ]; then
  echo "Использование: $0 <local-part> <password> [domain]"
  echo "Примеры:"
  echo "  $0 info MyPass123 volkov.kz"
  echo "  $0 sales MyPass123 volkova.kz"
  exit 1
fi

LOCAL="$1"
PASSWORD="$2"
EMAIL="${LOCAL}@${DOMAIN}"

if grep -q "^${EMAIL} " /etc/postfix/virtual_mailbox 2>/dev/null; then
  echo "Ошибка: ящик ${EMAIL} уже существует"
  exit 1
fi

grep -q "^${DOMAIN} OK" /etc/postfix/virtual_domains 2>/dev/null || echo "${DOMAIN} OK" >> /etc/postfix/virtual_domains

HASHED_PASS=$(doveadm pw -s SHA512-CRYPT -p "${PASSWORD}")

mkdir -p "${VMAIL_HOME}/${DOMAIN}/${LOCAL}"
maildirmake.dovecot "${VMAIL_HOME}/${DOMAIN}/${LOCAL}"
chown -R vmail:vmail "${VMAIL_HOME}/${DOMAIN}/${LOCAL}"

echo "${EMAIL} ${DOMAIN}/${LOCAL}/" >> /etc/postfix/virtual_mailbox
postmap /etc/postfix/virtual_mailbox

echo "${EMAIL}:${HASHED_PASS}:${VMAIL_UID}:${VMAIL_GID}::${VMAIL_HOME}/${DOMAIN}/${LOCAL}::userdb_mail=maildir:${VMAIL_HOME}/${DOMAIN}/${LOCAL}" >> /etc/dovecot/users

systemctl reload postfix dovecot
echo "Создан ящик: ${EMAIL}"
