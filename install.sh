#!/bin/bash

# Скрипт для установки и настройки rtube на Ubuntu

# Функция для проверки успешности выполнения команды
check_command() {
    if [ $? -ne 0 ]; then
        echo "Ошибка: Команда '$1' не выполнилась успешно. Скрипт прерван."
        exit 1
    fi
}

echo "Начинаем установку и настройку rtube..."

# 1. Обновление списка пакетов и обновление установленных пакетов
echo "Выполняем обновление системы..."
sudo apt update
check_command "sudo apt update"
sudo apt upgrade -y
check_command "sudo apt upgrade"

# 2. Установка uv
echo "Устанавливаем uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
check_command "curl -LsSf https://astral.sh/uv/install.sh | sh"

# 3. Источник переменных окружения uv (для текущей сессии скрипта)
# Этот шаг нужен, чтобы скрипт мог найти команду uv.
# В дальнейшем, после перезагрузки или открытия новой сессии,
# переменные окружения будут установлены автоматически при входе.
echo "Обновляем переменные окружения для uv..."
source "$HOME/.local/bin/env"
# Проверяем, доступна ли команда uv
if ! command -v uv &> /dev/null; then
    echo "Ошибка: Команда uv не найдена после установки и sourcing."
    echo "Возможно, путь $HOME/.local/bin не добавлен в вашу переменную PATH."
    exit 1
fi

# 4. Клонирование репозитория rtube
echo "Клонируем репозиторий rtube..."
# Проверяем, существует ли уже директория rtube, и удаляем ее, если да, чтобы избежать ошибок при клонировании.
if [ -d "rtube" ]; then
    echo "Директория rtube уже существует. Удаляем ее перед клонированием."
    rm -rf rtube
    check_command "удаление существующей директории rtube"
fi
git clone https://github.com/ek088/rtube
check_command "git clone https://github.com/ek088/rtube"

# 5. Переход в директорию rtube
echo "Переходим в директорию rtube..."
cd rtube
check_command "cd rtube"

# 6. Синхронизация зависимостей с помощью uv
echo "Синхронизируем зависимости с помощью uv..."
# Убедимся, что uv используется из правильного пути
"$HOME/.local/bin/uv" sync
check_command "uv sync"

# 7. Установка Playwright браузера (Chrome)
echo "Устанавливаем браузер Chrome для Playwright..."
# Используем python из виртуального окружения, созданного uv
"$HOME/rtube/.venv/bin/python" -m playwright install chrome
check_command "playwright install chrome"

# 8. Создание сервиса systemd для rtube
echo "Создаем сервис systemd для rtube..."
SERVICE_FILE="/etc/systemd/system/rtube.service"

# Проверяем, существует ли файл сервиса, и удаляем его, если да, чтобы избежать дублирования
if [ -f "$SERVICE_FILE" ]; then
    echo "Файл сервиса $SERVICE_FILE уже существует. Удаляем его перед созданием."
    sudo rm "$SERVICE_FILE"
    check_command "удаление существующего файла сервиса"
fi

sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=rtube
After=network.target

[Service]
ExecStart=/root/rtube/.venv/bin/python /root/rtube/main.py -w 12 -i 6 -H --size=600x600 links
Restart=on-failure
User=root
WorkingDirectory=/root/rtube
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
EOF
check_command "создание файла сервиса systemd"

# 9. Перезагрузка демона systemd
echo "Перезагружаем демон systemd..."
sudo systemctl daemon-reload
check_command "sudo systemctl daemon-reload"

# Запускаем сервис в первый раз
echo "Запускаем сервис rtube..."
sudo systemctl start rtube.service
check_command "sudo systemctl start rtube.service"

# Проверяем статус сервиса
echo "Проверяем статус сервиса rtube..."
sudo systemctl status rtube.service

# 10. Добавление задания в crontab для перезапуска сервиса каждые 5 часов
echo "Добавляем задание в crontab для перезапуска сервиса каждые 5 часов..."
# Используем crontab -l для получения текущего расписания, добавляем новую строку и записываем обратно
(sudo crontab -l 2>/dev/null; echo "0 */5 * * * systemctl restart rtube.service") | sudo crontab -
check_command "добавление задания в crontab"

echo "Установка и настройка rtube завершена успешно!"
echo "Сервис rtube запущен и настроен на перезапуск каждые 5 часов через Cron."

