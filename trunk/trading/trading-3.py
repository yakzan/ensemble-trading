# parse older prediction and trading results,
# and trade using different settings.
import glob
import logging
import os
import shutil
import sys
import time
from math import *
from util import *
from multiprocessing import Process

logger = 0
log_dir = ''
total_instances = 4

def analyze_result(orig_file, holding_period = 5):
    basename = os.path.basename(orig_file)
    arr = basename[:-4].split('_')
    symbol = arr[0]
    interval = int(arr[1][1:])
    #print file, symbol, interval

    trades = []
    initial_buying_power = 100000
    buying_power = initial_buying_power
    balance = initial_buying_power
    equity = initial_buying_power
    positions_size = 0
    positions_price = 0
    pnl = 0
    #holding_period = 5
    total_trades = 0
    max_equity = -1
    max_drawdown = 0
    total_pnl = 0

    last_price = None


    f_out_name = os.path.join(log_dir, basename[:-4] + ('_h%d' % holding_period) + basename[-4:])
    f_out = open_for_write(f_out_name, 'w')
    print >>f_out, 'date_str, positions_size, positions_price, cur_size, cur_price, unrealized_pnl, pnl, equity, predicted_value,  close_size, close_reason, open_size, holding_period, stoploss, change, atr, predicted_diff, size_per_trade'

    f = open(orig_file)
    for line in f:
        line = line.strip()
        if not line:
            continue
        arr = line.split(',')
        date_str, _positions_size, _positions_price, _cur_size, _cur_price, _unrealized_pnl, _pnl, _equity, _predicted_value, _close_size, _close_reason, _open_size, _holding_period, _stoploss, _change, _atr, _predicted_diff, _size_per_trade = arr
        try:
            int(_positions_size)
        except:
            continue

        cur_price = float(_cur_price)
        predicted_value = float(_predicted_value)
        size_per_trade = int(_size_per_trade)
        atr = float(_atr)
        #change = float(_change)
        #change = 0.002
        change = 0.00
        #change = atr / 2
        #change = atr
        #change = 0.01
        stoploss_diff = atr * 2
        #stoploss_diff = 0.005
        #stoploss_diff = 0.03

        cur_size = 0
        close_reason = ''
        has_stoploss = False
        for i in range(len(trades)-1, -1, -1):
            old_size, old_holding_period, old_stoploss, old_date = trades[i]
            if old_holding_period <= 1:
                close_reason += 'TO_%d_%s ' % (i, old_date)
                cur_size -= old_size
                del trades[i]
            elif (old_size > 0 and (old_stoploss > cur_price)) or \
                (old_size < 0 and (old_stoploss < cur_price)):
                close_reason += 'SL_%d_%.2f_%s ' % (i, old_stoploss, old_date)
                cur_size -= old_size
                has_stoploss = True
                del trades[i]
            else:
                trades[i][1] -= 1 # decrease holding period
        close_size = cur_size

        price_is_normal = True
        #if not last_price is None and \
           #abs(atr) > 0.0001 and abs(cur_price - last_price) > abs(atr):
            #price_is_normal = False
        last_price = cur_price

        if not has_stoploss and price_is_normal:
            if (predicted_value - cur_price > change): # predicted UP
                if abs((positions_size+cur_price) * positions_price + size_per_trade * cur_price) <= buying_power: # can buy
                    cur_size += size_per_trade
            elif cur_price - predicted_value > change: # predicted DOWN
                if abs((positions_size+cur_price) * positions_price - size_per_trade * cur_price) <= buying_power: # can sell
                    cur_size -= size_per_trade

        cur_pnl = 0
        if positions_size > 0: # was long
            if cur_size > 0: # long again
                positions_price = (positions_size * positions_price + cur_size * cur_price) / (positions_size + cur_size)
            elif cur_size < 0: # short
                cur_pnl = (cur_price - positions_price) * abs(cur_size)
        elif positions_size < 0: # was short
            if cur_size < 0: # short again
                positions_price = abs((positions_size * positions_price + cur_size * cur_price) / (positions_size + cur_size))
            elif cur_size > 0: # long
                cur_pnl = (positions_price - cur_price) * cur_size
        else:
            positions_price = cur_price

        # 3000, -1000, -1000, -2000
        # -3000, 1000, 1000, 2000
        # -1000, 0, 2000, 2000
        if positions_size != 0 and (cur_size - close_size) != 0 and \
            positions_size * (cur_size - close_size) < 0:
            # new trade => close
            new_trade_size = cur_size - close_size
            size_to_close = new_trade_size
            for i in range(len(trades)-1, -1, -1):
                old_size, old_holding_period, old_stoploss, old_date = trades[i]
                if old_size + size_to_close == 0:
                    close_size += size_to_close
                    size_to_close = 0
                    close_reason += 'Close_%s ' % (old_date)
                    del trades[i]
                    break
                elif (old_size + size_to_close) * old_size > 0: # close part
                    close_size += size_to_close
                    trades[i][0] += size_to_close
                    close_reason += 'Close_%d_%s ' % (size_to_close, old_date)
                    size_to_close = 0
                    break
                elif (old_size + size_to_close) * old_size < 0: # close all, only part ot the trade => close
                    #1000, -3000
                    close_size += (-old_size)
                    size_to_close -= (-old_size)
                    close_reason += 'Close_%s ' % (old_date)
                    del trades[i]

        pnl += cur_pnl
        positions_size += cur_size
        balance += cur_pnl
        equity = balance + (cur_price - positions_price) * (positions_size)
        buying_power = balance - abs(cur_price * cur_size)

        stoploss = 0
        if cur_size-close_size != 0:
            if cur_size-close_size > 0: # buy
                stoploss = cur_price - stoploss_diff #atr * 2 #cur_price - abs(predicted_value - cur_price)
            else: # sell
                stoploss = cur_price + stoploss_diff #atr * 2 # cur_price + abs(predicted_value - cur_price)
            trades.append([cur_size-close_size, holding_period, stoploss, date_str])
        total_trades += abs(cur_size)

        #print >>f_out, ','.join(map(str, [date_str, pnl, positions_size, positions_price, cur_size, close_size, cur_size-close_size, cur_price, predicted_value, buying_power, balance, equity, total_trades, pnl / total_trades]))
        print >>f_out, ','.join(map(str, [date_str, positions_size, positions_price, cur_size, cur_price, (cur_price - positions_price) * (positions_size), pnl, equity, predicted_value,  close_size, close_reason, cur_size-close_size, holding_period, stoploss, change, atr, predicted_value-cur_price, size_per_trade]))

        if max_equity == -1:
            max_equity = equity
        elif equity > max_equity:
            max_equity = equity
        elif max_equity > 0:
            cur_drawdown = (max_equity - equity) / max_equity
            if cur_drawdown > max_drawdown:
                max_drawdown = cur_drawdown

    f.close()
    f_out.close()

    if total_trades == 0:
        return

    print '-' * 20
    print basename, pnl, total_trades, pnl / total_trades, max_drawdown
    print '-' * 20
    logger.info('  '.join(map(str, [basename, pnl, total_trades, pnl / total_trades, max_drawdown])))
    logger.info('-' * 20)


