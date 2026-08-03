# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all

block_cipher = None

# Базовый список картинок, музыки и иконок проекта (строго кортежи из 2 элементов)
datas = [
    ('icon.ico', '.'),
    ('music.mp3', '.'),
    ('dog.wav', '.'),
    ('dog.png', '.'),
    ('fan.png', '.'),
    ('plug1.png', '.'),
    ('plug2.png', '.'),
    ('plug3.png', '.'),
    ('bulb1.png', '.'),
    ('bulb2.png', '.'),
    ('strip.png', '.'),
    ('m_away.png', '.'),
    ('m_cinema.png', '.'),
    ('m_home.png', '.'),
    ('m_music.png', '.'),
    ('m_night.png', '.'),
    ('m_monitors.png', '.')
]

binaries = []
hiddenimports = ['win32com', 'win32com.client', 'ctypes']

# Автоматически собираем ВСЕ скрытые пакеты данных, DLL и FLAC для аудио-движков
for module_name in ['speech_recognition', 'sounddevice', 'certifi']:
    info = collect_all(module_name)
    datas += info[0]        # Вытаскиваем datas
    binaries += info[1]     # Вытаскиваем binaries
    hiddenimports += info[2] # Вытаскиваем hiddenimports

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SmartHome',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Полностью прячем черное окно консоли
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
