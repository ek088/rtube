import argparse
import logging
import time
import sys
import threading # Добавляем импорт для работы с потоками

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException # Импортируем исключения Selenium

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Список для хранения всех активных драйверов, чтобы можно было их закрыть при выходе
active_drivers = []
# Блокировка для безопасного доступа к списку драйверов, если потребуется
# driver_list_lock = threading.Lock() # Возможно, не потребуется для данного уровня сложности

class BrowserWatcher(threading.Thread):
    """
    Поток, управляющий одним окном браузера и его циклом обновления.
    """
    def __init__(self, url_list, refresh_interval, window_size, thread_id):
        threading.Thread.__init__(self)
        self.url_list = url_list
        self.refresh_interval = refresh_interval
        self.window_size = window_size
        self.thread_id = thread_id
        self.driver = None
        self._stop_event = threading.Event() # Событие для сигнализации потоку о завершении
        self.current_url_index = 0

    def run(self):
        """Метод, выполняемый при запуске потока."""
        logging.info(f"Поток {self.thread_id} стартовал.")

        try:
            # Инициализация драйвера для этого потока
            self.driver = setup_driver(self.window_size)
            # with driver_list_lock: # Если нужно блокировать доступ к списку
            active_drivers.append(self.driver)
            logging.info(f"Поток {self.thread_id}: Драйвер инициализирован.")

            # Открываем первую ссылку
            if not self.url_list:
                logging.warning(f"Поток {self.thread_id}: Список ссылок пуст.")
                return # Завершаем поток, если нет ссылок

            initial_url = self.url_list[self.current_url_index]
            self.driver.get(initial_url)
            logging.info(f"Поток {self.thread_id}: Открыта начальная ссылка: {initial_url}")

            # Основной цикл обновления
            while not self._stop_event.is_set(): # Проверяем, нужно ли завершить работу
                # Переходим к следующей ссылке
                self.current_url_index = (self.current_url_index + 1) % len(self.url_list)
                next_url = self.url_list[self.current_url_index]

                try:
                    # Задержка перед обновлением. Используем wait() с timeout,
                    # чтобы можно было прервать ожидание при получении сигнала завершения
                    if self._stop_event.wait(self.refresh_interval):
                        logging.info(f"Поток {self.thread_id}: Получен сигнал остановки, завершение ожидания.")
                        break # Выходим из цикла, если получили сигнал остановки

                    # Выполняем обновление
                    self.driver.get(next_url)
                    logging.info(f"Поток {self.thread_id}: Обновлено, перешли на ссылку: {next_url}")

                except WebDriverException as e:
                    logging.error(f"Поток {self.thread_id}: Ошибка Selenium при обновлении на {next_url}: {e}")
                    # В случае ошибки Selenium, возможно, стоит попытаться продолжить
                    # Или закрыть этот конкретный драйвер и завершить поток?
                    # Для простоты при ошибке этого окна, завершаем только его поток.
                    logging.warning(f"Поток {self.thread_id}: Завершение работы из-за ошибки Selenium.")
                    break # Выходим из цикла при ошибке Selenium
                except Exception as e:
                    logging.error(f"Поток {self.thread_id}: Непредвиденная ошибка: {e}")
                    logging.warning(f"Поток {self.thread_id}: Завершение работы из-за непредвиденной ошибки.")
                    break # Выходим из цикла при другой ошибке

        except Exception as e:
            logging.error(f"Поток {self.thread_id}: Ошибка при инициализации драйвера или первой загрузке: {e}")

        finally:
            # Убедимся, что драйвер закрыт при завершении потока
            if self.driver:
                try:
                    self.driver.quit()
                    logging.info(f"Поток {self.thread_id}: Драйвер закрыт.")
                    # with driver_list_lock:
                    if self.driver in active_drivers:
                         active_drivers.remove(self.driver)
                except Exception as e:
                    logging.error(f"Поток {self.thread_id}: Ошибка при закрытии драйвера: {e}")

            logging.info(f"Поток {self.thread_id} завершен.")

    def stop(self):
        """Сигнализирует потоку о необходимости завершения."""
        logging.info(f"Поток {self.thread_id}: Получен запрос на остановку.")
        self._stop_event.set()
        # Попытка закрыть драйвер может помочь потоку быстрее завершиться,
        # но может вызвать исключение, если драйвер уже в плохом состоянии.
        # Можно попробовать добавить здесь driver.quit() с try/except.
        # try:
        #     if self.driver:
        #          self.driver.quit()
        # except Exception as e:
        #     logging.warning(f"Поток {self.thread_id}: Ошибка при попытке закрыть драйвер при остановке: {e}")


