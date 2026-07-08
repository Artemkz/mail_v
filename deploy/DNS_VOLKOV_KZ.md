# DNS для доставки на Gmail (домен volkov.kz)

Настройте в панели **hoster.kz** для домена **volkov.kz**.

## 1. SPF (обязательно)

| Тип | Имя | Значение |
|-----|-----|----------|
| TXT | `@` | `v=spf1 mx a:mail.volkova.kz ip4:37.140.243.10 ~all` |

Если запись `@` TXT уже есть — **удалите** старую и добавьте эту.

## 2. DKIM (обязательно)

| Тип | Имя | Значение |
|-----|-----|----------|
| TXT | `mail._domainkey` | см. `/etc/opendkim/keys/volkov.kz/mail.txt` на сервере |

**Удалите** текущую сломанную запись `mail._domainkey` (там только фрагмент ключа без `v=DKIM1`).

Получить правильное значение на сервере:

```bash
ssh root@37.140.243.10
grep -o '"[^"]*"' /etc/opendkim/keys/volkov.kz/mail.txt | tr -d '"' | tr -d '\n' | fold -w 0
# или: cat /etc/opendkim/keys/volkov.kz/mail.txt
```

## 3. DMARC (рекомендуется)

| Тип | Имя | Значение |
|-----|-----|----------|
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:postmaster@volkov.kz` |

## 4. MX (должен быть)

| Тип | Имя | Значение | Приоритет |
|-----|-----|----------|-----------|
| MX | `@` | `mail.volkov.kz` | 10 |
| A | `mail` | `37.140.243.10` | — |

## 5. PTR (у хостера VPS)

Попросите провайдера VPS: **37.140.243.10** → `mail.volkova.kz`

## Проверка после изменений (15–60 мин)

- https://mxtoolbox.com/SuperTool.aspx — SPF, DKIM, MX
- https://www.mail-tester.com — отправьте письмо на указанный адрес

## На сервере уже исправлено

- OpenDKIM включён и подписывает письма `@volkov.kz`
- Postfix передаёт исходящие письма через DKIM
