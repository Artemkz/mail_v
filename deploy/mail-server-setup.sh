#!/usr/bin/env bash
# Установка почтового сервера Postfix + Dovecot + OpenDKIM для volkova.kz
set -euo pipefail

DOMAIN="volkova.kz"
MAIL_HOST="mail.volkova.kz"
VMAIL_UID=5000
VMAIL_GID=5000
VMAIL_HOME="/var/mail/vhosts"
DEFAULT_MAILBOX="info@${DOMAIN}"
DEFAULT_PASSWORD="${MAILBOX_PASSWORD:-MailVolkova2026!}"

export DEBIAN_FRONTEND=noninteractive

echo "==> Установка пакетов"
apt-get update -qq
debconf-set-selections <<< "postfix postfix/mailname string ${MAIL_HOST}"
debconf-set-selections <<< "postfix postfix/main_mailer_type string 'Internet Site'"
apt-get install -y -qq postfix dovecot-core dovecot-imapd dovecot-lmtpd \
  opendkim opendkim-tools mailutils certbot

echo "==> Пользователь vmail"
getent group vmail >/dev/null || groupadd -g "${VMAIL_GID}" vmail
id -u vmail >/dev/null 2>&1 || useradd -u "${VMAIL_UID}" -g vmail -d "${VMAIL_HOME}" -m vmail
mkdir -p "${VMAIL_HOME}/${DOMAIN}"
chown -R vmail:vmail "${VMAIL_HOME}"

echo "==> Postfix virtual mailboxes"
cat > /etc/postfix/virtual_domains <<EOF
${DOMAIN} OK
EOF

cat > /etc/postfix/virtual_mailbox <<EOF
${DEFAULT_MAILBOX} ${DOMAIN}/info/
EOF
postmap /etc/postfix/virtual_mailbox

cat > /etc/postfix/main.cf <<EOF
# Основные параметры
smtpd_banner = \$myhostname ESMTP
biff = no
append_dot_mydomain = no
readme_directory = no
compatibility_level = 3.6

myhostname = ${MAIL_HOST}
mydomain = ${DOMAIN}
myorigin = \$mydomain
mydestination = localhost
relayhost =
mynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128
mailbox_size_limit = 0
recipient_delimiter = +
inet_interfaces = all
inet_protocols = ipv4

# Virtual domains
virtual_mailbox_domains = /etc/postfix/virtual_domains
virtual_mailbox_maps = hash:/etc/postfix/virtual_mailbox
virtual_mailbox_base = ${VMAIL_HOME}
virtual_minimum_uid = ${VMAIL_UID}
virtual_uid_maps = static:${VMAIL_UID}
virtual_gid_maps = static:${VMAIL_GID}
virtual_transport = lmtp:unix:private/dovecot-lmtp

# TLS
smtpd_tls_cert_file = /etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem
smtpd_tls_key_file = /etc/letsencrypt/live/${MAIL_HOST}/privkey.pem
smtpd_tls_security_level = may
smtp_tls_security_level = may
smtpd_tls_auth_only = yes

# SASL / restrictions
smtpd_relay_restrictions = permit_mynetworks, permit_sasl_authenticated, defer_unauth_destination
smtpd_recipient_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination
smtpd_helo_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_invalid_helo_hostname, permit

# DKIM
milter_default_action = accept
milter_protocol = 6
smtpd_milters = inet:localhost:8891
non_smtpd_milters = inet:localhost:8891
EOF

cat > /etc/postfix/master.cf <<'EOF'
smtp      inet  n       -       y       -       -       smtpd
submission inet n       -       y       -       -       smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=encrypt
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_recipient_restrictions=permit_sasl_authenticated,reject
  -o milter_macro_daemon_name=ORIGINATING
pickup    unix  n       -       y       60      1       pickup
cleanup   unix  n       -       y       -       0       cleanup
qmgr      unix  n       -       n       300     1       qmgr
tlsmgr    unix  -       -       y       1000?   1       tlsmgr
rewrite   unix  -       -       y       -       -       trivial-rewrite
bounce    unix  -       -       y       -       0       bounce
defer     unix  -       -       y       -       0       bounce
trace     unix  -       -       y       -       0       bounce
verify    unix  -       -       y       -       1       verify
flush     unix  n       -       y       1000?   0       flush
proxymap  unix  -       -       n       -       -       proxymap
proxywrite unix -       -       n       -       1       proxymap
smtp      unix  -       -       y       -       -       smtp
relay     unix  -       -       y       -       -       smtp
showq     unix  n       -       y       -       -       showq
error     unix  -       -       y       -       -       error
retry     unix  -       -       y       -       -       error
discard   unix  -       -       y       -       -       discard
local     unix  -       n       n       -       -       local
virtual   unix  -       n       n       -       -       virtual
lmtp      unix  -       -       y       -       -       lmtp
anvil     unix  -       -       y       -       1       anvil
scache    unix  -       -       y       -       1       scache
dovecot   unix  -       n       n       -       -       pipe
  flags=DRhu user=vmail:vmail argv=/usr/lib/dovecot/deliver -f ${sender} -d ${recipient}
EOF

echo "==> Dovecot"
HASHED_PASS=$(doveadm pw -s SHA512-CRYPT -p "${DEFAULT_PASSWORD}")

mkdir -p "${VMAIL_HOME}/${DOMAIN}/info"
maildirmake.dovecot "${VMAIL_HOME}/${DOMAIN}/info"
chown -R vmail:vmail "${VMAIL_HOME}/${DOMAIN}/info"

