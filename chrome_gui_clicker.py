import customtkinter as ctk
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from threading import Thread, Event
import time
import sys # Импортируем sys для проверки платформы и возможного указания пути к драйверу

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

# Функция для получения пути к драйверу (может потребоваться, если chromedriver не в PATH)
# В этом примере предполагается, что chromedriver находится в PATH.
# Если это не так, вам может понадобиться изменить эту функцию или использовать Service.
def get_driver_path():
    # Здесь можно добавить логику для поиска chromedriver в определенных местах
    # Или просто вернуть 'chromedriver', если он в PATH
    return 'chromedriver'

class BrowserController(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('Browser Controller')
        self.geometry('600x500')
        self.stop_event = Event()
        self.threads = []
        self.url_map = {} # Возможно, эта переменная не используется активно в текущем коде, но оставлена
        self.create_widgets()
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(pady=10, padx=10, fill='both', expand=True)

        ctk.CTkLabel(main_frame, text='Введите ссылки (каждая с новой строки):').pack(pady=5)
        self.urls_entry = ctk.CTkTextbox(main_frame, height=150)
        self.urls_entry.pack(pady=5, padx=10, fill='x')

        settings_frame = ctk.CTkFrame(main_frame, fg_color='transparent')
        settings_frame.pack(pady=5, fill='x', expand=True)

        left_col = ctk.CTkFrame(settings_frame, fg_color='transparent')
        left_col.pack(side='left', fill='x', expand=True)

        right_col = ctk.CTkFrame(settings_frame, fg_color='transparent')
        right_col.pack(side='right', fill='x', expand=True)

        ctk.CTkLabel(left_col, text='Количество окон:').pack(anchor='w')
        self.window_count = ctk.CTkEntry(left_col, placeholder_text='По умолчанию: 4')
        self.window_count.pack(pady=5, fill='x')

        ctk.CTkLabel(left_col, text='Интервал обновления (сек):').pack(anchor='w')
        self.refresh_entry = ctk.CTkEntry(left_col, placeholder_text='По умолчанию: 2.5')
        self.refresh_entry.pack(pady=5, fill='x')

        ctk.CTkLabel(right_col, text='Размер окна (ширина x высота):').pack(anchor='w')
        size_frame = ctk.CTkFrame(right_col, fg_color='transparent')
        size_frame.pack(pady=5, fill='x')

        self.width_entry = ctk.CTkEntry(size_frame, placeholder_text='860', width=70)
        self.width_entry.pack(side='left', padx=2)
        ctk.CTkLabel(size_frame, text='x').pack(side='left', padx=2)
        self.height_entry = ctk.CTkEntry(size_frame, placeholder_text='700', width=70)
        self.height_entry.pack(side='left', padx=2)

        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(pady=10)

        self.start_btn = ctk.CTkButton(button_frame, text='Запустить', command=self.start_browsers, fg_color='green', hover_color='dark green')
        self.start_btn.pack(side='left', padx=10)

        self.stop_btn = ctk.CTkButton(button_frame, text='Остановить', command=self.stop_browsers, fg_color='red', hover_color='dark red', state='disabled')
        self.stop_btn.pack(side='right', padx=10)

        self.status_label = ctk.CTkLabel(main_frame, text='Статус: Остановлено')
        self.status_label.pack(pady=5)

    def browser_instance(self, original_url, window_id, refresh_interval, width, height):
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-ad-blocking')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--mute-audio')
        options.add_argument('--disable-blink-features=AutomationControlled')
        # Добавьте этот аргумент, если хотите запускать Chrome в фоновом режиме (без GUI)
        # options.add_argument('--headless')

        driver = None # Инициализируем driver перед циклом

        while not self.stop_event.is_set(): # Внешний цикл для перезапуска браузера при ошибке
            try:
                # Инициализация драйвера должна быть внутри try, так как она может вызвать исключение
                driver = webdriver.Chrome(options=options) # Здесь предполагается, что chromedriver в PATH
                # Если chromedriver не в PATH, используйте Service:
                # from selenium.webdriver.chrome.service import Service
                # service = Service(get_driver_path()) # Укажите путь к chromedriver
                # driver = webdriver.Chrome(service=service, options=options)

                driver.set_window_size(width, height)
                driver.get(original_url)
                self.url_map[window_id] = original_url # Обновляем карту URL
                print(f'Окно {window_id} запущено с URL: {original_url}')

                # Внутренний цикл для обновления страницы, пока не получена команда остановки
                while not self.stop_event.is_set():
                    try:
                        current_url = driver.current_url
                        if current_url != original_url:
                            print(f'Обнаружен измененный URL в окне {window_id}. Возвращаю исходный...')
                            driver.get(original_url)
                            time.sleep(2) # Небольшая задержка после возврата на исходный URL

                        # Обновление всех окон/вкладок (если их несколько)
                        # Note: Исходный код переключался на каждое окно и обновлял его.
                        # Это может быть неэффективно, если окон много.
                        # Возможно, имелось в виду обновление только текущего окна.
                        # Оставляем как в декомпилированном коде, но имейте в виду.
                        for handle in driver.window_handles:
                            driver.switch_to.window(handle)
                            driver.get(current_url)
                            # print(f'Окно {window_id} обновлено') # Печать в цикле может быть избыточной

                        print(f'Окно {window_id} обновлено') # Печатаем один раз после всех обновлений

                        time.sleep(refresh_interval)

                    except WebDriverException as e:
                        # Если возникла ошибка WebDriverException внутри внутреннего цикла,
                        # возможно, браузер был закрыт или возникла другая проблема.
                        print(f'WebDriverException в окне {window_id}: {str(e)}')
                        # Выходим из внутреннего цикла, чтобы попытаться перезапустить браузер во внешнем цикле
                        break # Выход из внутреннего цикла

                    except Exception as e:
                         print(f'Неизвестная ошибка в окне {window_id} во внутреннем цикле: {str(e)}')
                         break # Выход из внутреннего цикла при других ошибках

            except Exception as e:
                # Обработка ошибок при запуске браузера или критических ошибок
                print(f'Ошибка при запуске/работе окна {window_id}: {str(e)}')
                # Проверяем, связана ли ошибка с недоступностью Chrome (браузер закрыт)
                if driver and 'chrome not reachable' in str(e).lower():
                    print(f'Окно {window_id} закрыто, перезапускаю...')
                    try:
                        driver.quit() # Пытаемся закрыть драйвер, если он был создан
                    except:
                        pass # Игнорируем ошибки при закрытии
                    driver = None # Обнуляем драйвер перед следующей попыткой
                    continue # Переходим к следующей итерации внешнего цикла для перезапуска
                else:
                    # Если ошибка не связана с недоступностью Chrome, возможно, это более серьезная проблема.
                    # Выводим ошибку и завершаем работу потока.
                    print(f'Критическая ошибка в окне {window_id}. Завершение работы потока.')
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                    driver = None
                    break # Выход из внешнего цикла

        # Этот код выполняется после выхода из внешнего цикла (когда self.stop_event.is_set() становится True)
        # Или при критической ошибке, которая привела к break из внешнего цикла
        if driver:
            try:
                driver.quit()
                print(f'Браузер окна {window_id} закрыт.')
            except:
                pass # Игнорируем ошибки при закрытии драйвера после остановки

    def start_browsers(self):
        self.stop_event.clear() # Сбрасываем событие остановки
        urls = [url.strip() for url in self.urls_entry.get('1.0', 'end-1c').split('\n') if url.strip()]

        if not urls:
            self.status_label.configure(text='Ошибка: введите хотя бы одну ссылку!')
            return

        # Обработка ввода количества окон
        try:
            num_windows_str = self.window_count.get().strip()
            num_windows = int(num_windows_str) if num_windows_str else 4
            if num_windows <= 0:
                 raise ValueError("Количество окон должно быть больше нуля")
        except ValueError:
            self.status_label.configure(text='Ошибка: некорректное число окон!')
            return

        # Обработка ввода интервала обновления
        try:
            refresh_interval_str = self.refresh_entry.get().strip()
            refresh_interval = float(refresh_interval_str) if refresh_interval_str else 2.5
            if refresh_interval <= 0:
                 raise ValueError("Интервал обновления должен быть больше нуля")
        except ValueError:
            self.status_label.configure(text='Ошибка: некорректный интервал обновления!')
            return

        # Обработка ввода размера окна
        try:
            width_str = self.width_entry.get().strip()
            width = int(width_str) if width_str else 860
            height_str = self.height_entry.get().strip()
            height = int(height_str) if height_str else 700
            if width <= 0 or height <= 0:
                 raise ValueError("Размеры окна должны быть больше нуля")
        except ValueError:
            self.status_label.configure(text='Ошибка: некорректный размер окна!')
            return

        # Очищаем список потоков перед запуском
        self.threads.clear()

        # Запускаем потоки браузеров
        for i in range(num_windows):
            url = urls[i % len(urls)] # Циклически используем URL, если окон больше, чем ссылок
            thread = Thread(target=self.browser_instance, args=(url, i + 1, refresh_interval, width, height), daemon=True)
            self.threads.append(thread)
            thread.start()

        self.start_btn.configure(state='disabled')
        self.stop_btn.configure(state='normal')
        self.status_label.configure(text=f'Статус: Запущено {len(self.threads)} окон')

    def stop_browsers(self):
        self.stop_event.set() # Устанавливаем событие остановки
        self.status_label.configure(text='Статус: Остановка...')

        # Ожидаем завершения потоков (с таймаутом)
        start_time = time.time()
        # Проходим по копии списка потоков, так как список может меняться
        for t in list(self.threads):
             if t.is_alive():
                 # join с таймаутом предотвращает зависание, если поток не завершается корректно
                 t.join(timeout=5)
                 if t.is_alive():
                     print(f"Поток {t.name} не завершился в течение таймаута.")

        self.threads.clear() # Очищаем список потоков после попытки остановки

        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.status_label.configure(text='Статус: Остановлено')

    def on_close(self):
        self.stop_browsers() # Останавливаем браузеры при закрытии окна GUI
        self.destroy() # Закрываем окно GUI

if __name__ == '__main__':

    app = BrowserController()
    app.mainloop()
