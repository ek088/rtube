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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        self.is_headless = is_headless # Сохраняем состояние headless
        self.thread_id = thread_id
        self.driver = None
        self._stop_event = threading.Event()
        self.current_url_index = 0

    def run(self):
        """Метод, выполняемый при запуске потока."""
        logging.info(f"Поток {self.thread_id} стартовал.")

        try:
            # Инициализация драйвера для этого потока, передавая состояние headless
            self.driver = setup_driver(self.window_size, self.is_headless)
            active_drivers.append(self.driver)
            logging.info(f"Поток {self.thread_id}: Драйвер инициализирован (headless: {self.is_headless}).")

            # Открываем первую ссылку
            if not self.url_list:
                logging.warning(f"Поток {self.thread_id}: Список ссылок пуст.")
                return # Завершаем поток, если нет ссылок

            initial_url = self.url_list[self.current_url_index]
            self.driver.get(initial_url)
            logging.info(f"Поток {self.thread_id}: Открыта начальная ссылка: {initial_url}")

            # Основной цикл обновления
            while not self._stop_event.is_set():
                # Переходим к следующей ссылке
                self.current_url_index = (self.current_url_index + 1) % len(self.url_list)
                next_url = self.url_list[self.current_url_index]

                try:
                    # Задержка перед обновлением
                    if self._stop_event.wait(self.refresh_interval):
                        logging.info(f"Поток {self.thread_id}: Получен сигнал остановки, завершение ожидания.")
                        break # Выходим из цикла

                    # Выполняем обновление
                    self.driver.get(next_url)
                    logging.info(f"Поток {self.thread_id}: Обновлено, перешли на ссылку: {next_url}")

                except WebDriverException as e:
                    logging.error(f"Поток {self.thread_id}: Ошибка Selenium при обновлении на {next_url}: {e}")
                    logging.warning(f"Поток {self.thread_id}: Завершение работы из-за ошибки Selenium.")
                    break
                except Exception as e:
                    logging.error(f"Поток {self.thread_id}: Непредвиденная ошибка: {e}")
                    logging.warning(f"Поток {self.thread_id}: Завершение работы из-за непредвиденной ошибки.")
                    break

        except Exception as e:
            logging.error(f"Поток {self.thread_id}: Ошибка при инициализации драйвера или первой загрузке: {e}")

        finally:
            # Убедимся, что драйвер закрыт при завершении потока
            if self.driver:
                try:
                    self.driver.quit()
                    logging.info(f"Поток {self.thread_id}: Драйвер закрыт.")
                    if self.driver in active_drivers:
                         active_drivers.remove(self.driver)
                except Exception as e:
                    logging.error(f"Поток {self.thread_id}: Ошибка при закрытии драйвера: {e}")

            logging.info(f"Поток {self.thread_id} завершен.")

    def stop(self):
        """Сигнализирует потоку о необходимости завершения."""
        logging.info(f"Поток {self.thread_id}: Получен запрос на остановку.")
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

# Функция настройки драйвера, принимает параметр is_headless
def setup_driver(window_size, is_headless):
    """Настраивает и возвращает экземпляр ChromeDriver."""
    options = Options()
    if is_headless: # Условное добавление опции headless
        options.add_argument("--headless=new") # Используйте "--headless=new" для более новых версий Chrome/ChromeDriver
        # Если у вас более старая версия, используйте просто "--headless"
        # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    # Можете добавить другие опции

    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        raise e # Позволяем исключению распространиться

def watch_urls(urls, num_windows, refresh_interval, window_size, is_headless):
    """Запускает просмотр URL в нескольких окнах с обновлением, используя потоки."""
    if not urls:
        logging.warning("Нет ссылок для просмотра.")
        return

    num_windows_to_use = min(num_windows, len(urls))
    if num_windows_to_use == 0:
        logging.warning("Нет доступных ссылок для открытия окон.")
        return

    threads = []
    logging.info(f"Создание {num_windows_to_use} потоков для просмотра {len(urls)} ссылок.")

    for i in range(num_windows_to_use):
        # Передаем состояние headless в конструктор BrowserWatcher
        thread = BrowserWatcher(urls, refresh_interval, window_size, is_headless, thread_id=i)
        threads.append(thread)
        thread.start()

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
    # Добавляем опциональный флаг headless
    parser.add_argument(
        '-H', '--headless',
        action='store_true', # Этот аргумент просто устанавливает True, если присутствует
        help='Запустить браузеры в headless режиме (без видимого окна).'
    )


    args = parser.parse_args()

    # Парсим размер окна
    try:
        width, height = map(int, args.size.split('x'))
        window_size = (width, height)
    except ValueError:
        logging.error(f"Неверный формат размера окна: {args.size}. Используйте формат ШИРИНАxВЫСОТА (например, 800x600).")
        sys.exit(1)

    logging.info(f"Чтение ссылок из файла: {args.urls_file}")
    urls = read_urls_from_file(args.urls_file)

    logging.info(f"Параметры запуска: Windows={args.windows}, Interval={args.interval}, Size={args.size}, Headless={args.headless}")

    # Передаем значение args.headless в watch_urls
    watch_urls(urls, args.windows, args.interval, window_size, args.headless)

if __name__ == "__main__":
    main()
