# -*- coding: utf-8 -*-
import os
import pathlib
import sys
from logging import (
    LogRecord, StreamHandler, FileHandler, Formatter, getLogger, INFO,
    WARN, ERROR, DEBUG,
)
from logging.handlers import TimedRotatingFileHandler


# ==============================================================================
# from django.core.management.color import supports_color
try:
    import colorama
    colorama.init()
except (ImportError, OSError):
    HAS_COLORAMA = False
else:
    HAS_COLORAMA = True


def supports_color():
    """
    Return True if the running system's terminal supports color,
    and False otherwise.
    """
    def vt_codes_enabled_in_windows_registry():
        """
        Check the Windows Registry to see if VT code handling has been enabled
        by default, see https://superuser.com/a/1300251/447564.
        """
        try:
            # winreg is only available on Windows.
            import winreg
        except ImportError:
            return False
        else:
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Console')
            try:
                reg_key_value, _ = winreg.QueryValueEx(reg_key, 'VirtualTerminalLevel')
            except FileNotFoundError:
                return False
            else:
                return reg_key_value == 1

    # isatty is not always implemented, #6223.
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

    return is_a_tty and (
            sys.platform != 'win32' or
            HAS_COLORAMA or
            'ANSICON' in os.environ or
            # Windows Terminal supports VT codes.
            'WT_SESSION' in os.environ or
            # Microsoft Visual Studio Code's built-in terminal supports colors.
            os.environ.get('TERM_PROGRAM') == 'vscode' or
            vt_codes_enabled_in_windows_registry()
    )


# form django.utils.termcolors import colorize
color_names = ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
foreground = {color_names[x]: '3%s' % x for x in range(8)}
background = {color_names[x]: '4%s' % x for x in range(8)}

RESET = '0'
opt_dict = {'bold': '1', 'underscore': '4', 'blink': '5', 'reverse': '7', 'conceal': '8'}


def colorize(text='', opts=(), **kwargs):
    """
    Return your text, enclosed in ANSI graphics codes.

    Depends on the keyword arguments 'fg' and 'bg', and the contents of
    the opts tuple/list.

    Return the RESET code if no parameters are given.

    Valid colors:
        'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'

    Valid options:
        'bold'
        'underscore'
        'blink'
        'reverse'
        'conceal'
        'noreset' - string will not be auto-terminated with the RESET code

    Examples:
        colorize('hello', fg='red', bg='blue', opts=('blink',))
        colorize()
        colorize('goodbye', opts=('underscore',))
        print(colorize('first line', fg='red', opts=('noreset',)))
        print('this should be red too')
        print(colorize('and so should this'))
        print('this should not be red')
    """
    code_list = []
    if text == '' and len(opts) == 1 and opts[0] == 'reset':
        return '\x1b[%sm' % RESET
    for k, v in kwargs.items():
        if k == 'fg':
            code_list.append(foreground[v])
        elif k == 'bg':
            code_list.append(background[v])
    for o in opts:
        if o in opt_dict:
            code_list.append(opt_dict[o])
    if 'noreset' not in opts:
        text = '%s\x1b[%sm' % (text or '', RESET)
    return '%s%s' % (('\x1b[%sm' % ';'.join(code_list)), text or '')


# ==============================================================================
def set_color(levelname, msg):
    if levelname in ("FATAL", "CRITICAL"):
        msg = colorize(msg, fg="red", opts=("bold",))
    elif levelname == "ERROR":
        msg = colorize(msg, fg="red", opts=("bold",))
    elif levelname in ("WARN", "WARNING"):
        msg = colorize(msg, fg="yellow", opts=("bold",))
    elif levelname == "INFO":
        msg = colorize(msg, fg="green")
    elif levelname == "DEBUG":
        msg = colorize(msg, fg="cyan")
    return msg


class ColorFormatter(Formatter):
    def __init__(self, *args, **kwargs):
        self.support_color = supports_color()
        super(ColorFormatter, self).__init__(*args, **kwargs)

    def format(self, record: LogRecord) -> str:
        if self.support_color:
            record.msg = set_color(record.levelname, record.msg)
        return super(ColorFormatter, self).format(record)

    def formatException(self, ei) -> str:
        msg = super(ColorFormatter, self).formatException(ei)
        if self.support_color:
            return set_color("CRITICAL", msg)
        else:
            return msg


LOG_Name = pathlib.Path(__file__).parent.name
LOG_Path = pathlib.Path(__file__).parent.joinpath(LOG_Name + '.log')
FileH = TimedRotatingFileHandler(LOG_Path, when='W0', backupCount=12)
LOG_FORMAT = ColorFormatter("%(asctime)s %(levelname)s - %(message)s")
FileH.setLevel(INFO)
FileH.setFormatter(LOG_FORMAT)
TerminalH = StreamHandler()
DEBUG_FORMAT = ColorFormatter(
    "%(asctime)s %(levelname)s  %(processName)s[%(threadName)s]  "
    "%(pathname)s[%(funcName)s:%(lineno)d] %(message)s")
TerminalH.setLevel(INFO)
TerminalH.setFormatter(LOG_FORMAT)

logger = getLogger()
logger.addHandler(FileH)
logger.setLevel(INFO)
