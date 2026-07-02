# Почта на своём сервере (volkova.kz)

## Что установлено на 37.140.243.10

- **Postfix** — приём и отправка почты (порты 25, 587)
- **Dovecot** — IMAP с SSL (порт 993)
- **OpenDKIM** — подпись писем (ключ сгенерирован, сервис можно включить позже)

Почтовый сервер: `mail.volkova.kz`

## Ящик по умолчанию

| | |
|---|---|
| Email | `info@volkova.kz` |
| Пароль | `MailVolkova2026!` |
| IMAP | `mail.volkova.kz:993` (SSL) |

Учётные данные на сервере: `/root/mailbox-credentials.txt`

## DNS — обязательно настроить в hoster.kz

**Замените** текущие MX записи Mail.ru на свои:

| Тип | Имя | Значение |
|-----|-----|----------|
| MX | `@` | `10 mail.volkova.kz` |
| A | `mail` | `37.140.243.10` |
| TXT | `@` | `v=spf1 mx a:mail.volkova.kz -all` |
| TXT | `mail._domainkey` | *(см. `/etc/opendkim/keys/volkova.kz/mail.txt` на сервере)* |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:postmaster@volkova.kz` |

Без смены MX письма продолжат идти на Mail.ru, а не на ваш сервер.

## Добавить новый ящик

На сервере:

```bash
ssh root@37.140.243.10
bash /opt/mail_v/deploy/add-mailbox.sh sales MyPassword123
```

## Подключение в Mail V

В веб-интерфейсе http://37.140.243.10/mail/ → **«+ Добавить ящик»**:

| Поле | Значение |
|------|----------|
| IMAP-хост | `mail.volkova.kz` |
| Порт | `993` |
| SSL | да |
| Логин | `info@volkova.kz` |
| Пароль | пароль ящика |
| Папка | `INBOX` |

Ящик `info@volkova.kz` уже добавлен в приложение.

## Проверка

```bash
# Статус сервисов
systemctl status postfix dovecot

# Логи
journalctl -u postfix -f
pm2 logs mail_v

# Тест IMAP
doveadm auth test info@volkova.kz 'пароль'
```

## Важно

1. **PTR (обратная DNS)** — попросите хостера прописать для `37.140.243.10` → `mail.volkova.kz` (иначе письма могут попадать в спам).
2. **Порт 25** — у некоторых VPS заблокирован; проверьте отправку на внешний ящик.
3. Пароль ящика смените: `bash /opt/mail_v/deploy/add-mailbox.sh info НовыйПароль` (пересоздаст с тем же именем — лучше вручную через `doveadm pw`).
