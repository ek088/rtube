import argparse
import logging
import time
import sys
import threading
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Создаем файловый обработчик для ошибок, ЯВНО УКАЗЫВАЯ КОДИРОВКУ UTF-8
error_file_handler = logging.FileHandler('logs.txt', encoding='utf-8')
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Получаем корневой логгер и добавляем файловый обработчик
root_logger = logging.getLogger()
root_logger.addHandler(error_file_handler)

active_drivers = []

class BrowserWatcher(threading.Thread):
    """
    Поток, управляющий одним окном браузера и его циклом обновления.
    Перезапускает браузер в случае ошибки.
    """
    def __init__(self, url_list, refresh_interval, window_size, is_headless, thread_id):
        threading.Thread.__init__(self)
        self.url_list = url_list
        self.refresh_interval = refresh_interval
        self.window_size = window_size
        self.is_headless = is_headless
        self.thread_id = thread_id
        self.driver = None # Драйвер инициализируется внутри run
        self._stop_event = threading.Event()
        self.current_url_index = 0
        self.logger = logging.getLogger(f'Thread-{self.thread_id}')
        # Устанавливаем начальный индекс для этого потока, если нужно
        # (Логика установки начального индекса из watch_urls будет вызвана после __init__)


    def run(self):
        """Метод, выполняемый при запуске потока."""
        self.logger.info("Поток стартовал.")

        # Внешний цикл для перезапуска браузера. Продолжается до получения сигнала остановки.
        while not self._stop_event.is_set():
            try:
                # --- Инициализация драйвера и первая загрузка для этого цикла перезапуска ---
                # Инициализируем драйвер только если он None (первый запуск или после ошибки)
                if self.driver is None:
                     self.logger.info("Попытка инициализации нового драйвера...")
                     self.driver = setup_driver(self.window_size, self.is_headless)
                     # with driver_list_lock:
                     active_drivers.append(self.driver)
                     self.logger.info(f"Драйвер инициализирован (headless: {self.is_headless}).")

                     # Открываем первую ссылку после успешной инициализации нового драйвера
                     if not self.url_list:
                         self.logger.warning("Список ссылок пуст.")
                         self.stop() # Сигнализируем о завершении, если нет ссылок
                         break # Выходим из внешнего цикла

                     # Начинаем с текущего индекса ссылки (сохранен после предыдущей ошибки или установлен из watch_urls)
                     initial_url = self.url_list[self.current_url_index]
                     self.driver.get(initial_url)
                     self.logger.info(f"Открыта начальная ссылка в новом драйвере: {initial_url}")
                     # Успешно открыли первую ссылку, теперь переходим к циклу обновления


                # --- Внутренний цикл обновления. Работает, пока драйвер жив и нет сигнала остановки ---
                # Если мы сюда попали, значит драйвер успешно инициализирован и загрузил первую ссылку
                while not self._stop_event.is_set():
                    # Переходим к следующей ссылке
                    self.current_url_index = (self.current_url_index + 1) % len(self.url_list)
                    next_url = self.url_list[self.current_url_index]

                    try:
                        # Задержка перед обновлением. wait() прерывается при stop_event.
                        # Если wait() возвращает True, значит, _stop_event был установлен.
                        if self._stop_event.wait(random.randint(self.refresh_interval - 2, self.refresh_interval + 3)):
                            self.logger.info("Получен сигнал остановки во время ожидания, завершение внутреннего цикла.")
                            break # Выходим из внутреннего цикла

                        # Выполняем обновление
                        self.driver.get(next_url)
                        self.logger.info(f"Обновлено, перешли на ссылку: {next_url}")

                    # Перехватываем ошибки Selenium (включая тайм-ауты) при операции get()
                    except WebDriverException as e:
                        self.logger.error(f"Ошибка Selenium при обновлении на {next_url}: {e}")
                        # При ошибке Selenium, закрываем текущий драйвер и выходим из внутреннего цикла.
                        # Внешний цикл поймает это и попытается перезапустить.
                        break # Выходим из внутреннего цикла, чтобы сработал блок except/finally внешнего цикла
                    except Exception as e:
                        # Перехватываем любые другие непредвиденные ошибки во внутреннем цикле
                        self.logger.error(f"Непредвиденная ошибка во внутреннем цикле: {e}")
                        break # Выходим из внутреннего цикла

                # Если вышли из внутреннего цикла (либо из-за break, либо _stop_event)
                if self._stop_event.is_set():
                     self.logger.info("Внешний цикл: Обнаружен сигнал остановки.")
                     break # Выходим и из внешнего цикла тоже


            # --- Перехват ошибок инициализации или ошибок из внутреннего цикла ---
            # Этот блок сработает, если в блоке try выше (при инициализации или во внутреннем цикле)
            # возникло исключение (WebDriverException, SessionNotCreatedException, или любое другое,
            # если оно не было поймано во внутреннем try-except).
            except (WebDriverException, SessionNotCreatedException) as e:
                 self.logger.error(f"Ошибка при работе или инициализации драйвера: {e}")
                 # Закрываем проблемный драйвер, если он был создан
                 if self.driver:
                     try:
                         self.driver.quit()
                         self.logger.info("Закрыт проблемный драйвер после ошибки.")
                         # with driver_list_lock:
                         if self.driver in active_drivers:
                             active_drivers.remove(self.driver)
                     except Exception as quit_e:
                          self.logger.error(f"Ошибка при закрытии проблемного драйвера: {quit_e}")
                 self.driver = None # Сбрасываем ссылку на драйвер, чтобы в следующем витке внешнего цикла он был переинициализирован

                 # Задержка перед попыткой перезапуска, если программа не завершается
                 if not self._stop_event.is_set():
                     restart_delay = random.randint(1,10)
                     self.logger.warning(f"Попытка перезапуска через {restart_delay} секунд...")
                     # Ждем с возможностью прерывания
                     if self._stop_event.wait(restart_delay):
                         self.logger.info("Получен сигнал остановки во время задержки перезапуска.")
                         break # Выходим из внешнего цикла, если получили сигнал во время ожидания
                 else:
                      self.logger.info("Сигнал остановки получен, перезапуск отменен.")
                      break # Выходим из внешнего цикла

            except Exception as e:
                # Ловим любые другие исключения, которые могли просочиться
                self.logger.error(f"Непредвиденная ошибка в основном цикле потока: {e}")
                # Аналогично, пытаемся закрыть драйвер при любой другой ошибке
                if self.driver:
                    try:
                        self.driver.quit()
                        self.logger.info("Закрыт драйвер из-за непредвиденной ошибки.")
                        # with driver_list_lock:
                        if self.driver in active_drivers:
                            active_drivers.remove(self.driver)
                    except Exception as quit_e:
                         self.logger.error(f"Ошибка при закрытии драйвера после непредвиденной ошибки: {quit_e}")
                self.driver = None # Сбрасываем драйвер

                if not self._stop_event.is_set():
                    restart_delay = random.randint(1,10)
                    self.logger.warning(f"Попытка перезапуска через {restart_delay} секунд...")
                    if self._stop_event.wait(restart_delay):
                        self.logger.info("Получен сигнал остановки во время задержки перезапуска.")
                        break
                else:
                     self.logger.info("Сигнал остановки получен, перезапуск отменен.")
                     break


            finally:
                # Этот блок выполняется при выходе из ВНЕШНЕГО цикла while (т.е. при окончательном завершении потока)
                # Убедимся, что драйвер закрыт, если он еще открыт
                self.logger.info("Поток завершает работу.")
                if self.driver:
                    try:
                        self.driver.quit()
                        self.logger.info("Драйвер закрыт при окончательном завершении потока.")
                        # with driver_list_lock:
                        if self.driver in active_drivers:
                                active_drivers.remove(self.driver)
                    except Exception as e:
                        self.logger.error(f"Ошибка при закрытии драйвера в finally блоке потока: {e}")
                    self.driver = None # Окончательно сбрасываем

                self.logger.info("Поток завершен.")


    def stop(self):
        """Сигнализирует потоку о необходимости завершения."""
        self.logger.info("Получен запрос на остановку.")
        self._stop_event.set()
        # Можно добавить здесь driver.quit() с try/except,
        # чтобы разблокировать блокирующие операции быстрее,
        # но это может быть менее надежно, чем дождаться обработки в run().
        # try:
        #     if self.driver:
        #         # Закрытие драйвера может вызвать исключения, если он уже в плохом состоянии
        #         self.driver.quit()
        #         self.logger.info("Попытка экстренного закрытия драйвера при остановке.")
        # except Exception as e:
        #     self.logger.warning(f"Ошибка при попытке экстренного закрытия драйвера при остановке: {e}")


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
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    # Опции, добавленные вами:
    options.add_argument('--disable-ad-blocking')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-notifications')
    options.add_argument('--mute-audio')
    options.add_argument('--disable-blink-features=AutomationControlled')

    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        # Здесь мы просто возбуждаем исключение, обработка в вызывающем коде (run метода BrowserWatcher)
        raise e

