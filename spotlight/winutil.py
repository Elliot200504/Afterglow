# A few Windows-only tricks through ctypes
import ctypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
kernel32.CreateEventW.restype = ctypes.c_void_p
kernel32.OpenEventW.restype = ctypes.c_void_p

SHOW_EVENT = "SpotLightShowWidget"


def set_app_id():
    # without this windows thinks the widget is just "python" and shows python's icon in the taskbar
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SpotLight.Widget")


def round_corners(hwnd):
    # windows 11 rounds the corners of the frameless window if we ask nicely
    round_ = ctypes.c_int(2)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(round_), 4)


_mutex = None


def already_running():
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, "SpotLightMutex")
    return kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def tell_running_app_to_show():
    event = kernel32.OpenEventW(0x0002, False, SHOW_EVENT)
    if event:
        kernel32.SetEvent(ctypes.c_void_p(event))


def wait_for_show(callback):
    # runs in a thread: every time SpotLight is started again (e.g. the pinned icon), show the widget
    event = kernel32.CreateEventW(None, False, False, SHOW_EVENT)
    while kernel32.WaitForSingleObject(ctypes.c_void_p(event), 0xFFFFFFFF) == 0:
        callback()
