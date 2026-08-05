# ExamSL

Внутренняя Django‑система для менеджеров: экзамены, клиенты, комментарии, быстрый поиск и браузерные FCM‑уведомления. Интерфейс и расписание работают в часовом поясе `Asia/Ashgabat`.

## Быстрый запуск

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Откройте `http://127.0.0.1:8000/`. Обычный менеджер может самостоятельно зарегистрироваться на `/register/`.

## Firebase Cloud Messaging

Для серверной отправки нужен **JSON‑ключ service account**:

1. Firebase Console → Project settings → Service accounts.
2. Нажмите **Generate new private key**.
3. Сохраните скачанный файл в корне проекта как `firebase-service-account.json`.
4. Не добавляйте его в Git — имя уже внесено в `.gitignore`.

Для регистрации web push также нужен публичный Web Push certificate key: Firebase Console → Project settings → Cloud Messaging → Web Push certificates → Generate key pair. Скопируйте открытый ключ в `.env`:

```env
FIREBASE_CREDENTIALS=./firebase-service-account.json
FIREBASE_LEGACY_CREDENTIALS=./firebase-service-account-legacy.json
FCM_VAPID_PUBLIC_KEY=ваш_публичный_vapid_key
```

Web push работает только по HTTPS, исключение — локальный `localhost`/`127.0.0.1`.

`FIREBASE_CREDENTIALS` — основной проект для новых web-токенов. `FIREBASE_LEGACY_CREDENTIALS`
можно указать на время миграции: если старый токен не подходит основному проекту, ExamSL попробует
отправить его через legacy service account.

## Students Life API

Заполните один из вариантов доступа к пользователям/профилям и Bearer для токенов:

```env
STUDENTSLIFE_API_KEY=service_key
STUDENTSLIFE_BEARER_TOKEN=manager_or_admin_jwt
STUDENTSLIFE_REFRESH_TOKEN=manager_or_admin_refresh_jwt
STUDENTSLIFE_TOKEN_FILE=./studentslife-token.json
SITE_URL=https://exam.example.com
```

- Если рядом лежит локальный `studentslife-token.json`, созданный `studentslife-auth.ps1`, ExamSL берёт `access` и `refresh` оттуда. Файл содержит секреты, исключён из Git и не должен передаваться вместе с исходным кодом или пакетами выпуска. При ответе `401` приложение само вызывает `/auth/refresh/`, сохраняет новый `access` в локальный файл и повторяет запрос.
- `refresh` нельзя использовать как Bearer для обычных API. Bearer всегда должен быть `access`, а `refresh` нужен только для `/auth/refresh/`.
- `X-API-KEY` используется как запасной вариант для поиска пользователей и профилей, если Bearer не задан.
- Для тестового push конкретному клиенту API токенов должен возвращать связь с владельцем как `user`, `user_id` или `owner`. Если serializer отдаёт только `token/platform/device_id`, сервер API нужно расширить либо добавить endpoint фильтрации `?user=<id>`.

Если FCM пишет `SenderIdMismatch`, токен был создан другим Firebase проектом или другим Web Push certificate/VAPID. Нужно очистить разрешение уведомлений в браузере и заново подключить push с текущими `FIREBASE_*` и `FCM_VAPID_PUBLIC_KEY`.

`firebase-service-account.json`, `FIREBASE_PROJECT_ID`, `FIREBASE_MESSAGING_SENDER_ID` и `FCM_VAPID_PUBLIC_KEY` должны быть из одного Firebase проекта. Если JSON скачан из другого проекта, ExamSL остановит отправку с понятной ошибкой конфигурации.

## Автоматические уведомления

Каждый активный экзамен получает три фиксированных слота: на предыдущий день в `08:00` и `20:00`, а также за `30 минут` до начала. Если заполнено «Дополнительное время уведомления», создаётся ещё один произвольный слот. Пустой список получателей означает всех активных локальных менеджеров. На странице уведомлений тестовый push можно отправить себе либо выбранным менеджерам.

Для разработки запустите worker во втором терминале:

```powershell
python manage.py run_notification_worker
```

Для production предпочтительно запускать одноразовую команду каждую минуту через cron/systemd timer/планировщик:

```powershell
python manage.py process_notifications
```

Worker идемпотентен: уникальный журнал предотвращает повторную отправку одного слота одному менеджеру.

## Проверка

```powershell
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```

## Важное о паролях клиентов

По заданию пароль клиента отображается открыто в интерфейсе и сейчас хранится в базе как текст. Ограничьте доступ к ExamSL доверенными менеджерами, используйте HTTPS и защищённые резервные копии. Для публичного развёртывания рекомендуется добавить шифрование поля на уровне приложения/KMS.
