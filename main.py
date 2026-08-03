import os
import sys
import asyncio
import threading
import ctypes
import customtkinter as ctk
from PIL import Image
from tapo_core import TapoController, decode_name
from voice import VoiceRecognizer
from tray import TrayIconController

try:
    ctypes.windll.ole32.CoInitialize(None)
except:
    pass


# СИСТЕМНЫЙ КЛАСС: Перехватывает все вызовы print() и дублирует их в графическое окно
class LogRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.stdout = sys.stdout

    def write(self, string):
        # ИСПРАВЛЕНО: Защитный блок. Если программа запущена без консоли (sys.stdout == None),
        # мы просто не пишем в терминал, предотвращая аварийное падение всего приложения.
        if self.stdout is not None:
            try:
                self.stdout.write(string)
            except:
                pass

        if string.strip():
            # Безопасно для фоновых потоков добавляем строку в текстовое поле ctk
            try:
                self.text_widget.configure(state="normal")
                self.text_widget.insert("end", string + "\n")
                self.text_widget.see("end")
                self.text_widget.configure(state="disabled")
            except:
                pass

    def flush(self):
        if self.stdout is not None:
            try:
                self.stdout.flush()
            except:
                pass


class SmartHomeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Умный Дом")
        self.geometry("430x410")
        ctk.set_appearance_mode("dark")
        self.attributes("-alpha", 0.85)

        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        self.wm_iconbitmap(os.path.join(base_path, "icon.ico"))
        self.protocol('WM_DELETE_WINDOW', lambda: self.withdraw())

        self.loop = asyncio.new_event_loop()
        self.tapo = TapoController(self)
        self.voice = VoiceRecognizer(self)
        self.tray = TrayIconController(self)

        self.handlers, self.p300_slots, self.ui_elements = {}, [], {}
        self.slot_names = ["Слот №1", "Слот №2", "Слот №3"]
        self.is_running = True

        self.log_window = None
        self.init_log_window()

        try:
            self.img_fan = ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "fan.png")),
                                        dark_image=Image.open(os.path.join(base_path, "fan.png")), size=(64, 64))
            self.img_slots = [
                ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "plug1.png")),
                             dark_image=Image.open(os.path.join(base_path, "plug1.png")), size=(64, 64)),
                ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "plug2.png")),
                             dark_image=Image.open(os.path.join(base_path, "plug2.png")), size=(64, 64)),
                ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "plug3.png")),
                             dark_image=Image.open(os.path.join(base_path, "plug3.png")), size=(64, 64))
            ]
            self.img_bulb1 = ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "bulb1.png")),
                                          dark_image=Image.open(os.path.join(base_path, "bulb1.png")), size=(64, 64))
            self.img_bulb2 = ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "bulb2.png")),
                                          dark_image=Image.open(os.path.join(base_path, "bulb2.png")), size=(64, 64))
            self.img_strip = ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "strip.png")),
                                          dark_image=Image.open(os.path.join(base_path, "strip.png")), size=(64, 64))

            self.img_macros = {
                "away": ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "m_away.png")),
                                     dark_image=Image.open(os.path.join(base_path, "m_away.png")), size=(64, 64)),
                "cinema": ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "m_cinema.png")),
                                       dark_image=Image.open(os.path.join(base_path, "m_cinema.png")), size=(64, 64)),
                "home": ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "m_home.png")),
                                     dark_image=Image.open(os.path.join(base_path, "m_home.png")), size=(64, 64)),
                "music": ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "m_music.png")),
                                      dark_image=Image.open(os.path.join(base_path, "m_music.png")), size=(64, 64)),
                "night": ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "m_night.png")),
                                      dark_image=Image.open(os.path.join(base_path, "m_night.png")), size=(64, 64)),
                "monitors_off": ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "m_monitors.png")),
                                             dark_image=Image.open(os.path.join(base_path, "m_monitors.png")),
                                             size=(64, 64)),
                "bad_dog": ctk.CTkImage(light_image=Image.open(os.path.join(base_path, "dog.png")),
                                        dark_image=Image.open(os.path.join(base_path, "dog.png")), size=(64, 64))
            }
        except Exception as e:
            print(f"❌ Ошибка иконок: {e}")

        self.left_power_col = ctk.CTkFrame(self, fg_color="transparent")
        self.left_power_col.pack(side="left", fill="both", expand=True, padx=2, pady=10, anchor="n")

        self.middle_light_col = ctk.CTkFrame(self, fg_color="transparent")
        self.middle_light_col.pack(side="left", fill="both", expand=True, padx=2, pady=10, anchor="n")

        self.right_macro_col = ctk.CTkFrame(self, fg_color="transparent")
        self.right_macro_col.pack(side="right", fill="both", expand=True, padx=2, pady=10, anchor="n")

        self.ui_elements["P300"] = {"slots": []}

        for key in ["P110", "P300", "L535_1", "L535_2", "L920"]:
            dev_type = "p110" if key == "P110" else "p300" if key == "P300" else "strip" if key == "L920" else "bulb"
            target_container = self.left_power_col if dev_type in ["p110", "p300"] else self.middle_light_col

            if dev_type == "p300":
                for i in range(3):
                    f = ctk.CTkFrame(target_container, fg_color="transparent")
                    f.pack(pady=4, fill="x", padx=5)
                    b_toggle = ctk.CTkButton(f, text="", image=self.img_slots[i], width=80, height=80, corner_radius=12,
                                             fg_color="#7f8c8d", hover_color="#95a5a6", border_width=2,
                                             border_color="#ffffff",
                                             state="disabled",
                                             command=lambda idx=i: self.tapo.execute_click_p300(idx, self.ui_elements[
                                                 "P300"]["slots"][idx]["btn"].cget("fg_color") == "#7f8c8d"))
                    b_toggle.pack(anchor="center")
                    self.ui_elements[key]["slots"].append({"btn": b_toggle})
            elif dev_type == "p110":
                self.ui_elements[key] = {"lbl": None}
                f = ctk.CTkFrame(target_container, fg_color="transparent")
                f.pack(pady=4, fill="x", padx=5)
                b_toggle = ctk.CTkButton(f, text="", image=self.img_fan, width=80, height=80, corner_radius=12,
                                         fg_color="#7f8c8d", hover_color="#95a5a6", border_width=2,
                                         border_color="#ffffff",
                                         state="disabled",
                                         command=lambda k=key: self.tapo.execute_click_direct(k, self.ui_elements[k][
                                             "btn"].cget("fg_color") == "#7f8c8d"))
                b_toggle.pack(anchor="center")
                self.ui_elements[key]["btn"] = b_toggle
                self.ui_elements[key]["sld_bright"] = None
                self.ui_elements[key]["sld_temp"] = None

            else:
                f = ctk.CTkFrame(target_container, fg_color="transparent")
                f.pack(pady=4, fill="x", padx=5)
                if key == "L535_1":
                    img_target = self.img_bulb1
                elif key == "L535_2":
                    img_target = self.img_bulb2
                else:
                    img_target = self.img_strip

                b_toggle = ctk.CTkButton(f, text="", image=img_target, width=80, height=80, corner_radius=12,
                                         fg_color="#7f8c8d", hover_color="#95a5a6", border_width=2,
                                         border_color="#ffffff",
                                         state="disabled",
                                         command=lambda k=key: self.tapo.execute_click_direct(k, self.ui_elements[k][
                                             "btn"].cget("fg_color") == "#7f8c8d"))
                b_toggle.pack(anchor="center")

                sld_bright = ctk.CTkSlider(target_container, from_=1, to=100, width=100, height=16, corner_radius=8,
                                           fg_color="#2c3e50", progress_color="#3498db",
                                           button_color="#3498db", button_hover_color="#2980b9", button_length=0,
                                           state="disabled", command=lambda v, k=key: self.tapo.execute_slide(k, v))
                sld_bright.pack(pady=4)

                sld_temp = None
                if dev_type == "strip":
                    sld_temp = ctk.CTkSlider(target_container, from_=2500, to=6500, width=100, height=16,
                                             corner_radius=8,
                                             fg_color="#2c3e50", progress_color="#e67e22",
                                             button_color="#e67e22", button_hover_color="#d35400", button_length=0,
                                             state="disabled", command=lambda v: self.tapo.execute_fx(int(v)))
                    sld_temp.pack(pady=2)
                    sld_temp.set(4000)

                self.ui_elements[key] = {"btn": b_toggle, "sld_bright": sld_bright, "sld_temp": sld_temp, "lbl": None}

        # Правая колонка макросов, оптимизированная под размер окна 430x410
        macros = [
            ("away", "m_away"), ("cinema", "m_cinema"),
            ("home", "m_home"), ("music", "m_music"),
            ("night", "m_night"), ("monitors_off", "m_monitors"),
            ("bad_dog", "bad_dog")  # Уникальный ключ под dog.png
        ]

        self.macro_buttons = {}
        row_frames = [
            ctk.CTkFrame(self.right_macro_col, fg_color="transparent"),
            ctk.CTkFrame(self.right_macro_col, fg_color="transparent"),
            ctk.CTkFrame(self.right_macro_col, fg_color="transparent"),
            ctk.CTkFrame(self.right_macro_col, fg_color="transparent")  # 4 ряд для собаки
        ]

        row_frames[0].pack(pady=(4, 10), fill="x")
        row_frames[1].pack(pady=(0, 10), fill="x")
        row_frames[2].pack(pady=(0, 10), fill="x")
        row_frames[3].pack(pady=0, fill="x")

        for idx, (m_type, _) in enumerate(macros):
            row_idx = idx // 2
            target_row = row_frames[row_idx]

            h_color = "#e74c3c" if m_type == "bad_dog" else "#2ecc71"

            btn = ctk.CTkButton(target_row, text="", image=self.img_macros[m_type], width=80, height=80,
                                corner_radius=12,
                                fg_color="#34495e", hover_color=h_color, border_width=2, border_color="#ffffff",
                                command=lambda mt=m_type: self.run_macro_async(mt))
            btn.pack(side="left" if idx % 2 == 0 else "right", padx=4)
            self.macro_buttons[m_type] = btn

        self.tray.start()
        self.voice.start()
        threading.Thread(target=lambda: (asyncio.set_event_loop(self.loop), self.loop.run_forever()),
                         daemon=True).start()
        asyncio.run_coroutine_threadsafe(self.tapo.connect_all(), self.loop)

    def init_log_window(self):
        self.log_window = ctk.CTkToplevel(self)
        self.log_window.title("Консоль: Логи Умного Дома")
        self.log_window.geometry("550x380")
        self.log_window.configure(fg_color="#1a1a1a")

        self.log_window.attributes("-alpha", 1.0)
        self.log_window.protocol("WM_DELETE_WINDOW", lambda: self.log_window.withdraw())

        self.log_text = ctk.CTkTextbox(self.log_window, fg_color="#111111", text_color="#2ecc71", font=("Consolas", 13),
                                       corner_radius=8)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.log_text.configure(state="disabled")

        sys.stdout = LogRedirector(self.log_text)
        self.log_window.withdraw()
        self.write_log("Система Умного Дома успешно инициализирована.")

    def write_log(self, string):
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", string + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except:
            pass

    def show_log_window(self):
        if self.log_window:
            self.log_window.deiconify()
            self.log_window.focus_force()

    def set_btn(self, b_on, b_off, is_on):
        try:
            b_on.configure(state="normal")
            if is_on:
                b_on.configure(fg_color="#2ecc71", hover_color="#27ae60", border_color="#ffffff")
            else:
                b_on.configure(fg_color="#7f8c8d", hover_color="#95a5a6", border_color="#333333")

            for key, ui in self.ui_elements.items():
                if key != "P300" and ui.get("btn") == b_on:
                    new_state = "normal" if is_on else "disabled"
                    if ui.get("sld_bright"): ui["sld_bright"].configure(state=new_state)
                    if ui.get("sld_temp"): ui["sld_temp"].configure(state=new_state)
                    break
        except:
            pass

    def run_macro_async(self, macro_type):
        def run():
            btn_color = "#e74c3c" if macro_type == "bad_dog" else "#2ecc71"
            if macro_type in self.macro_buttons:
                self.macro_buttons[macro_type].configure(fg_color=btn_color)
            future = asyncio.run_coroutine_threadsafe(self.tapo.run_macro(macro_type), self.loop)
            future.result()
            if macro_type in self.macro_buttons:
                self.macro_buttons[macro_type].configure(fg_color="#34495e")

        threading.Thread(target=run, daemon=True).start()

    def exit_application(self):
        self.is_running = False;
        self.withdraw()
        self.tray.stop()
        try:
            self.loop.call_soon_threadsafe(self.loop.stop); self.after(100, self.destroy)
        except:
            pass


if __name__ == "__main__":
    SmartHomeApp().mainloop()