def watch_urls(urls, num_windows, refresh_interval, window_size, is_headless):
    """Запускает просмотр URL в нескольких окнах с обновлением, используя потоки."""
    if not urls:
        logging.warning("Нет ссылок для просмотра.")
        return

    if len(urls) == 0: # Проверяем, что список ссылок не пуст
        logging.warning("Нет доступных ссылок для открытия окон.")
        return

    threads = []
    logging.info(f"Создание {num_windows} потоков для просмотра {len(urls)} ссылок.")

    url_index = 0
    for i in range(num_windows): # Итерируемся до запрошенного количества окон
        thread = BrowserWatcher(urls, refresh_interval, window_size, is_headless, thread_id=i)
        # Устанавливаем начальный индекс для этого потока
        thread.current_url_index = url_index
        threads.append(thread)
        thread.start()
        time.sleep(2)

        # Определяем начальный индекс для следующего потока
        # Если окон больше, чем ссылок, индексы будут повторяться
        url_index = (url_index + 1) % len(urls)


    logging.info("Все потоки запущены.")
    if is_headless:
        logging.info("Браузеры работают в headless режиме (без видимых окон).")
    else:
        logging.info("Браузеры работают в видимом режиме.")


    try:
        # Основной поток просто ждет сигнала прерывания (Ctrl+C)
        while True:
            time.sleep(1) # Небольшая задержка, чтобы не загружать CPU

    except KeyboardInterrupt:
        logging.info("Получен сигнал прерывания (Ctrl+C). Инициирую завершение потоков.")
        # При получении Ctrl+C, просим каждый поток остановиться
        for thread in threads:
            thread.stop()

        # Ждем завершения всех потоков
        logging.info("Ожидание завершения потоков...")
        for thread in threads:
             # Используем join() без таймаута, чтобы дождаться их аккуратного завершения
             thread.join()

    finally:
        # Убеждаемся, что все драйверы закрыты в конце, даже если что-то пошло не так.
        logging.info("Закрытие оставшихся драйверов.")
        # Итерируемся по копии списка active_drivers, т.к. элементы могут удаляться внутри цикла
        for driver in list(active_drivers):
            try:
                driver.quit()
                # with driver_list_lock: # Если используется блокировка
                if driver in active_drivers:
                     active_drivers.remove(driver)
            except Exception as e:
                logging.error(f"Ошибка при закрытии драйвера в finally блоке watch_urls: {e}")

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
