import time
import datetime
import glob
import os
from util import *
from svm_data import *

def get_date_list():
    today = datetime.datetime.today()
    date_list = []
    day = datetime.datetime(2011, 1, 1)
    while day < today:
        weekday = day.isoweekday()
        if weekday >= 1 and weekday <= 5:
            date_list.append(day)
        day += datetime.timedelta(days=1)
    return date_list

def download_forex_data():
    for day in get_date_list():
        print 'http://www.forexite.com/free_forex_quotes/%d/%02d/%02d%02d%02d.zip' % (
            day.year, day.month, day.day, day.month, day.year % 100)

#download_forex_data()

def convert_forex_data():
    symbol_to_bars = {}
    for orig_file in glob.glob(r'../data/forex-orig/*.txt'):
        print orig_file
        with open(orig_file, 'r') as orig_f:
            for line in orig_f:
                line = line.strip()
                if line.startswith('<') or not line:
                    continue
                #EURUSD,20110201,001500,1.3689,1.3689,1.3689,1.3689
                symbol, date, time, o, h, l, c = line.split(',')
                date = int(date)
                time = int(time) / 100
                c = float(c)
                bar = (date, time, c)
                if not symbol_to_bars.has_key(symbol):
                    symbol_to_bars[symbol] = [ bar ]
                else:
                    symbol_to_bars[symbol].append(bar)

    print '-' * 50

    for symbol, bar_list in symbol_to_bars.items():
        print symbol
        bar_list.sort(lambda a, b: cmp(a[0] * 10000 + a[1], b[0] * 10000 + b[1]))
        with open_for_write(r'../data/forex/%s_1.txt' % symbol) as out_f:
            for bar in bar_list:
                # 07/21/2011	09:38	384.53	384.68	383.9	384.39	146948
                date, time, c = bar
                print >>out_f, '%02d/%02d/%04d\t%02d:%02d\t%.02f\t%.02f\t%.02f\t%.02f\t%d' % (
                    date % 10000 / 100, date % 100, date / 10000,
                    time / 100, time % 100,
                    c, c, c, c, 0)

convert_forex_data()