def save_settings(argv, instance_num):

    global logger
    global log_dir

    log_file = os.path.join(log_dir, 'log.txt')
    if instance_num != -1:
        log_file = os.path.join(log_dir, 'log_%d.txt' % instance_num)
    ensure_dir(log_file)

    if instance_num == -1 or instance_num == 0:
        this_file = sys.argv[0]
        shutil.copy(this_file, log_dir)

    logger = logging.getLogger()
    hdlr = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)

    logger.info(repr(argv))

def main_worker(orig_files, instance_num):
    global logger
    save_settings(sys.argv, instance_num)

    if instance_num != -1:
        n = len(orig_files)
        n2 = n / total_instances
        if n % total_instances != 0:
            n2 += 1
        orig_files = orig_files[instance_num * n2 : instance_num * n2 + n2]


    for orig_file in orig_files:
        try:
            for holding_period in range(1, 20, 2):
                analyze_result(orig_file, holding_period)
        except:
            dump_exception()
            pass

def main():
    global log_dir
    this_file = sys.argv[0]
    timestamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())
    log_dir = '../results/%s-%s' % (this_file, timestamp)

    orig_dir = r'../results/trading-2.py-20130531-174057'
    if len(sys.argv) > 1:
        orig_dir = sys.argv[1]
    orig_files = glob.glob(os.path.join(orig_dir, '*.csv'))

    for i in range(total_instances):
        #Process(target=main_worker, args=(orig_files, i)).start()
        main_worker(orig_files, i)

main()

