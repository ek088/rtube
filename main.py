import argparse
import logging
import asyncio
import sys
import random
import settings
from typing import Optional
from playwright.async_api import async_playwright, Playwright, Browser, Page, Error
from aiogram import Bot
from services.captcha_service import YandexCaptchaEnums, YandexCaptchaSolver




logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

error_file_handler = logging.FileHandler('logs.txt', encoding='utf-8')
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

root_logger = logging.getLogger()
root_logger.addHandler(error_file_handler)

alerting_bot = Bot(settings.TELEGRAM_BOT_TOKEN)

active_pages = []
pages_lock = asyncio.Lock()

class PageWatcher:
    rutube_ads_watched = 0
    reloads_count = 0
    def __init__(self, playwright_instance: Playwright, url_list, refresh_interval, window_size, is_headless, thread_id, name):
        self.name = name
        self.playwright = playwright_instance
        self.url_list = url_list
        self.refresh_interval = refresh_interval
        self.window_size = window_size
        self.is_headless = is_headless
        self.thread_id = thread_id
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._stop_event = asyncio.Event()
        self.current_url_index = 0
        self.logger = logging.getLogger(f'Watcher-{self.thread_id}')

    async def solve_yandex_captcha(self):
        if random.randint(1,3) != 2:
            self.logger.info(f'{self.name}: Пробую скипнуть без прохождения капчи')
            return

        captcha_button = self.page.locator(YandexCaptchaEnums.IM_NOT_ROBOT_BUTTON)
        await captcha_button.wait_for(timeout=20000)
        await captcha_button.click()

        await self.page.wait_for_selector(YandexCaptchaEnums.CAPTCHA_IMAGE_SELECTOR, state='visible')
        await self.page.wait_for_selector(YandexCaptchaEnums.CAPTCHA_ONLY_IMAGE, state='visible')

        captcha_image = self.page.locator(YandexCaptchaEnums.CAPTCHA_IMAGE_SELECTOR)
        await captcha_image.wait_for(timeout=20000)
        await asyncio.sleep(5)

        await captcha_image.screenshot(path=f'screenshots/{self.name}.png')
        self.logger.info(f"{self.name}: Капча отправлена на решение")
        coordinates = await YandexCaptchaSolver.solve(image_path=f'screenshots/{self.name}.png')

        for point in coordinates:
            await captcha_image.click(position=point)
            await asyncio.sleep(1)

        solve_button = self.page.locator(YandexCaptchaEnums.SOLVED_BUTTON_SELECTOR)
        await solve_button.click()
        self.logger.info(f"{self.name}: Капча решена")

        await asyncio.sleep(2)

    async def run(self):
        """Асинхронный метод, выполняемый при запуске наблюдателя страницы."""
        self.logger.info("Наблюдатель страницы стартовал.")

        while not self._stop_event.is_set():
            try:

                if self.browser is None or self.page is None:
                    self.logger.info("Попытка инициализации нового браузера и страницы...")
                    self.browser = await self.playwright.chromium.launch(
                        channel="chrome",
                        headless=self.is_headless,
                    )

                    context = await self.browser.new_context(viewport={'width': self.window_size[0], 'height': self.window_size[1]})

                    self.page = await context.new_page()

                    async with pages_lock:
                        active_pages.append(self.page)

                    self.logger.info(f"Браузер и страница инициализированы (headless: {self.is_headless}).")

                    if not self.url_list:
                        self.logger.warning("Список ссылок пуст.")
                        self.stop()
                        break


                    initial_url = self.url_list[self.current_url_index]
                    await self.page.goto(initial_url, timeout=60000)
                    self.logger.info(f"Открыта начальная ссылка в новой странице: {initial_url}")

                while not self._stop_event.is_set():
                    self.current_url_index = (self.current_url_index + 1) % len(self.url_list)
                    next_url = self.url_list[self.current_url_index]

                    try:

                        try:
                             await asyncio.wait_for(self._stop_event.wait(), timeout=random.randint(self.refresh_interval - 1, self.refresh_interval + 2))
                             self.logger.info("Получен сигнал остановки во время ожидания, завершение внутреннего цикла.")
                             break
                        except asyncio.TimeoutError:
                             pass

                        try:
                            if "showcaptcha" in self.page.url:
                                logging.info(f"{self.name}: Появилась капча")
                                try:
                                    await self.solve_yandex_captcha()
                                except Exception as e:
                                    logging.error(f"Ошибка при решении капчи: {e}")
                                # await alerting_bot.send_message(chat_id=settings.TELEGRAM_BOT_CHAT_ID, text="ПОЯВИЛАСЬ КАПЧА")
                                # await asyncio.sleep(120)

                            ad_element = self.page.locator("text=Отключить рекламу")
                            if await ad_element.count() > 0:
                                PageWatcher.rutube_ads_watched += 1
                                self.logger.info(f"Rutube Реклам просмотрено: {PageWatcher.rutube_ads_watched}" )
                            PageWatcher.reloads_count += 1
                        except:
                            pass
                        await self.page.goto(next_url, wait_until=None, timeout=self.refresh_interval*1000)

                        self.logger.info(f"Обновлено, перешли на ссылку: {next_url}")

                    except TimeoutError:
                        self.logger.info(f"Яндекс пытается помешать соединению, продолжаем работу")

                    except Error as e:
                        self.logger.error(f"Ошибка Playwright при обновлении на {next_url}: {e}")
                        break
                    except Exception as e:
                        self.logger.error(f"Непредвиденная ошибка во внутреннем цикле: {e}")
                        break

                if self._stop_event.is_set():
                     self.logger.info("Внешний цикл: Обнаружен сигнал остановки.")
                     break

            except Error as e:
                 self.logger.error(f"Ошибка Playwright при работе или инициализации: {e}")
                 await self._close_browser_and_page()

                 if not self._stop_event.is_set():
                     restart_delay = random.randint(1, 5)
                     self.logger.warning(f"Попытка перезапуска через {restart_delay} секунд...")
                     try:
                         await asyncio.wait_for(self._stop_event.wait(), timeout=restart_delay)
                         self.logger.info("Получен сигнал остановки во время задержки перезапуска.")
                         break
                     except asyncio.TimeoutError:
                         pass
                 else:
                      self.logger.info("Сигнал остановки получен, перезапуск отменен.")
                      break


            except Exception as e:
                self.logger.error(f"Непредвиденная ошибка в основном цикле наблюдателя: {e}")
                await self._close_browser_and_page()

                if not self._stop_event.is_set():
                    restart_delay = random.randint(1, 5)
                    self.logger.warning(f"Попытка перезапуска через {restart_delay} секунд...")
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=restart_delay)
                        self.logger.info("Получен сигнал остановки во время задержки перезапуска.")
                        break
                    except asyncio.TimeoutError:
                         pass
                else:
                     self.logger.info("Сигнал остановки получен, перезапуск отменен.")
                     break


            finally:
                self.logger.info("Наблюдатель страницы завершает работу.")
                await self._close_browser_and_page()
                self.logger.info("Наблюдатель страницы завершен.")


    async def _close_browser_and_page(self):
        """Аккуратно закрывает страницу и браузер."""
        if self.page:
            try:
                async with pages_lock:
                    if self.page in active_pages:
                        active_pages.remove(self.page)
                await self.page.close()
                self.logger.info("Страница закрыта.")
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии страницы: {e}")
            self.page = None

        if self.browser:
            try:
                await self.browser.close()
                self.logger.info("Браузер закрыт.")
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии браузера: {e}")
            self.browser = None


    def stop(self):
        """Сигнализирует наблюдателю о необходимости завершения."""
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

