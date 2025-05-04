import customtkinter as ctk
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from threading import Thread, Event
import time
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

class BrowserController(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('Browser Controller')
        self.geometry('600x500')
        self.stop_event = Event()
        self.threads = []
        self.url_map = {}
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
        while not self.stop_event.is_set():
            driver = None
            try:
                driver = webdriver.Chrome(options=options)
                driver.set_window_size(width, height)
                driver.get(original_url)
                self.url_map[window_id] = original_url
                print(f'Окно {window_id} запущено с URL: {original_url}')
                while not self.stop_event.is_set():
                    pass  # postinserted
            except Exception as e:
                else:  # inserted
                    try:
                        current_url = driver.current_url
                        if current_url!= original_url:
                            print(f'Обнаружен измененный URL в окне {window_id}. Возвращаю исходный...')
                            driver.get(original_url)
                            time.sleep(2)
                        for handle in driver.window_handles:
                            driver.switch_to.window(handle)
                            driver.refresh()
                            print(f'Окно {window_id} обновлено')
                        time.sleep(refresh_interval)
                    except WebDriverException as e:
                        pass  # postinserted
            else:  # inserted
                if driver:
                    try:
                        driver.quit()
            if 'chrome not reachable' in str(e).lower():
                print(f'Окно {window_id} закрыто, перезапускаю...')
                continue
        else:  # inserted
            raise
            print(f'Ошибка в окне {window_id}: {str(e)}')
            time.sleep(5)

    def start_browsers(self):
        self.stop_event.clear()
        urls = [url.strip() for url in self.urls_entry.get('1.0', 'end-1c').split('\n') if url.strip()]
        try:
            num_windows = int(self.window_count.get().strip() or 4)
        except ValueError:
            pass  # postinserted
        else:  # inserted
            if not urls:
                self.status_label.configure(text='Ошибка: введите хотя бы одну ссылку!')
                return
            try:
                refresh_interval = float(self.refresh_entry.get().strip() or 2.5)
        except ValueError:
            else:  # inserted
                try:
                    width = int(self.width_entry.get().strip() or 860)
            except ValueError:
                else:  # inserted
                    try:
                        height = int(self.height_entry.get().strip() or 700)
                except ValueError:
                    else:  # inserted
                        for i in range(num_windows):
                            url = urls[i % len(urls)]
                            thread = Thread(target=self.browser_instance, args=(url, i + 1, refresh_interval, width, height), daemon=True)
            self.status_label.configure(text='Ошибка: некорректное число окон!')
            return None
        else:  # inserted
            pass
            refresh_interval = 2.5
        else:  # inserted
            pass
            width = 860
        else:  # inserted
            pass
            height = 700
        else:  # inserted
            pass

    def stop_browsers(self):
        self.stop_event.set()
        start_time = time.time()
        while time.time() - start_time < 5 and any((t.is_alive() for t in self.threads)):
            time.sleep(0.1)
        self.threads.clear()
        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.status_label.configure(text='Статус: Остановлено')

    def on_close(self):
        self.stop_browsers()
        self.destroy()
if __name__ == '__main__':
    app = BrowserController()
    app.mainloop()