cat > /etc/dovecot/users <<EOF
${DEFAULT_MAILBOX}:${HASHED_PASS}:${VMAIL_UID}:${VMAIL_GID}::${VMAIL_HOME}/${DOMAIN}/info::userdb_mail=maildir:${VMAIL_HOME}/${DOMAIN}/info
EOF
chmod 640 /etc/dovecot/users
chown root:dovecot /etc/dovecot/users

cat > /etc/dovecot/dovecot.conf <<'EOF'
protocols = imap lmtp
listen = *, ::
!include conf.d/*.conf
!include_try local.conf
EOF

cat > /etc/dovecot/conf.d/10-mail.conf <<'EOF'
mail_location = maildir:~/Maildir
mail_privileged_group = mail
namespace inbox {
  inbox = yes
}
EOF

cat > /etc/dovecot/conf.d/10-auth.conf <<'EOF'
disable_plaintext_auth = yes
auth_mechanisms = plain login

passdb {
  driver = passwd-file
  args = scheme=SHA512-CRYPT username_format=%u /etc/dovecot/users
}

userdb {
  driver = passwd-file
  args = username_format=%u /etc/dovecot/users
}
EOF

cat > /etc/dovecot/conf.d/10-master.conf <<'EOF'
service imap-login {
  inet_listener imap {
    port = 0
  }
  inet_listener imaps {
    port = 993
    ssl = yes
  }
}

service lmtp {
  unix_listener /var/spool/postfix/private/dovecot-lmtp {
    mode = 0600
    user = postfix
    group = postfix
  }
}

service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0666
    user = postfix
    group = postfix
  }
}
EOF

cat > /etc/dovecot/conf.d/10-ssl.conf <<EOF
ssl = required
ssl_cert = </etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem
ssl_key = </etc/letsencrypt/live/${MAIL_HOST}/privkey.pem
ssl_min_protocol = TLSv1.2
EOF

echo "==> OpenDKIM"
mkdir -p /etc/opendkim/keys/${DOMAIN}
opendkim-genkey -b 2048 -d ${DOMAIN} -D /etc/opendkim/keys/${DOMAIN} -s mail -v
chown -R opendkim:opendkim /etc/opendkim

cat > /etc/opendkim.conf <<EOF
Syslog yes
UMask 002
Canonicalization relaxed/simple
Mode sv
SubDomains no
AutoRestart yes
AutoRestartRate 10/1M
Background yes
DNSTimeout 5
SignatureAlgorithm rsa-sha256

Domain ${DOMAIN}
KeyFile /etc/opendkim/keys/${DOMAIN}/mail.private
Selector mail
Socket inet:8891@localhost

InternalHosts /etc/opendkim/TrustedHosts
KeyTable /etc/opendkim/KeyTable
SigningTable refile:/etc/opendkim/SigningTable
EOF

cat > /etc/opendkim/TrustedHosts <<EOF
127.0.0.1
localhost
${MAIL_HOST}
.${DOMAIN}
EOF

echo "mail._domainkey.${DOMAIN} ${DOMAIN}:mail:/etc/opendkim/keys/${DOMAIN}/mail.private" > /etc/opendkim/KeyTable
echo "*@${DOMAIN} mail._domainkey.${DOMAIN}" > /etc/opendkim/SigningTable

echo "==> SSL сертификат"
if [ ! -f "/etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem" ]; then
  certbot certonly --nginx -d "${MAIL_HOST}" --non-interactive --agree-tos -m ${DEFAULT_MAILBOX} --redirect || \
  certbot certonly --standalone -d "${MAIL_HOST}" --non-interactive --agree-tos -m ${DEFAULT_MAILBOX} --preferred-challenges http || true
fi

if [ ! -f "/etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem" ]; then
  echo "WARN: SSL не получен, используем snakeoil временно"
  mkdir -p /etc/letsencrypt/live/${MAIL_HOST}
  cp /etc/ssl/certs/ssl-cert-snakeoil.pem /etc/letsencrypt/live/${MAIL_HOST}/fullchain.pem
  cp /etc/ssl/private/ssl-cert-snakeoil.key /etc/letsencrypt/live/${MAIL_HOST}/privkey.pem
fi

echo "==> Запуск сервисов"
systemctl enable postfix dovecot opendkim
systemctl restart opendkim postfix dovecot

# Сохранить учётные данные
cat > /root/mailbox-credentials.txt <<EOF
Домен: ${DOMAIN}
Почтовый сервер: ${MAIL_HOST}
IMAP: ${MAIL_HOST}:993 (SSL)

Ящик: ${DEFAULT_MAILBOX}
Пароль: ${DEFAULT_PASSWORD}

DNS записи (настроить в hoster.kz):
MX   @    10 mail.volkova.kz
A    mail 37.140.243.10
TXT  @    v=spf1 mx a:mail.volkova.kz -all
TXT  mail._domainkey  $(cat /etc/opendkim/keys/${DOMAIN}/mail.txt | tr -d '\n' | sed 's/.*( "//;s/").*//')
TXT  _dmarc  v=DMARC1; p=none; rua=mailto:postmaster@${DOMAIN}

DKIM (полная запись):
$(cat /etc/opendkim/keys/${DOMAIN}/mail.txt)
EOF
chmod 600 /root/mailbox-credentials.txt

echo "==> Готово"
cat /root/mailbox-credentials.txt
