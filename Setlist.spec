# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
a = Analysis(['setlist/app.py'], pathex=['setlist'],
 datas=[('setlist/ui','ui'),('setlist/seeds.json','.'),('setlist/PhotoReader.exe','.')],
 hiddenimports=collect_submodules('mutagen'),excludes=['shazamio','tkinter'],
 binaries=[], hookspath=[], hooksconfig={},runtime_hooks=[],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='Setlist',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,icon=['setlist/setlist.ico'])
