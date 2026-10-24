"""Give this click's foreground permission to the Chrome process owning our pipe.

This does not force focus, change foreground-lock settings, inspect other tabs,
or grant permission to every process. Chrome still selects its exact window.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path


class Windows:
    def __init__(self):
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        for dll,name,args,result in (
            (self.kernel,'GetNamedPipeServerProcessId',[wintypes.HANDLE,ctypes.POINTER(wintypes.ULONG)],wintypes.BOOL),
            (self.kernel,'OpenProcess',[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD],wintypes.HANDLE),
            (self.kernel,'QueryFullProcessImageNameW',[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)],wintypes.BOOL),
            (self.kernel,'CloseHandle',[wintypes.HANDLE],wintypes.BOOL),
            (self.kernel,'CreateToolhelp32Snapshot',[wintypes.DWORD,wintypes.DWORD],wintypes.HANDLE),
            (self.user,'GetForegroundWindow',[],wintypes.HWND),
            (self.user,'GetWindowThreadProcessId',[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)],wintypes.DWORD),
            (self.user,'AllowSetForegroundWindow',[wintypes.DWORD],wintypes.BOOL),
        ):
            fn=getattr(dll,name);fn.argtypes=args;fn.restype=result

    def server_pid(self,handle):
        pid=wintypes.ULONG()
        if not self.kernel.GetNamedPipeServerProcessId(handle,ctypes.byref(pid)):raise ctypes.WinError(ctypes.get_last_error())
        return pid.value

    def process_path(self,pid):
        handle=self.kernel.OpenProcess(0x1000,False,pid)
        if not handle:raise ctypes.WinError(ctypes.get_last_error())
        try:
            length=wintypes.DWORD(32768);value=ctypes.create_unicode_buffer(length.value)
            if not self.kernel.QueryFullProcessImageNameW(handle,0,value,ctypes.byref(length)):raise ctypes.WinError(ctypes.get_last_error())
            return value.value
        finally:self.kernel.CloseHandle(handle)

    def parents(self):
        class Entry(ctypes.Structure):
            _fields_=[('size',wintypes.DWORD),('usage',wintypes.DWORD),('pid',wintypes.DWORD),('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('name',wintypes.WCHAR*260)]
        for name in ('Process32FirstW','Process32NextW'):
            fn=getattr(self.kernel,name);fn.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)];fn.restype=wintypes.BOOL
        snapshot=self.kernel.CreateToolhelp32Snapshot(2,0)
        if snapshot in (None,ctypes.c_void_p(-1).value):raise ctypes.WinError(ctypes.get_last_error())
        result={};entry=Entry();entry.size=ctypes.sizeof(entry)
        try:
            found=self.kernel.Process32FirstW(snapshot,ctypes.byref(entry))
            while found:
                result[entry.pid]=entry.parent
                found=self.kernel.Process32NextW(snapshot,ctypes.byref(entry))
            return result
        finally:self.kernel.CloseHandle(snapshot)

    def foreground_pid(self):
        pid=wintypes.DWORD();self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(),ctypes.byref(pid));return pid.value

    def allow(self,pid):return bool(self.user.AllowSetForegroundWindow(pid))


def handoff(pipe_handle,chrome_path,host_path,api=None,caller_pid=None):
    result={'granted':False,'browserPid':None}
    if not chrome_path or not host_path:return result
    try:
        api=api or Windows();caller_pid=caller_pid or os.getpid()
        expected_chrome=os.path.normcase(os.path.abspath(chrome_path))
        expected_host=os.path.normcase(os.path.abspath(host_path))
        expected_launcher=os.path.normcase(os.path.abspath(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/cmd.exe'))
        if Path(expected_chrome).name.lower()!='chrome.exe':return result
        pid=api.server_pid(pipe_handle);parents=api.parents()
        # Chrome's Windows native-messaging launcher uses cmd.exe; the frozen
        # host adds its own bootloader. Validate the entire observed ancestry.
        for _ in range(4):
            path=os.path.normcase(os.path.abspath(api.process_path(pid)))
            if path==expected_chrome:
                result['browserPid']=pid
                if api.foreground_pid()==caller_pid:result['granted']=api.allow(pid)
                return result
            if path!=expected_host and not (_>0 and path==expected_launcher):return result
            pid=parents.get(pid)
            if not pid:return result
    except (OSError,ValueError,AttributeError):pass
    return result
