import os
import sys
import traceback
import logging

def ensure_dir(filename):
    dir = os.path.dirname(filename)

    if not os.path.exists(dir):
        os.makedirs(dir)

def dump_exception(to_std=1):
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_list = traceback.format_tb(exc_traceback, 10)
    s = "%s, %s \nTraceback:" % (exc_type.__name__, exc_value)
    for i in tb_list:
        s += "\n" + i
    logging.error(s)
    if to_std:
        print s

def open_for_write(filename, mode='w'):
    ensure_dir(filename)
    return open(filename, mode)
