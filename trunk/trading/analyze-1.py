import os
import glob
from util import *

def analyze_result(symbol, filename, interval, desc='DESC'):
    max_equity = -1
    max_drawdown = 0
    trades = 0
    total_pnl = 0

    f = open(filename)
    f3 = None
    plot_input = filename.replace('csv', 'txt')
    first_dt = None
    last_dt = None
    for line in f:
        line = line.strip()
        if not line:
            continue
        arr = line.split(',')
        dt, position_size, position_price, cur_size, cur_price, cur_pnl, pnl, equity, predicted_value = arr[:9]
        position_size = int(position_size)
        position_price = float(position_price)
        cur_size = int(cur_size)
        cur_price = float(cur_price)
        cur_pnl = float(cur_pnl)
        pnl = float(pnl)
        equity = float(equity)
        predicted_value = float(predicted_value)
        dt2 = dt.replace(' ', '').replace('/', '').replace(':', '')
        if first_dt is None:
            first_dt = dt2
        last_dt = dt2

        if not f3:
            #f3 = open_for_write('../plot-6/%s_%d.txt' % (symbol, interval), 'w')
            f3 = open_for_write(plot_input, 'w')
        print >> f3, dt2, cur_price, equity, predicted_value

        if max_equity == -1:
            max_equity = equity
        elif equity > max_equity:
            max_equity = equity
        elif max_equity > 0:
            cur_drawdown = (max_equity - equity) / max_equity
            if cur_drawdown > max_drawdown:
                max_drawdown = cur_drawdown

        trades += abs(cur_size)
        total_pnl = pnl

    f.close()
    if f3:
        f3.close()
    else:
        print '%s empty' % symbol
        return

    if trades == 0:
        trades = 1
    print '%s\t%.4f\t%d\t%.6f\t%.2f\t%.2f\t%s' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, max_equity, desc)

    f2 = open_for_write('../data/trading-results/%s.txt' % (symbol), 'a+')
    result_line = '%s\tPNL=%.4f\tTRADES=%d\tPNL/TRADE=%.6f\tMAX_DRAWDOWN=%.2f\tMAX_EQUITY=%.2f\t%s' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, max_equity, desc)
    print >> f2, result_line
    f2.close()

    result_line2 = '<STOPLOSS>(%s -> %s) %s PNL=%.4f TRADES=%d PNL/TRADE=%.6f MAX_DD=%.2f%% %d' % (
        first_dt, last_dt, symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, interval) #set y2range [100000:300000];
    plot_output = plot_input.replace('txt', 'jpg')
    img_w, img_h = 1800, 800
    cmd = '''gnuplot -e "set terminal png size %d,%d; set output '%s'; set y2tics; set tics out; set tics nomirror; unset xtics; plot '%s' using 2 with l lc 5 title 'price', '' using 4 with l lc 4 title 'predicted', '' using 3 with l lc -1 title 'equity' axes x1y2, 100000 axes x1y2 title '%s' " ''' % (img_w, img_h, plot_output, plot_input, result_line2)
    #print cmd
    os.system(cmd)

def main():
    print 'symbol\tPNL\tTRADES\tPNL/TRADE\tMAX_DRAWDOWN\tMAX_EQUITY\tDESC'
    for file in glob.glob(r'..\results\analyze-2.py-20130529-005302\*.csv'):
        basename = os.path.basename(file)
        arr = basename[:-4].split('_')
        if len(arr) < 3:
            continue
        symbol = arr[0]
        interval = 5
        if arr[1].startswith('i'):
            interval = int(arr[1][1:])
        else:
            interval = int(arr[2])
        #print file, symbol, interval
        try:
            analyze_result(symbol, file, interval, 'interval=%d, 0.5 for training, holding 10, stoploss, different size' % interval)
        except:
           pass

main()

def main1():
    print 'symbol\tPNL\tTRADES\tPNL/TRADE\tMAX_DRAWDOWN\tMAX_EQUITY\tDESC'
    for symbol in ['XLP']:
        interval = 10
        #print file, symbol, interval
        file = r'd:\chimen-snippets\prediction\branches\over-embedding\output\trading-6\%s_3_%d.csv' % (symbol, interval)
        analyze_result(symbol, file, interval, 'interval=%d, 0.9 for training, holding 10, stoploss, different size' % interval)

#main1()
