import io
import queue
import threading
import speech_recognition as sr
import sounddevice as sd
import numpy as np
from config import TRIGGERS


class VoiceRecognizer:
    def __init__(self, app):
        self.app = app
        self.audio_queue = queue.Queue()

    def start(self):
        threading.Thread(target=self._recognition_loop, daemon=True).start()

    def _recognition_loop(self):
        recognizer = sr.Recognizer()

        # Надежные стандартные настройки распознавания фразы
        recognizer.dynamic_energy_threshold = True
        recognizer.dynamic_energy_adjustment_damping = 0.15
        recognizer.dynamic_energy_ratio = 1.5

        # Комфортный порог тишины: 0.45 секунды молчания — и звук улетает в сеть
        recognizer.pause_threshold = 0.45
        recognizer.phrase_threshold = 0.15
        recognizer.non_speaking_duration = 0.3

        # Замените старый print в районе 31-й строки первой части voice.py на это:
        self.app.write_log("Голосовой движок (Облачный Google Safe-VAD Core) запущен.")
        self.app.write_log(f"Ожидаю команды для триггеров: {', '.join([t.capitalize() for t in TRIGGERS])}...")

        def audio_callback(indata, frames, time, status):
            if not self.app.is_running:
                raise sd.CallbackStop()
            clipped_data = np.clip(indata * 32767.0, -32768, 32767)
            self.audio_queue.put(clipped_data.astype(np.int16).tobytes())

        phrase_frames = []
        last_silence_chunk = b""  # Хранилище предыдущего кусочка тишины для спасения букв
        is_speaking = False
        silence_counter = 0
        energy_threshold = 350

        with sd.InputStream(device=0, samplerate=16000, channels=1, dtype='float32', callback=audio_callback):
            while self.app.is_running:
                # Стабильный шаг 150мс — исключает любые аппаратные зависания звуковых карт
                sd.sleep(150)
                if not self.app.is_running:
                    break

                chunk_frames = []
                while not self.audio_queue.empty():
                    chunk_frames.append(self.audio_queue.get_nowait())

                if not chunk_frames:
                    continue

                full_chunk = b"".join(chunk_frames)

                audio_data_int = np.frombuffer(full_chunk, dtype=np.int16).astype(np.float64)
                if len(audio_data_int) > 0:
                    current_energy = np.sqrt(np.mean(audio_data_int ** 2))
                else:
                    current_energy = 0

                # Логика VAD детекции голоса
                if current_energy > energy_threshold:
                    if not is_speaking:
                        is_speaking = True
                        # ЖЕЛЕЗОБЕТОННО: Приклеиваем прошлый кусок тишины перед началом речи.
                        # Теперь имя "Бобик" физически невозможно "проглотить" или обрезать при старте!
                        if last_silence_chunk:
                            phrase_frames.append(last_silence_chunk)
                    phrase_frames.append(full_chunk)
                    silence_counter = 0
                else:
                    if is_speaking:
                        phrase_frames.append(full_chunk)
                        silence_counter += 1

                        # 3 цикла по 150мс = ровно 0.45 секунды тишины после фразы
                        if silence_counter > 3:
                            speech_data = b"".join(phrase_frames)
                            phrase_frames = []
                            is_speaking = False
                            silence_counter = 0

                            def send_to_google(audio_bytes):
                                try:
                                    audio_obj = sr.AudioData(audio_bytes, 16000, 2)
                                    text = recognizer.recognize_google(audio_obj, language="ru-RU").lower()
                                    if not text:
                                        return

                                    if any(w in text for w in TRIGGERS):
                                        self.app.write_log(f"[Услышал триггер]: {text}")

                                        # КРИТИЧЕСКИЙ МАКРОС: Перехват команды наказания собаки
                                        if "плохая" in text and "собак" in text:
                                            self.app.run_macro_async("bad_dog")
                                        elif "ушел" in text or "ушёл" in text:
                                            self.app.run_macro_async("away")
                                        elif "кино" in text or "смотрим" in text:
                                            self.app.run_macro_async("cinema")
                                        elif "дома" in text or "пришел" in text or "пришёл" in text:
                                            self.app.run_macro_async("home")
                                        elif "музык" in text:
                                            self.app.run_macro_async("music")
                                        elif "ночн" in text and "работ" in text:
                                            self.app.run_macro_async("night")
                                        elif "монитор" in text or "экран" in text:
                                            self.app.run_macro_async("monitors_off")
                                        else:
                                            is_on = any(w in text for w in
                                                        ["включ", "зажги", "зажгись", "открой", "пусти", "включи"])
                                            is_off = any(w in text for w in
                                                         ["выключ", "погаси", "туши", "закрой", "отключ", "выключи"])
                                            if is_on or is_off:
                                                action = True if is_on else False
                                                if "чайник" in text:
                                                    self.app.tapo.execute_click_p300(0, action)
                                                elif "батаре" in text or "радиатор" in text:
                                                    self.app.tapo.execute_click_p300(1, action)
                                                elif "обогрев" in text:
                                                    self.app.tapo.execute_click_p300(2, action)
                                                elif "вентилятор" in text or "p110" in text:
                                                    self.app.tapo.execute_click_direct("P110", action)
                                                elif "свет" in text or "ламп" in text or "люстр" in text:
                                                    self.app.tapo.execute_click_direct("L535_1", action)
                                                    self.app.tapo.execute_click_direct("L535_2", action)
                                                elif "лент" in text:
                                                    self.app.tapo.execute_click_direct("L920", action)
                                    else:
                                        self.app.write_log(f"[Игнорирую фоновую речь]: {text}")
                                except sr.UnknownValueError:
                                    pass
                                except Exception as e:
                                    if self.app.is_running:
                                        self.app.write_log(f"[Аудио]: Ошибка Google API (Сброшено): {e}")

                            threading.Thread(target=send_to_google, args=(speech_data,), daemon=True).start()
                    else:
                        last_silence_chunk = full_chunk
                        energy_threshold = (energy_threshold * 0.95) + (current_energy * 0.05)
                        if energy_threshold < 150:
                            energy_threshold = 150
