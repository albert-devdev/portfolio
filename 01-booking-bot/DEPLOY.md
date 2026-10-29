# Запуск бота для клиента на сервере

Чтобы бот работал круглосуточно, ему нужен сервер (VPS): это компьютер в дата-центре, который не выключается.
Подойдёт самый дешёвый тариф с Ubuntu 22.04 или 24.04 у любого российского хостинга (Timeweb Cloud, Beget, Selectel и т.п.).
Обычно это 150–300 ₽ в месяц. Сервер оформляет и оплачивает **клиент на себя**, а вам даёт доступ.

## 1. Что взять у клиента
- Название, адрес, телефон.
- Мастера: имя и пара слов о каждом.
- Услуги с ценами.
- Часы работы и на сколько дней вперёд открыта запись.
- Токен бота. Клиент создаёт бота сам в @BotFather (команда `/newbot`) и присылает токен. Так бот с первого дня принадлежит ему.
- Telegram ID администратора: администратор пишет @userinfobot, и тот показывает число.

## 2. Настроить под клиента (на своём компьютере)
1. Скопируйте `business.example.json` в `business.json` и впишите данные клиента.
   Ключи мастеров и услуг (`anna`, `mani`) должны быть латиницей, без пробелов.
2. Проверьте, что файл читается:
   ```bash
   python -c "import config; print(config.BUSINESS_NAME, list(config.SERVICES))"
   ```

## 3. Залить на сервер
Подключитесь к серверу (`ssh root@IP_сервера`, пароль хостинг пришлёт на почту клиента) и выполните:
```bash
apt update && apt install -y python3-venv git
git clone https://github.com/albert-devdev/portfolio.git /opt/src
cp -r /opt/src/01-booking-bot /opt/bot && rm -rf /opt/src
cd /opt/bot && python3 -m venv venv && venv/bin/pip install -r requirements.txt
```
С вашего компьютера скопируйте настройки клиента:
```bash
scp business.json root@IP_сервера:/opt/bot/
```
На сервере создайте `/opt/bot/.env`: `nano /opt/bot/.env`
```
BOT_TOKEN=токен_клиента
ADMIN_ID=id_администратора
```
На зарубежном сервере или на сервере с доступом к Telegram строку PROXY не пишем.

## 4. Автозапуск
Создайте службу: `nano /etc/systemd/system/bot.service`
```ini
[Unit]
Description=Telegram booking bot
After=network-online.target

[Service]
WorkingDirectory=/opt/bot
ExecStart=/opt/bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Включите её:
```bash
systemctl daemon-reload && systemctl enable --now bot
systemctl status bot          # должно быть active (running)
journalctl -u bot -f          # логи в реальном времени, выход: Ctrl+C
```
Бот сам поднимется после перезагрузки сервера или падения.

## 5. Сдать работу
1. Сделайте тестовую запись с телефона.
2. Убедитесь, что администратору пришло уведомление.
3. Откройте `/admin` от имени администратора и проверьте, что меню работает.
4. Отмените тестовую запись.
5. Дайте клиенту ссылку на бота `t.me/имя_бота`. Её можно добавить в шапку Инстаграма, в Яндекс Карты и 2ГИС.

## Изменить цены или мастеров потом
```bash
nano /opt/bot/business.json
systemctl restart bot
```

## Резервная копия записей
Все записи хранятся в одном файле `/opt/bot/bookings.db`. Чтобы скачать его к себе:
```bash
scp root@IP_сервера:/opt/bot/bookings.db .
```
