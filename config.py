import os
import sys

# ЖЕЛЕЗОБЕТОННО: Исправляем SSL-ошибку серверов Google внутри скомпилированного EXE
if getattr(sys, 'frozen', False):
    # Указываем Python искать корневые сертификаты безопасности внутри ресурсов EXE
    cert_path = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
    os.environ["SSL_CERT_FILE"] = cert_path
    os.environ["REQUESTS_CA_BUNDLE"] = cert_path

# Патчи совместимости для speech_recognition
sys.modules['js2py.utils.injector'] = type('sys', (), {'check': lambda *a, **kw: None})()

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Авторизация Tapo Cloud
TP_LINK_EMAIL = "savinb1968@gmail.com"
TP_LINK_PASSWORD = "Termi2107"

TRIGGERS = [
    "шарик", "бобик", "шайтан", "собака", "жарик",
    "жучка", "ручка", "сучка", "сукко", "шлюшка", "бучка", "тучка", "жвачка"
]
