"""
Главный файл приложения - генератор договоров
"""
import os
import re
import sys
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime

# Устанавливаем кодировку для Windows
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

# Добавляем текущую директорию в путь для импорта
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    import config
    from contract_filler import (
        load_company_data, 
        get_company_info, 
        fill_template,
        generate_contract_number
    )
except ImportError as e:
    # В режиме GUI показываем сообщение в окне
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()  # Скрываем главное окно
        messagebox.showerror(
            "Ошибка импорта",
            f"Не удалось загрузить модули:\n\n{str(e)}\n\n"
            "Убедитесь, что файлы config.py и contract_filler.py "
            "находятся в одной папке с программой."
        )
        root.destroy()
    except:
        pass
    sys.exit(1)


class ContractGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Генератор договоров B2B")
        self.root.geometry("850x750")
        self.root.minsize(750, 650)
        
        # Переменные
        self.template_path = tk.StringVar()
        self.company_file = tk.StringVar()
        self.company_data = None
        self.contract_number = tk.StringVar()
        
        # Создаем интерфейс
        self.create_widgets()
        
        # Принудительное отображение окна
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        
        # Центрируем окно
        self.center_window()
        
        # Обновляем canvas после создания
        self.root.after(100, self._force_redraw)
        
    def center_window(self):
        """Центрирование окна на экране"""
        try:
            self.root.update_idletasks()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            
            if width < 100 or height < 100:
                width = 850
                height = 750
            
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except:
            pass
        
    def _force_redraw(self):
        """Принудительная перерисовка интерфейса"""
        try:
            self.canvas.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self._on_resize(None)
            self.root.update()
            self.root.update_idletasks()
            self.center_window()
            self.root.after(1000, self._update_canvas)
        except Exception as e:
            print(f"Ошибка перерисовки: {e}")
    
    def _update_canvas(self):
        """Обновление canvas после полной загрузки"""
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            self.root.update_idletasks()
        except:
            pass
        
    def create_widgets(self):
        """Создание интерфейса с прокруткой"""
        
        # Создаем главный контейнер с прокруткой
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Canvas для прокрутки
        self.canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Фрейм, который будет прокручиваться
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Помещаем фрейм в canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Упаковываем canvas и scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Привязываем колесо мыши для прокрутки
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        
        # При изменении размера окна обновляем canvas
        self.root.bind("<Configure>", self._on_resize)
        
        # Создаем содержимое во фрейме с прокруткой
        self.create_content()
        
        # Принудительно обновляем canvas
        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_mousewheel(self, event):
        """Обработка колеса мыши для прокрутки"""
        try:
            if hasattr(event, 'num'):
                if event.num == 4:
                    self.canvas.yview_scroll(-2, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(2, "units")
            else:
                delta = -1 if event.delta > 0 else 1
                self.canvas.yview_scroll(delta, "units")
        except:
            pass
    
    def _on_resize(self, event):
        """Обновление ширины canvas при изменении размера окна"""
        try:
            if event is None or event.widget == self.root:
                width = self.canvas.winfo_width()
                if width > 10:
                    self.canvas.itemconfig(self.canvas_window, width=width)
        except:
            pass
    
    def create_content(self):
        """Создание содержимого внутри прокручиваемого фрейма"""
        main_frame = ttk.Frame(self.scrollable_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок
        title_label = ttk.Label(
            main_frame, 
            text="🤖 Генератор договоров B2B",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Шаг 1: Шаблон
        template_frame = ttk.LabelFrame(main_frame, text="Шаг 1: Выберите шаблон договора", padding="15")
        template_frame.pack(fill=tk.X, pady=(0, 15))
        
        template_row = ttk.Frame(template_frame)
        template_row.pack(fill=tk.X)
        
        template_path_entry = ttk.Entry(template_row, textvariable=self.template_path, width=60)
        template_path_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        template_btn = ttk.Button(
            template_row, 
            text="📁 Выбрать шаблон",
            command=self.select_template
        )
        template_btn.pack(side=tk.RIGHT)
        
        # Шаг 2: Карточка
        company_frame = ttk.LabelFrame(main_frame, text="Шаг 2: Выберите карточку компании", padding="15")
        company_frame.pack(fill=tk.X, pady=(0, 15))
        
        company_row = ttk.Frame(company_frame)
        company_row.pack(fill=tk.X)
        
        company_entry = ttk.Entry(company_row, textvariable=self.company_file, width=60)
        company_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        company_btn = ttk.Button(
            company_row, 
            text="📂 Выбрать карточку",
            command=self.select_company_file
        )
        company_btn.pack(side=tk.RIGHT)
        
        # Шаг 3: Информация о компании
        info_frame = ttk.LabelFrame(main_frame, text="Шаг 3: Информация о компании", padding="15")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.info_text = scrolledtext.ScrolledText(
            info_frame, 
            height=14, 
            wrap=tk.WORD,
            font=("Courier", 10)
        )
        self.info_text.pack(fill=tk.BOTH, expand=True)
        
        # Шаг 4: Номер договора
        contract_frame = ttk.LabelFrame(main_frame, text="Шаг 4: Номер договора", padding="15")
        contract_frame.pack(fill=tk.X, pady=(0, 15))
        
        contract_row = ttk.Frame(contract_frame)
        contract_row.pack(fill=tk.X)
        
        contract_label = ttk.Label(contract_row, text="Номер:", font=("Arial", 10))
        contract_label.pack(side=tk.LEFT, padx=(0, 10))
        
        contract_entry = ttk.Entry(contract_row, textvariable=self.contract_number, width=40, font=("Arial", 10))
        contract_entry.pack(side=tk.LEFT, padx=(0, 10), fill=tk.X, expand=True)
        
        generate_btn = ttk.Button(
            contract_row,
            text="🔄 Сгенерировать новый номер",
            command=self.generate_new_number
        )
        generate_btn.pack(side=tk.LEFT)
        
        # Шаг 5: Настройки
        options_frame = ttk.LabelFrame(main_frame, text="Шаг 5: Дополнительные настройки", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.auto_open_var = tk.BooleanVar(value=True)
        auto_open_cb = ttk.Checkbutton(
            options_frame,
            text="Автоматически открывать папку с результатом",
            variable=self.auto_open_var
        )
        auto_open_cb.pack(anchor=tk.W)
        
        self.add_date_var = tk.BooleanVar(value=True)
        add_date_cb = ttk.Checkbutton(
            options_frame,
            text="Добавлять дату и время к имени файла",
            variable=self.add_date_var
        )
        add_date_cb.pack(anchor=tk.W)
        
        # Кнопка генерации
        generate_frame = ttk.Frame(main_frame)
        generate_frame.pack(fill=tk.X, pady=(10, 20))
        
        self.generate_btn = ttk.Button(
            generate_frame,
            text="🚀 Сгенерировать договор",
            command=self.generate_contract,
            state=tk.DISABLED,
            width=30
        )
        self.generate_btn.pack(pady=10)
        
        # Статус
        self.status_label = ttk.Label(
            main_frame, 
            text="✅ Готов к работе",
            foreground="green",
            font=("Arial", 10)
        )
        self.status_label.pack(pady=(0, 10))
        
        # Подсказка
        help_frame = ttk.Frame(main_frame)
        help_frame.pack(fill=tk.X, pady=(10, 0))
        
        help_text = """💡 Подсказка:
• Используйте {имя_поля} в шаблоне для автоматической замены
• Поддерживаются колонтитулы (верхние и нижние)
• Дата автоматически преобразуется в формат "дд месяц гггг"
• Для прокрутки используйте колесо мыши"""
        
        help_label = ttk.Label(
            help_frame,
            text=help_text,
            foreground="gray",
            font=("Arial", 9),
            justify=tk.LEFT
        )
        help_label.pack(anchor=tk.W)
    
    def select_template(self):
        """Выбор шаблона договора"""
        try:
            if not os.path.exists(config.TEMPLATES_DIR):
                os.makedirs(config.TEMPLATES_DIR)
                
            file_path = filedialog.askopenfilename(
                title="Выберите шаблон договора",
                filetypes=[("Word документы", "*.docx"), ("Все файлы", "*.*")],
                initialdir=config.TEMPLATES_DIR
            )
            if file_path:
                self.template_path.set(file_path)
                self.check_ready()
                self.update_status(f"✅ Шаблон выбран: {os.path.basename(file_path)}", "green")
        except Exception as e:
            self.update_status(f"❌ Ошибка: {str(e)}", "red")
            messagebox.showerror("Ошибка", str(e))
    
    def select_company_file(self):
        """Выбор файла с карточкой компании"""
        try:
            if not os.path.exists(config.DATA_DIR):
                os.makedirs(config.DATA_DIR)
                
            file_path = filedialog.askopenfilename(
                title="Выберите карточку компании",
                filetypes=[("Excel файлы", "*.xlsx *.xls"), ("Все файлы", "*.*")],
                initialdir=config.DATA_DIR
            )
            if file_path:
                self.company_file.set(file_path)
                self.load_company_data(file_path)
                self.check_ready()
                self.update_status(f"✅ Карточка загружена: {os.path.basename(file_path)}", "green")
        except Exception as e:
            self.update_status(f"❌ Ошибка: {str(e)}", "red")
            messagebox.showerror("Ошибка", str(e))
    
    def load_company_data(self, file_path):
        """Загрузка и отображение данных компании"""
        try:
            data = load_company_data(file_path)
            self.company_data = get_company_info(data)
            
            if self.company_data.get('contract_number'):
                self.contract_number.set(self.company_data['contract_number'])
            
            self.info_text.config(state=tk.NORMAL)
            self.info_text.delete(1.0, tk.END)
            
            info_str = "=" * 70 + "\n"
            info_str += "📋 ИНФОРМАЦИЯ О КОМПАНИИ\n"
            info_str += "=" * 70 + "\n\n"
            
            groups = [
                ("Основная информация", [
                    ('Форма собственности', 'ownership_form'),
                    ('Наименование компании', 'company_name'),
                    ('Юридический адрес', 'legal_address'),
                    ('Почтовый адрес', 'postal_address'),
                ]),
                ("Регистрационные данные", [
                    ('ОГРН', 'ogrn'),
                    ('ИНН', 'inn'),
                    ('КПП', 'kpp'),
                ]),
                ("Банковские реквизиты", [
                    ('Расчетный счет', 'bank_account'),
                    ('Корреспондентский счет', 'corr_account'),
                    ('Банк', 'bank_name'),
                    ('БИК', 'bik'),
                ]),
                ("Контактные данные", [
                    ('Телефон', 'phone'),
                    ('E-mail', 'email'),
                    ('Домены заказчика', 'domains'),
                ]),
                ("Подписант", [
                    ('ФИО полное', 'signatory_full'),
                    ('ФИО кратко', 'signatory_short'),
                    ('Должность', 'signatory_position'),
                    ('Пол', 'signatory_gender'),
                    ('Действует на основании', 'based_on'),
                ]),
                ("ЭДО", [
                    ('Поставщик ЭДО', 'edo_provider'),
                ]),
                ("Договор", [
                    ('Номер договора', 'contract_number'),
                    ('Дата договора', 'contract_date_formatted'),
                    ('Срок действия, лет', 'contract_term_years'),
                    ('Дата окончания', 'contract_end_date_formatted'),
                ]),
            ]
            
            for group_name, fields in groups:
                info_str += f"\n{group_name}:\n"
                info_str += "-" * 50 + "\n"
                for display_name, field_name in fields:
                    value = self.company_data.get(field_name, '')
                    if value:
                        info_str += f"  {display_name}: {value}\n"
                    else:
                        info_str += f"  {display_name}: [не указано]\n"
            
            self.info_text.insert(1.0, info_str)
            self.info_text.config(state=tk.DISABLED)
            
        except Exception as e:
            self.update_status(f"❌ Ошибка загрузки данных: {str(e)}", "red")
            messagebox.showerror("Ошибка", f"Не удалось загрузить данные компании:\n{str(e)}")
    
    def generate_new_number(self):
        """Генерация нового номера договора"""
        try:
            new_number = generate_contract_number()
            self.contract_number.set(new_number)
            self.update_status(f"🔄 Сгенерирован новый номер: {new_number}", "blue")
        except Exception as e:
            self.update_status(f"❌ Ошибка генерации номера: {str(e)}", "red")
            messagebox.showerror("Ошибка", str(e))
    
    def generate_contract(self):
        """Генерация заполненного договора"""
        try:
            if not self.template_path.get():
                messagebox.showerror("Ошибка", "Выберите шаблон договора")
                return
            
            if not self.company_data:
                messagebox.showerror("Ошибка", "Загрузите данные компании")
                return
            
            self.company_data['contract_number'] = self.contract_number.get()
            
            company_name = self.company_data.get('company_name', 'company')
            company_name = re.sub(r'[<>:"/\\|?*]', '_', company_name)
            
            if not os.path.exists(config.OUTPUT_DIR):
                os.makedirs(config.OUTPUT_DIR)
            
            if self.add_date_var.get():
                now = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"{company_name}_договор_{now}.docx"
            else:
                output_filename = f"{company_name}_договор.docx"
            
            output_path = os.path.join(config.OUTPUT_DIR, output_filename)
            
            counter = 1
            base_name = output_path.replace('.docx', '')
            while os.path.exists(output_path):
                output_path = f"{base_name}_{counter}.docx"
                counter += 1
            
            self.update_status("⏳ Генерация договора... (включая колонтитулы)", "orange")
            self.root.update()
            
            fill_template(
                self.template_path.get(),
                self.company_data,
                output_path
            )
            
            self.update_status(f"✅ Договор создан: {os.path.basename(output_path)}", "green")
            
            if self.auto_open_var.get():
                try:
                    os.startfile(config.OUTPUT_DIR)
                except:
                    messagebox.showinfo("Успешно", 
                        f"Договор создан!\n\nФайл: {os.path.basename(output_path)}\n\nПапка: {config.OUTPUT_DIR}")
            else:
                if messagebox.askyesno("Успешно", 
                    f"Договор создан!\n\nФайл: {os.path.basename(output_path)}\n\nОткрыть папку с результатом?"):
                    try:
                        os.startfile(config.OUTPUT_DIR)
                    except:
                        messagebox.showinfo("Информация", 
                            f"Файл сохранен в: {config.OUTPUT_DIR}")
            
        except Exception as e:
            self.update_status(f"❌ Ошибка при создании договора: {str(e)}", "red")
            messagebox.showerror("Ошибка", f"Не удалось создать договор:\n{str(e)}")
    
    def check_ready(self):
        """Проверка готовности к генерации"""
        try:
            if self.template_path.get() and self.company_data:
                self.generate_btn.config(state=tk.NORMAL)
                self.update_status("✅ Готов к генерации", "green")
            else:
                self.generate_btn.config(state=tk.DISABLED)
                if not self.template_path.get() and not self.company_data:
                    self.update_status("⏳ Выберите шаблон и карточку компании", "orange")
                elif not self.template_path.get():
                    self.update_status("⏳ Выберите шаблон договора", "orange")
                else:
                    self.update_status("⏳ Загрузите карточку компании", "orange")
        except:
            self.generate_btn.config(state=tk.DISABLED)
            self.update_status("⏳ Ожидание данных", "orange")
    
    def update_status(self, message, color="black"):
        """Обновление статуса"""
        try:
            self.status_label.config(text=message, foreground=color)
            self.root.update_idletasks()
        except:
            pass


def main():
    """Запуск приложения"""
    try:
        root = tk.Tk()
        
        # Устанавливаем иконку если есть
        try:
            root.iconbitmap(default='icon.ico')
        except:
            pass
        
        app = ContractGeneratorApp(root)
        root.mainloop()
        
    except Exception as e:
        import traceback
        error_msg = f"Критическая ошибка:\n{str(e)}\n\n{traceback.format_exc()}"
        try:
            messagebox.showerror("Ошибка запуска", error_msg)
        except:
            print(error_msg)


if __name__ == "__main__":
    main()