"""Start Windows voice typing into the app's focused request box."""
import ctypes, os
from ctypes import wintypes

def start():
    if os.name!='nt':raise ValueError('Voice typing is available in the Windows desktop app.')
    class Keyboard(ctypes.Structure):
        _fields_=[('vk',wintypes.WORD),('scan',wintypes.WORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Mouse(ctypes.Structure):
        _fields_=[('dx',wintypes.LONG),('dy',wintypes.LONG),('data',wintypes.DWORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Union(ctypes.Union):_fields_=[('ki',Keyboard),('mi',Mouse)]
    class Input(ctypes.Structure):_fields_=[('type',wintypes.DWORD),('value',Union)]
    events=(Input*4)(*[Input(1,Union(ki=Keyboard(vk,0,flags,0,0))) for vk,flags in [(0x5B,0),(0x48,0),(0x48,2),(0x5B,2)]])
    send=ctypes.windll.user32.SendInput;send.argtypes=[wintypes.UINT,ctypes.POINTER(Input),ctypes.c_int];send.restype=wintypes.UINT
    if send(4,events,ctypes.sizeof(Input))!=4:raise ValueError('Windows blocked the microphone shortcut. Click in the request box and press Windows + H.')
    return True
