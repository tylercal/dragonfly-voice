#
# This file is a command-module for Dragonfly.
# (c) Copyright 2008 by Christo Butcher
# Licensed under the LGPL, see <http://www.gnu.org/licenses/>
#

"""
Command-module loader for WSR
=============================

This script can be used to look Dragonfly command-modules 
for use with Window Speech Recognition.  It scans the 
directory it's in and loads any ``*.py`` it finds.

"""
import ctypes
import ctypes.wintypes

import time
import os.path
import win32con
from dragonfly import Window
import pythoncom

import logging
import dragonfly.engines
engine = dragonfly.engines.get_engine('sapi5')


#---------------------------------------------------------------------------
# Command module class; wraps a single command-module.

class CommandModule(object):

    _log = logging.getLogger("module")

    def __init__(self, path):
        self._path = os.path.abspath(path)
        self._namespace = None
        self._loaded = False

    def __str__(self):
        return "%s(%r)" % (self.__class__.__name__,
                           os.path.basename(self._path))

    def load(self):
        self._log.error("%s: Loading module: %r" % (self, self._path))

        # Prepare namespace in which to execute the 
        namespace = {}
        namespace["__file__"] = self._path

        # Attempt to execute the module; handle any exceptions.
        try:
            execfile(self._path, namespace)
        except Exception, e:
            self._log.error("%s: Error loading module: %s" % (self, e))
            self._loaded = False
            return

        self._loaded = True
        self._namespace = namespace

    def unload(self):
        pass

    def check_freshness(self):
        pass


#---------------------------------------------------------------------------
# Command module directory class.

class CommandModuleDirectory(object):

    _log = logging.getLogger("directory")

    def __init__(self, path, excludes=None):
        self._path = os.path.abspath(path)
        self._excludes = excludes
        self._modules = {}

    def load(self):
        valid_paths = self._get_valid_paths()

        # Remove any deleted modules.
        for path, module in self._modules.items():
            if path not in valid_paths:
                del self._modules[path]
                module.unload()

        # Add any new modules.
        for path in valid_paths:
            if path not in self._modules:
                module = CommandModule(path)
                module.load()
                self._modules[path] = module
            else:
                module = self._modules[path]
                module.check_freshness()

    def _get_valid_paths(self):
        valid_paths = []
        for filename in os.listdir(self._path):
            path = os.path.abspath(os.path.join(self._path, filename))
            if not os.path.isfile(path):
                continue
            if not os.path.splitext(path)[1] == ".py":
                continue
            if path in self._excludes:
                continue
            valid_paths.append(path)
        self._log.error("valid paths: %r" % valid_paths)
        return valid_paths


#---------------------------------------------------------------------------
# Main event driving loop.

try:
    path = os.path.dirname(__file__)
except NameError:
    # The "__file__" name is not always available, for example
    #  when this module is run from PythonWin.  In this case we
    #  simply use the current working directory.
    path = os.path.dirname(os.getcwd())
    __file__ = os.path.join(path, "dragonfly-main.py")

directory = CommandModuleDirectory(path, excludes=[__file__])
directory.load()

engine.connect()


WinEventProcType = ctypes.WINFUNCTYPE(None, ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.wintypes.HWND,
                                      ctypes.wintypes.LONG, ctypes.wintypes.LONG, ctypes.wintypes.DWORD,
                                      ctypes.wintypes.DWORD)


def callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    window = Window.get_foreground()
    if hwnd == window.handle:
        engine.window_change(window.executable, window.title, window.handle)


def set_hook(win_event_proc, event_type):
    return ctypes.windll.user32.SetWinEventHook(event_type, event_type, 0, win_event_proc, 0, 0, win32con.WINEVENT_OUTOFCONTEXT)


win_event_proc = WinEventProcType(callback)
ctypes.windll.user32.SetWinEventHook.restype = ctypes.wintypes.HANDLE

[set_hook(win_event_proc, et) for et in
 {win32con.EVENT_SYSTEM_FOREGROUND, win32con.EVENT_OBJECT_NAMECHANGE, }]


engine.speak('beginning loop!')

while 1:
    pythoncom.PumpWaitingMessages()
    time.sleep(.1)
