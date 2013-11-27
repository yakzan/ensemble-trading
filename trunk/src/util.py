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

def stime(secs):
    return '%02d:%02d:%02d' % (secs / 3600, secs % 3600 / 60, secs % 60)

def sdate(d):
    return '%4d/%02d/%02d' % (d / 10000, d % 10000 / 100, d % 100)

def get_secs(stime):
    arr = stime.split(':')
    if len(arr) == 2:
        return int(arr[0]) * 3600 + int(arr[1]) * 60
    elif len(arr) == 3:
        return int(arr[0]) * 3600 + int(arr[1]) * 60 + int(arr[2])
    else:
        return int(arr[0])