def read_urls_from_file(filepath):
    """Читает список URL из файла."""
    urls = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url:  # Игнорируем пустые строки
                    urls.append(url)
    except FileNotFoundError:
        logging.error(f"Файл с ссылками не найден: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Ошибка при чтении файла с ссылками {filepath}: {e}")
        sys.exit(1)
    return urls

# Упрощенная функция настройки драйвера (без webdriver-manager)
def setup_driver(window_size):
    """Настраивает и возвращает экземпляр ChromeDriver."""
    options = Options()
    # Для работы в консоли часто не нужна видимость окна браузера
    # options.add_argument("--headless") # Закомментировано для видимости окон
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    # Можете добавить другие опции, например, User-Agent

    try:
        # Использование Service без явного указания executable_path.
        # Selenium попробует найти chromedriver в PATH или других стандартных местах.
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        # Логирование ошибки инициализации драйвера происходит в потоке или main,
        # в зависимости от того, где происходит вызов setup_driver.
        # Здесь просто возбуждаем исключение, чтобы вызывающий код его поймал.
        raise e # Позволяем исключению распространиться

def watch_urls(urls, num_windows, refresh_interval, window_size):
    """Запускает просмотр URL в нескольких окнах с обновлением, используя потоки."""
    if not urls:
        logging.warning("Нет ссылок для просмотра.")
        return

    # Ограничиваем количество окон количеством доступных ссылок
    num_windows_to_use = min(num_windows, len(urls))
    if num_windows_to_use == 0:
        logging.warning("Нет доступных ссылок для открытия окон.")
        return

    threads = []
    logging.info(f"Создание {num_windows_to_use} потоков для просмотра {len(urls)} ссылок.")

    for i in range(num_windows_to_use):
        # Создаем подмножество URL для каждого потока, если нужно
        # В данном случае каждый поток будет циклически перебирать ВЕСЬ список URL
        thread = BrowserWatcher(urls, refresh_interval, window_size, thread_id=i)
        threads.append(thread)
        # Можно установить поток как демон, чтобы он завершился автоматически
        # при завершении основной программы, но это не гарантирует аккуратное закрытие драйверов.
        # thread.daemon = True
        thread.start()

    logging.info("Все потоки запущены.")

    try:
        # Основной поток просто ждет сигнала прерывания (Ctrl+C)
        # Или вы можете добавить логику для Join всех потоков, если они должны завершаться сами
        # Например, если список ссылок конечен и каждое окно проходит его один раз.
        # Но в вашем случае, кажется, они должны работать постоянно.
        while True:
            time.sleep(1) # Делаем небольшую задержку, чтобы не загружать CPU
            # Проверяем, остались ли активные драйверы/потоки
            # if not active_drivers:
            #     logging.warning("Все драйверы закрылись. Завершение работы.")
            #     break # Выходим из цикла, если все окна закрылись

    except KeyboardInterrupt:
        logging.info("Получен сигнал прерывания (Ctrl+C). Инициирую завершение потоков.")
        # При получении Ctrl+C, просим каждый поток остановиться
        for thread in threads:
            thread.stop()

        # Ждем завершения всех потоков (или таймаут)
        logging.info("Ожидание завершения потоков...")
        for thread in threads:
             # Можно использовать thread.join(timeout) для установки таймаута
             thread.join() # Ждем бесконечно, пока поток не завершится сам

    finally:
        # Убеждаемся, что все драйверы закрыты в конце, даже если что-то пошло не так
        # в логике остановки потоков.
        logging.info("Закрытие оставшихся драйверов.")
        # Итерируемся по копии списка active_drivers
        for driver in list(active_drivers):
            try:
                driver.quit()
                # with driver_list_lock:
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

    logging.info(f"Параметры запуска: Windows={args.windows}, Interval={args.interval}, Size={args.size}")

    watch_urls(urls, args.windows, args.interval, window_size)

if __name__ == "__main__":
    main()
