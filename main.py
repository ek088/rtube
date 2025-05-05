import argparse
import logging
import time
import sys
import threading
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException

# Настройка логирования
# Используем базовую настройку, чтобы получить стандартный консольный обработчик
# Затем добавим файловый обработчик для ошибок
logging.basicConfig(
    level=logging.INFO, # Общий минимальный уровень для логгера и консоли
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Создаем файловый обработчик для ошибок
error_file_handler = logging.FileHandler('logs.txt', encoding='utf-8')
error_file_handler.setLevel(logging.ERROR) # Устанавливаем уровень для файла
error_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')) # Формат для файла (можно сделать другим)

# Получаем корневой логгер и добавляем файловый обработчик
root_logger = logging.getLogger()
root_logger.addHandler(error_file_handler)

# Список для хранения всех активных драйверов
active_drivers = []

class BrowserWatcher(threading.Thread):
    """
    Поток, управляющий одним окном браузера и его циклом обновления.
    """
    def __init__(self, url_list, refresh_interval, window_size, is_headless, thread_id):
        threading.Thread.__init__(self)
        self.url_list = url_list
        self.refresh_interval = refresh_interval
        self.window_size = window_size
        self.is_headless = is_headless
        self.thread_id = thread_id
        self.driver = None
        self._stop_event = threading.Event()
        self.current_url_index = 0
        # Логгер для потока (добавляем имя потока в лог)
        self.logger = logging.getLogger(f'Thread-{self.thread_id}')


    def run(self):
        """Метод, выполняемый при запуске потока."""
        self.logger.info("Поток стартовал.")

        try:
            self.driver = setup_driver(self.window_size, self.is_headless)
            active_drivers.append(self.driver)
            self.logger.info(f"Драйвер инициализирован (headless: {self.is_headless}).")

            if not self.url_list:
                self.logger.warning("Список ссылок пуст.")
                return

            initial_url = self.url_list[self.current_url_index]
            self.driver.get(initial_url)
            self.logger.info(f"Открыта начальная ссылка: {initial_url}")

            while not self._stop_event.is_set():
                self.current_url_index = (self.current_url_index + 1) % len(self.url_list)
                next_url = self.url_list[self.current_url_index]

                try:
                    if self._stop_event.wait(self.refresh_interval):
                        self.logger.info("Получен сигнал остановки, завершение ожидания.")
                        break

                    self.driver.get(next_url)
                    self.logger.info(f"Обновлено, перешли на ссылку: {next_url}")

                except WebDriverException as e:
                    self.logger.error(f"Ошибка Selenium при обновлении на {next_url}: {e}")
                    self.logger.warning("Завершение работы из-за ошибки Selenium.")
                    break
                except Exception as e:
                    self.logger.error(f"Непредвиденная ошибка: {e}")
                    self.logger.warning("Завершение работы из-за непредвиденной ошибки.")
                    break

        except Exception as e:
            self.logger.error(f"Ошибка при инициализации драйвера или первой загрузке: {e}")

        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    self.logger.info("Драйвер закрыт.")
                    if self.driver in active_drivers:
                         active_drivers.remove(self.driver)
                except Exception as e:
                    self.logger.error(f"Ошибка при закрытии драйвера: {e}")

            self.logger.info("Поток завершен.")

    def stop(self):
        self.logger.info("Получен запрос на остановку.")
        self._stop_event.set()


def read_urls_from_file(filepath):
    """Читает список URL из файла."""
    urls = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:
                    urls.append(url)
    except FileNotFoundError:
        logging.error(f"Файл с ссылками не найден: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Ошибка при чтении файла с ссылками {filepath}: {e}")
        sys.exit(1)
    return urls

def setup_driver(window_size, is_headless):
    """Настраивает и возвращает экземпляр ChromeDriver."""
    options = Options()
    if is_headless:
        options.add_argument("--headless=new")
        # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")

    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        raise e

def watch_urls(urls, num_windows, refresh_interval, window_size, is_headless):
    """Запускает просмотр URL в нескольких окнах с обновлением, используя потоки."""
    if not urls:
        logging.warning("Нет ссылок для просмотра.")
        return

    if len(urls) == 0:
        logging.warning("Нет доступных ссылок для открытия окон.")
        return

    threads = []
    logging.info(f"Создание {num_windows} потоков для просмотра {len(urls)} ссылок.")

    for i in range(num_windows):
        thread = BrowserWatcher(urls, refresh_interval, window_size, is_headless, thread_id=i)
        threads.append(thread)
        thread.start()
        time.sleep(2)

    logging.info("Все потоки запущены.")
    if is_headless:
        logging.info("Браузеры работают в headless режиме (без видимых окон).")
    else:
        logging.info("Браузеры работают в видимом режиме.")


    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logging.info("Получен сигнал прерывания (Ctrl+C). Инициирую завершение потоков.")
        for thread in threads:
            thread.stop()

        logging.info("Ожидание завершения потоков...")
        for thread in threads:
             thread.join()

    finally:
        logging.info("Закрытие оставшихся драйверов.")
        for driver in list(active_drivers):
            try:
                driver.quit()
                if driver in active_drivers:
                     active_drivers.remove(driver)
            except Exception as e:
                logging.error(f"Ошибка при закрытии драйвера в finally блоке: {e}")

        logging.info("Программа завершена.")


def main():
    """Основная функция для парсинга аргументов и запуска просмотра."""
    parser = argparse.ArgumentParser(description='Программа для просмотра веб-страниц в нескольких окнах с обновлением.')
    parser.add_argument(
        '-w', '--windows',
        type=int,
        default=4,
        help='Количество окон для просмотра (по умолчанию: 4)'
    )
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=3,
        help='Интервал обновления страниц в секундах (по умолчанию: 3)'
    )
    parser.add_argument(
        '-s', '--size',
        type=str,
        default='350x350',
        help='Размер окна браузера в формате ШИРИНАxВЫСОТА (по умолчанию: 350x350)'
    )
    parser.add_argument(
        'urls_file',
        type=str,
        help='Путь к файлу, содержащему список URL (одна ссылка на строку)'
    )
    parser.add_argument(
        '-H', '--headless',
        action='store_true',
        help='Запустить браузеры в headless режиме (без видимого окна).'
    )


    args = parser.parse_args()

    try:
        width, height = map(int, args.size.split('x'))
        window_size = (width, height)
    except ValueError:
        logging.error(f"Неверный формат размера окна: {args.size}. Используйте формат ШИРИНАxВЫСОТА (например, 800x600).")
        sys.exit(1)

    logging.info(f"Чтение ссылок из файла: {args.urls_file}")
    urls = read_urls_from_file(args.urls_file)

    logging.info(f"Параметры запуска: Windows={args.windows}, Interval={args.interval}, Size={args.size}, Headless={args.headless}")

    watch_urls(urls, args.windows, args.interval, window_size, args.headless)

if __name__ == "__main__":
    main()
