import os
import sys
import asyncio
import base64
import webbrowser
import configparser
import json
import ctypes
from tapo import ApiClient
from config import TP_LINK_EMAIL, TP_LINK_PASSWORD


def decode_name(b64, default):
    try:
        return base64.b64decode(b64, validate=True).decode('utf-8') if b64 else default
    except:
        return str(b64)


class TapoController:
    def __init__(self, app):
        self.app = app
        self.client = ApiClient(TP_LINK_EMAIL, TP_LINK_PASSWORD)
        self._saved_windows = {}
        self.is_music_playing = False

        self.base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            self.config_dir = os.path.dirname(sys.executable)
        else:
            self.config_dir = os.path.dirname(os.path.abspath(__file__))

        self.config_path = os.path.join(self.config_dir, "config.ini")
        self.config = configparser.ConfigParser()

    async def connect_all(self):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding="cp1251")
        else:
            print("⚠️ Файл config.ini не найден!")
            return

        for k in ["P110", "P300", "L535_1", "L535_2", "L920"]:
            if not self.config.has_option("DEVICES", k):
                continue
            ip = self.config.get("DEVICES", k)
            dev_type = "p110" if k == "P110" else "p300" if k == "P300" else "strip" if k == "L920" else "bulb"

            try:
                if dev_type == "p110":
                    h = await self.client.p110(ip)
                    self.app.handlers[k] = h
                    inf = await h.get_device_info_json()
                    self.app.set_btn(self.app.ui_elements[k]["btn"], None, inf.get('device_on', False))
                    asyncio.run_coroutine_threadsafe(self.p110_loop(k), self.app.loop)

                elif dev_type == "bulb":
                    h = await self.client.l530(ip)
                    self.app.handlers[k] = h
                    inf = await h.get_device_info_json()
                    self.app.set_btn(self.app.ui_elements[k]["btn"], None, inf.get('device_on', False))
                    self.app.ui_elements[k]["sld_bright"].set(int(inf.get('brightness', 50)))

                elif dev_type == "strip":
                    h = await self.client.l530(ip)
                    self.app.handlers[k] = h
                    inf = await h.get_device_info_json()
                    self.app.set_btn(self.app.ui_elements[k]["btn"], None, inf.get('device_on', False))
                    self.app.ui_elements[k]["sld_bright"].set(int(inf.get('brightness', 50)))
                    try:
                        color_temp = inf.get('color_temp', 4000)
                        if color_temp > 0 and self.app.ui_elements[k]["sld_temp"]:
                            self.app.ui_elements[k]["sld_temp"].set(int(color_temp))
                    except:
                        pass

                elif dev_type == "p300":
                    h = await self.client.p300(ip)
                    self.app.handlers[k] = h
                    data = await h.get_child_device_list_json()
                    slots = data if isinstance(data, list) else data.get('child_device_list', [])
                    self.app.p300_slots = [c['device_id'] for c in slots if 'device_id' in c]

                    for i, child in enumerate(slots):
                        if i < 3:
                            ui = self.app.ui_elements[k]["slots"][i]
                            self.app.set_btn(ui["btn"], None, child.get('device_on', False))
                            self.app.slot_names[i] = decode_name(child.get('nickname', ''), f"Слот №{i + 1}")
                    if hasattr(self.app, 'tray') and self.app.tray.tray_icon:
                        self.app.tray.tray_icon.update_menu()
                self.app.update_idletasks()
            except Exception as e:
                print(f"[Сеть]: Ошибка инициализации устройства {k}: {e}")

    async def p110_loop(self, key):
        while self.app.is_running:
            if self.app.handlers.get(key):
                try:
                    eng = await self.app.handlers[key].get_energy_usage()
                    if self.app.is_running:
                        current_power = getattr(eng, 'current_power', 0.0)
                        self.app.title(f"📊 {current_power:.2f} Вт")
                        self.app.update_idletasks()
                except Exception as e:
                    print(f"[Ваттметр]: Ошибка обновления заголовка: {e}")
            await asyncio.sleep(3)

    def execute_click_direct(self, key, turn_on):
        h = self.app.handlers.get(key)
        if h:
            async def act():
                if turn_on:
                    await h.on()
                else:
                    await h.off()
                self.app.set_btn(self.app.ui_elements[key]["btn"], None, turn_on)
                self.app.update_idletasks()

            asyncio.run_coroutine_threadsafe(act(), self.app.loop)

    def execute_click_p300(self, idx, turn_on):
        h = self.app.handlers.get("P300")
        if h and len(self.app.p300_slots) > idx:
            async def act():
                slot = await h.plug(self.app.p300_slots[idx])
                if turn_on:
                    await slot.on()
                else:
                    await slot.off()
                self.app.set_btn(self.app.ui_elements["P300"]["slots"][idx]["btn"], None, turn_on)
                self.app.update_idletasks()

            asyncio.run_coroutine_threadsafe(act(), self.app.loop)

    def execute_slide(self, key, value):
        h = self.app.handlers.get(key)
        if h: asyncio.run_coroutine_threadsafe(h.set_brightness(int(value)), self.app.loop)

    def execute_fx(self, temp):
        h = self.app.handlers.get("L920")
        if h: asyncio.run_coroutine_threadsafe(h.set_color_temperature(temp),
                                               self.app.loop); self.app.update_idletasks()

    async def run_macro(self, macro_type):
        if os.path.exists(self.config_path):
            self.config.read(self.config_path, encoding="cp1251")

        if macro_type == "bad_dog":
            self.app.write_log("🚨 Режим 'Плохая собака'! Тотальный сброс...")
            os.system("taskkill /f /im wscript.exe >nul 2>&1")
            self.is_music_playing = False

            if self.app.handlers.get("P110"): await self.app.handlers["P110"].off()
            if self.app.handlers.get("L535_1"): await self.app.handlers["L535_1"].off()
            if self.app.handlers.get("L535_2"): await self.app.handlers["L535_2"].off()
            if self.app.handlers.get("L920"): await self.app.handlers["L920"].off()
            if self.app.handlers.get("P300"):
                for s_id in self.app.p300_slots:
                    slot = await self.app.handlers["P300"].plug(s_id);
                    await slot.off()

            for k in ["P110", "P300", "L535_1", "L535_2", "L920"]:
                if k == "P300":
                    for ui in self.app.ui_elements[k]["slots"]: self.app.set_btn(ui["btn"], None, False)
                else:
                    self.app.set_btn(self.app.ui_elements[k]["btn"], None, False)

            wav_path = os.path.abspath(os.path.join(self.base_path, "dog.wav"))
            if os.path.exists(wav_path):
                ctypes.windll.winmm.PlaySoundW(wav_path, None, 0x20002)
            return
        elif macro_type == "away":
            os.system("taskkill /f /im wscript.exe >nul 2>&1")
            self.is_music_playing = False

            if self.app.handlers.get("P110"): await self.app.handlers["P110"].off()
            if self.app.handlers.get("L535_1"): await self.app.handlers["L535_1"].off()
            if self.app.handlers.get("L535_2"): await self.app.handlers["L535_2"].off()
            if self.app.handlers.get("L920"): await self.app.handlers["L920"].off()
            if self.app.handlers.get("P300"):
                for s_id in self.app.p300_slots:
                    slot = await self.app.handlers["P300"].plug(s_id);
                    await slot.off()

            for k in ["P110", "P300", "L535_1", "L535_2", "L920"]:
                if k == "P300":
                    for ui in self.app.ui_elements[k]["slots"]: self.app.set_btn(ui["btn"], None, False)
                else:
                    self.app.set_btn(self.app.ui_elements[k]["btn"], None, False)

            # ИСПРАВЛЕНО: Перед тушением экранов фиксируем раскладку окон в config.ini
            self.manage_windows_positions("save")

            # ИСПРАВЛЕНО: Отправляем системную команду Windows на мгновенное отключение мониторов
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
            return

        elif macro_type == "cinema":
            if self.app.handlers.get("L535_1"): await self.app.handlers["L535_1"].off()
            if self.app.handlers.get("L535_2"): await self.app.handlers["L535_2"].off()
            if self.app.handlers.get("L920"):
                await self.app.handlers["L920"].on();
                await self.app.handlers["L920"].set_brightness(20);
                await self.app.handlers["L920"].set_color_temperature(2500)
            self.app.set_btn(self.app.ui_elements["L535_1"]["btn"], None, False)
            self.app.set_btn(self.app.ui_elements["L535_2"]["btn"], None, False)
            self.app.set_btn(self.app.ui_elements["L920"]["btn"], None, True)
            self.app.ui_elements["L920"]["sld_bright"].set(20)
            if self.app.ui_elements["L920"]["sld_temp"]: self.app.ui_elements["L920"]["sld_temp"].set(2500)
            return

        elif macro_type == "home":
            if self.app.handlers.get("L535_1"): await self.app.handlers["L535_1"].on()
            if self.app.handlers.get("L535_2"): await self.app.handlers["L535_2"].on()
            if self.app.handlers.get("L920"): await self.app.handlers["L920"].on()
            self.app.set_btn(self.app.ui_elements["L535_1"]["btn"], None, True)
            self.app.set_btn(self.app.ui_elements["L535_2"]["btn"], None, True)
            self.app.set_btn(self.app.ui_elements["L920"]["btn"], None, True)
            return

        elif macro_type == "music":
            mp3_path = os.path.abspath(os.path.join(self.base_path, "music.mp3"))
            if not self.is_music_playing:
                vbs_cmd = (
                    f'Set wmp = CreateObject("WMPlayer.OCX")\n'
                    f'wmp.URL = "{mp3_path.replace("\\", "\\\\")}"\n'
                    f'wmp.settings.setMode "loop", True\n'
                    f'wmp.settings.volume = 100\n'
                    f'wmp.controls.play\n'
                    f'Set fso = CreateObject("Scripting.FileSystemObject")\n'
                    f'vol_file = "{os.path.join(self.base_path, "vol.txt").replace("\\", "\\\\")}"\n'
                    f'Do While wmp.playState <> 1\n'
                    f'  If fso.FileExists(vol_file) Then\n'
                    f'    On Error Resume Next\n'
                    f'    Set f = fso.OpenTextFile(vol_file, 1)\n'
                    f'    v = CInt(f.ReadAll)\n'
                    f'    f.Close\n'
                    f'    If v >= 0 And v <= 100 Then wmp.settings.volume = v\n'
                    f'  End If\n'
                    f'  WScript.Sleep 50\n'
                    f'Loop'
                )
                self.vbs_path = os.path.join(self.base_path, "play_music.vbs")
                with open(self.vbs_path, "w", encoding="cp1251") as f:
                    f.write(vbs_cmd)
                with open(os.path.join(self.base_path, "vol.txt"), "w") as f:
                    f.write("100")
                os.startfile(self.vbs_path)
                self.is_music_playing = True
                print("🎵 Плеер Windows Media: Воспроизведение запущенного music.mp3 со звуком!")
            else:
                os.system("taskkill /f /im wscript.exe >nul 2>&1")
                try:
                    if os.path.exists(self.vbs_path): os.remove(self.vbs_path)
                    vol_file = os.path.join(self.base_path, "vol.txt")
                    if os.path.exists(vol_file): os.remove(vol_file)
                except:
                    pass
                self.is_music_playing = False
                print("🔇 Плеер Windows Media: Воспроизведение остановлено.")
            return

        elif macro_type == "night":
            if self.app.handlers.get("L535_1"): await self.app.handlers["L535_1"].off()
            if self.app.handlers.get("L535_2"): await self.app.handlers["L535_2"].off()
            if self.app.handlers.get("L920"):
                await self.app.handlers["L920"].on();
                await self.app.handlers["L920"].set_brightness(50);
                await self.app.handlers["L920"].set_color_temperature(4000)
            self.app.set_btn(self.app.ui_elements["L535_1"]["btn"], None, False)
            self.app.set_btn(self.app.ui_elements["L535_2"]["btn"], None, False)
            self.app.set_btn(self.app.ui_elements["L920"]["btn"], None, True)
            self.app.ui_elements["L920"]["sld_bright"].set(50)
            if self.app.ui_elements["L920"]["sld_temp"]: self.app.ui_elements["L920"]["sld_temp"].set(4000)
            return

        elif macro_type == "monitors_off":
            self.manage_windows_positions("save")
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
            return

    def set_music_volume(self, value):
        if self.is_music_playing:
            try:
                vol_file = os.path.join(self.base_path, "vol.txt")
                with open(vol_file, "w") as f:
                    f.write(str(int(value)))
            except:
                pass

    def manage_windows_positions(self, action="save"):
        if os.path.exists(self.config_path): self.config.read(self.config_path, encoding="cp1251")
        if not hasattr(self, '_saved_windows') or self._saved_windows is None: self._saved_windows = {}

        if action == "save":
            self._saved_windows.clear()

            def enum_windows_proc(hwnd, lParam):
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        rect = RECT()
                        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        width = rect.right - rect.left
                        height = rect.bottom - rect.top
                        self._saved_windows[hwnd] = (rect.left, rect.top, width, height)
                return True

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
            if not self.config.has_section("WINDOWS"): self.config.add_section("WINDOWS")
            serializable_data = {str(hwnd): coords for hwnd, coords in self._saved_windows.items()}
            self.config.set("WINDOWS", "layout_data", json.dumps(serializable_data))
            with open(self.config_path, "w", encoding="cp1251") as configfile:
                self.config.write(configfile)
            print(f"💾 Раскладка окон зафиксирована в config.ini ({len(self._saved_windows)} шт.)")
            return

        elif action == "restore":
            if not self.config.has_option("WINDOWS", "layout_data"): return
            try:
                serializable_data = json.loads(self.config.get("WINDOWS", "layout_data"))
                self._saved_windows = {int(hwnd): tuple(coords) for hwnd, coords in serializable_data.items()}
            except:
                return
            if not self._saved_windows: return
            restored_count = 0
            for hwnd, (x, y, w, h) in self._saved_windows.items():
                if ctypes.windll.user32.IsWindow(hwnd) and ctypes.windll.user32.IsWindowVisible(hwnd):
                    ctypes.windll.user32.MoveWindow(hwnd, x, y, w, h, True)
                    restored_count += 1
            print(f"🔄 Окна восстановлены из INI ({restored_count} шт.)")
            return
