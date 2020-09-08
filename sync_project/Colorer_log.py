# -*- coding: utf-8 -*-
import pathlib
import platform
from logging import (StreamHandler, FileHandler, Formatter, getLogger, INFO,
                     WARN, ERROR, DEBUG)
from logging.handlers import TimedRotatingFileHandler
# now we patch Python code to add color support to logging.StreamHandler
import sys


PYV = sys.version_info[0]
if PYV == 3:
    code_type = str
elif PYV == 2:
    code_type = unicode


class ColorMixin(object):

    def _set_color(self, code):
        pass


class ColorStreamHandler(ColorMixin, StreamHandler):
    """
    color stream handler base
    """


class ColorFileHandler(ColorMixin, FileHandler):
    """
    color file handler base
    """


class ColorTimedRotatingFileHandler(ColorMixin, TimedRotatingFileHandler):
    """
    color timed rotating file handler base
    """


def add_coloring_to_emit_windows(fn):
    # add methods we need to the class
    def _out_handle(self):
        import ctypes
        return ctypes.windll.kernel32.GetStdHandle(self.STD_OUTPUT_HANDLE)
    out_handle = property(_out_handle)

    def _set_color(self, code):
        import ctypes
        # Constants from the Windows API
        self.STD_OUTPUT_HANDLE = -11
        hdl = ctypes.windll.kernel32.GetStdHandle(self.STD_OUTPUT_HANDLE)
        ctypes.windll.kernel32.SetConsoleTextAttribute(hdl, code)

    setattr(ColorStreamHandler, '_set_color', _set_color)

    def new(*args):
        FOREGROUND_BLUE = 0x0001  # text color contains blue.
        FOREGROUND_GREEN = 0x0002  # text color contains green.
        FOREGROUND_RED = 0x0004  # text color contains red.
        FOREGROUND_INTENSITY = 0x0008  # text color is intensified.
        FOREGROUND_WHITE = FOREGROUND_BLUE | FOREGROUND_GREEN | FOREGROUND_RED
        # winbase.h
        STD_INPUT_HANDLE = -10
        STD_OUTPUT_HANDLE = -11
        STD_ERROR_HANDLE = -12

        # wincon.h
        FOREGROUND_BLACK = 0x0000
        FOREGROUND_BLUE = 0x0001
        FOREGROUND_GREEN = 0x0002
        FOREGROUND_CYAN = 0x0003
        FOREGROUND_RED = 0x0004
        FOREGROUND_MAGENTA = 0x0005
        FOREGROUND_YELLOW = 0x0006
        FOREGROUND_GREY = 0x0007
        FOREGROUND_INTENSITY = 0x0008  # foreground color is intensified.

        BACKGROUND_BLACK = 0x0000
        BACKGROUND_BLUE = 0x0010
        BACKGROUND_GREEN = 0x0020
        BACKGROUND_CYAN = 0x0030
        BACKGROUND_RED = 0x0040
        BACKGROUND_MAGENTA = 0x0050
        BACKGROUND_YELLOW = 0x0060
        BACKGROUND_GREY = 0x0070
        BACKGROUND_INTENSITY = 0x0080  # background color is intensified.

        levelno = args[1].levelno
        if(levelno >= 50):
            color = BACKGROUND_YELLOW | FOREGROUND_RED | FOREGROUND_INTENSITY | BACKGROUND_INTENSITY
        elif(levelno >= 40):
            color = FOREGROUND_RED | FOREGROUND_INTENSITY
        elif(levelno >= 30):
            color = FOREGROUND_YELLOW | FOREGROUND_INTENSITY
        elif(levelno >= 20):
            color = FOREGROUND_GREEN
        elif(levelno >= 10):
            color = FOREGROUND_MAGENTA
        else:
            color = FOREGROUND_WHITE
        args[0]._set_color(color)

        ret = fn(*args)
        args[0]._set_color(FOREGROUND_WHITE)
        # print "after"
        return ret
    return new