async def watch_urls(urls, num_windows, refresh_interval, window_size, is_headless):
    """Запускает просмотр URL в нескольких окнах с обновлением, используя асинхронные задачи."""
    if not urls:
        logging.warning("Нет ссылок для просмотра.")
        return

    if len(urls) == 0:
        logging.warning("Нет доступных ссылок для открытия окон.")
        return

    # Playwright запускается один раз для всего асинхронного контекста
    async with async_playwright() as p:
        watchers = []
        logging.info(f"Создание {num_windows} наблюдателей для просмотра {len(urls)} ссылок.")

        url_index = 0
        for i in range(num_windows):
            watcher = PageWatcher(p, urls, refresh_interval, window_size, is_headless, thread_id=i, name=f"process_{i}")
            watcher.current_url_index = url_index
            watchers.append(watcher)
            # Запускаем run() как асинхронную задачу
            asyncio.create_task(watcher.run())

            # Определяем начальный индекс для следующего наблюдателя
            url_index = (url_index + 1) % len(urls)

            # Небольшая задержка между запуском наблюдателей
            await asyncio.sleep(2)


        logging.info("Все наблюдатели запущены.")
        if is_headless:
            logging.info("Браузеры работают в headless режиме (без видимых окон).")
        else:
            logging.info("Браузеры работают в видимом режиме.")


        try:
            while True:
                if all(watcher._stop_event.is_set() for watcher in watchers):
                    logging.info("Все наблюдатели завершили работу.")
                    break
                await asyncio.sleep(1)

        except asyncio.CancelledError:
             logging.info("Получен сигнал отмены (например, из-за KeyboardInterrupt). Инициирую завершение наблюдателей.")
             for watcher in watchers:
                 watcher.stop()
             logging.info("Ожидание завершения наблюдателей...")
             await asyncio.gather(*[watcher.run() for watcher in watchers if not watcher._stop_event.is_set()], return_exceptions=True)


        finally:
            # Убеждаемся, что все страницы и браузеры закрыты в конце
            logging.info("Закрытие оставшихся страниц и браузеров.")
            async with pages_lock:
                for page in list(active_pages):
                    try:
                        await page.close()
                        if page in active_pages:
                             active_pages.remove(page)
                    except Exception as e:
                        logging.error(f"Ошибка при закрытии страницы в finally блоке watch_urls: {e}")
            logging.info(f"ОТЧЕТ | Просмотры: {PageWatcher.reloads_count} | Просмотрено реклам на Rutube: {PageWatcher.rutube_ads_watched}")

            logging.info("Программа завершена.")


async def main():
    """Основная асинхронная функция для парсинга аргументов и запуска просмотра."""
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
        default=5,
        help='Интервал обновления страниц в секундах (по умолчанию: 5)'
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

    await watch_urls(urls, args.windows, args.interval, window_size, args.headless)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Программа прервана пользователем (Ctrl+C).")

    except Exception as e:
        logging.error(f"Непредвиденная ошибка в main: {e}")
        sys.exit(1)