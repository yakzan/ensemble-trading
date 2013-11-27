from svm_helper import *
from svm_data import *
from random import *
from math import *
from util import *
from rv import *
import sys
import os
import time
import shutil
import logging

logger = 0
log_dir = ''
out_file = ''
out_f = 0

def get_stat(symbol, interval=1, delay=1, dimension=5, data_file=None):
    data = SvmData(symbol, SvmData.ONE_MIN, interval, data_file=data_file)
    data.set_settings(portion_training=1)
    data.set_dimension_delay(dimension, delay)

    if len(data.bars) < 5000:
        return
    if len(data.bars) > 20000:
        data.bars = data.bars[-20000:]

    data.prepare_svm_lines(verbose=0)

    extended_svm_lines = data.detailed_svm_lines

    prices = [line[-2] for line in extended_svm_lines]
    avg_price = sum(prices) / len(prices)
    changes = [abs(line[-3] - line[-2]) / line[-2] for line in extended_svm_lines]
    max_change = max(changes)

    arr_atr = [abs(line[-6]) for line in extended_svm_lines]
    avg_atr = sum(arr_atr) / len(arr_atr)
    stddev_atr = math.sqrt(sum([(b - avg_atr) ** 2 for b in arr_atr]) / len(arr_atr))

    arr_volume = [line[-8] for line in extended_svm_lines]
    avg_volume = sum(arr_volume) / len(arr_volume)

    line = '%s, avg_price,%.4f, max_change,%.4f, avg_atr,%.4f, stddev_atr,%.4f, avg_volume,%.4f' % (
        symbol, avg_price, max_change, avg_atr, stddev_atr, avg_volume)
    print line
    logger.info(line)
    print >>out_f, '%s, %.4f, %.4f, %.4f, %.4f, %.4f' % (
        symbol, avg_price, max_change, avg_atr, stddev_atr, avg_volume)
    out_f.flush()

def save_settings(argv, timestamp):

    global logger
    global log_dir

    this_file = argv[0]

    log_dir = '../results/%s-%s' % (
            this_file,
            timestamp)
    log_file = os.path.join(log_dir, 'log.txt')
    ensure_dir(log_file)
    shutil.copy(this_file, log_dir)

    logger = logging.getLogger()
    hdlr = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)

    logger.info(repr(argv))
if __name__ == '__main__':
    timestamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())
    save_settings(sys.argv, timestamp)

    out_file = os.path.join(log_dir, 'stat.csv')
    out_f = open_for_write(out_file)
    print >>out_f, 'symbol, avg_price, max_change, avg_atr, stddev_atr, avg_volume'

    files = glob.glob(r'//192.168.137.1/MarketData/US/1Min/Data/1minuteMin/*_1.txt')
    print len(files), 'files'
    for file in files:
        basename = os.path.basename(file)
        symbol = basename[:-6]
        print symbol, file
        get_stat(symbol, interval=1, delay=1, dimension=5, data_file=file)
    out_f.close()