def add_coloring_to_emit_ansi(fn):
    # add methods we need to the class
    def new(*args):
        levelno = args[1].levelno
        if(levelno >= 50):
            color = '\x1b[31m'  # red
        elif(levelno >= 40):
            color = '\x1b[31m'  # red
        elif(levelno >= 30):
            color = '\x1b[33m'  # yellow
        elif(levelno >= 20):
            color = '\x1b[32m'  # green
        elif(levelno >= 10):
            color = '\x1b[35m'  # pink
        else:
            color = '\x1b[0m'  # normal
        if args[1].msg:
            args[1].msg = color + args[1].msg.getMessage() + '\x1b[0m'  # normal
        # print "after"
        return fn(*args)
    return new


if platform.system() == 'Windows':
    # Windows does not support ANSI escapes and we are using API calls to set
    # the console color
    ColorStreamHandler.emit = add_coloring_to_emit_windows(
        ColorStreamHandler.emit)
    ColorFileHandler.emit = add_coloring_to_emit_windows(
            ColorFileHandler.emit)
    ColorTimedRotatingFileHandler.emit = add_coloring_to_emit_windows(
            ColorTimedRotatingFileHandler.emit)
else:
    # all non-Windows platforms are supporting ANSI escapes so we use them
    ColorStreamHandler.emit = add_coloring_to_emit_ansi(
        ColorStreamHandler.emit)
    ColorFileHandler.emit = add_coloring_to_emit_ansi(
            ColorFileHandler.emit)
    ColorTimedRotatingFileHandler.emit = add_coloring_to_emit_ansi(
            ColorTimedRotatingFileHandler.emit)

LOG_Name = pathlib.Path(__file__).parent.name
LOG_Path = pathlib.Path(__file__).parent.joinpath(LOG_Name + '.log')
FileH = ColorTimedRotatingFileHandler(LOG_Path, when='W0', backupCount=12)
LOG_FORMAT = Formatter("%(asctime)s %(levelname)s %(message)s")
FileH.setLevel(INFO)
FileH.setFormatter(LOG_FORMAT)
TerminalH = ColorStreamHandler()
DEBUG_FORMAT = Formatter(
        "%(asctime)s %(levelname)s  %(processName)s[%(threadName)s]  "
        "%(pathname)s[%(funcName)s:%(lineno)d] %(message)s")
TerminalH.setLevel(INFO)
TerminalH.setFormatter(LOG_FORMAT)


logger = getLogger()
logger.addHandler(FileH)
logger.setLevel(INFO)


def set_log_handler(LOG, method, name):
    if name in ('f', 'F'):
        if method in ('a', 'A'):
            if FileH not in LOG.handlers:
                LOG.addHandler(FileH)
                LOG.warning('write log to file')
        elif method in ('d', 'd'):
            if FileH in LOG.handlers:
                LOG.removeHandler(FileH)
                LOG.warning("don't write log to file")
        else:
            LOG.error('alter method error, must be a or d')
    if name in ('t', 'T'):
        if method in ('a', 'A'):
            if FileH not in LOG.handlers:
                LOG.addHandler(TerminalH)
                LOG.warning('write log to terminal')
        elif method in ('d', 'd'):
            if FileH in LOG.handlers:
                LOG.removeHandler(TerminalH)
                LOG.warning("don't write log to terminal")
        else:
            LOG.error('alter method error, must be a or d')
    return LOG

"""
e.g.
from Colorer_log import logger

logger.info("xxx")
logger.error("xxx")


2020-01-06 15:26:47,756 INFO xxx
=====================================
debug

from Colorer_log import logger, DEBUG_FORMAT, FileH

FileH.setFormatter(DEBUG_FORMAT)

logger.debug("xxx")
logger.info("xxx")


2020-01-06 15:37:42,355 DEBUG  MainProcess[Thread-15]  dirname/file_name.py[method_name:125] xxx
"""
