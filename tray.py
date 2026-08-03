import threading
import pystray
from pystray import MenuItem as item
from PIL import Image


class TrayIconController:
    def __init__(self, app):
        self.app = app
        self.tray_icon = None

    def start(self):
        try:
            image = Image.open("icon.ico")
        except:
            image = Image.new('RGB', (64, 64), color='white')

        def ui_save_layout():
            self.app.tapo.manage_windows_positions("save")

        def ui_restore_layout():
            self.app.tapo.manage_windows_positions("restore")

        menu = (
            item('Развернуть окно', lambda: self.app.deiconify(), default=True),
            item('Лог', lambda: self.app.after(0, self.app.show_log_window)),
            pystray.Menu.SEPARATOR,

            # Вентилятор P110
            item('Вентилятор', pystray.Menu(
                item('Включить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("P110", True))),
                item('Выключить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("P110", False)))
            )),

            pystray.Menu.SEPARATOR,

            # УЛУЧШЕНО: Разделили P300 на 3 отдельных пункта верхнего уровня с динамическими именами устройств
            item(lambda io: self.app.slot_names[0], pystray.Menu(
                item('Включить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_p300(0, True))),
                item('Выключить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_p300(0, False)))
            )),
            item(lambda io: self.app.slot_names[1], pystray.Menu(
                item('Включить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_p300(1, True))),
                item('Выключить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_p300(1, False)))
            )),
            item(lambda io: self.app.slot_names[2], pystray.Menu(
                item('Включить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_p300(2, True))),
                item('Выключить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_p300(2, False)))
            )),

            pystray.Menu.SEPARATOR,

            # Лампы L535 и лента L920
            item('Первая лампа', pystray.Menu(
                item('Включить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("L535_1", True))),
                item('Выключить',
                     lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("L535_1", False)))
            )),
            item('Вторая лампа', pystray.Menu(
                item('Включить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("L535_2", True))),
                item('Выключить',
                     lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("L535_2", False)))
            )),
            item('Светодиодная лента', pystray.Menu(
                item('Включить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("L920", True))),
                item('Выключить', lambda: self.app.after(0, lambda: self.app.tapo.execute_click_direct("L920", False))),
                item('Режим: Тёплый свет', lambda: self.app.after(0, lambda: self.app.tapo.execute_fx(2500))),
                item('Режим: Дневной свет', lambda: self.app.after(0, lambda: self.app.tapo.execute_fx(4000)))
            )),

            pystray.Menu.SEPARATOR,
            item('Сохранить положения окон', lambda: self.app.after(0, ui_save_layout)),
            item('Восстановить положения окон', lambda: self.app.after(0, ui_restore_layout)),
            pystray.Menu.SEPARATOR,
            item('Выход из программы', lambda: self.app.exit_application())
        )
        self.tray_icon = pystray.Icon("SmartHome", image, "Умный Дом Tapo", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def stop(self):
        if self.tray_icon:
            self.tray_icon.stop()
