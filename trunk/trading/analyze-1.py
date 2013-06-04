import os
import glob
from util import *
import sys

def analyze_result(symbol, filename, interval, desc='DESC', out_f=sys.stdout):
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
        try:
            int(position_size)
        except:
            continue
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
            first_dt = dt
        last_dt = dt

        if not f3:
            #f3 = open_for_write('../plot-6/%s_%d.txt' % (symbol, interval), 'w')
            f3 = open_for_write(plot_input, 'w')
        print >> f3, dt2, cur_price, equity, predicted_value, pnl + 100000 - 100

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
    print >>out_f, '%s,%.4f,%d,%.6f,%.2f,%.2f,%s' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, max_equity, desc)
    print '%s,%.4f,%d,%.6f,%.2f,%.2f,%s' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, max_equity, desc)

    f2 = open_for_write('../data/trading-results/%s.txt' % (symbol), 'a+')
    result_line = '%s\tPNL=%.4f\tTRADES=%d\tPNL/TRADE=%.6f\tMAX_DRAWDOWN=%.2f\tMAX_EQUITY=%.2f\t%s' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, max_equity, desc)
    print >> f2, result_line
    f2.close()

    result_line2 = '<STOPLOSS>(%s -> %s) %s PNL=%.4f TRADES=%d PNL/TRADE=%.6f MAX_DD=%.2f%% %d' % (
        first_dt, last_dt, symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, interval) #set y2range [100000:300000];
    plot_output = plot_input.replace('txt', 'jpg')
    # dt2, cur_price, equity, predicted_value, pnl+100000
    img_w, img_h = 1800, 800
    cmd = '''gnuplot -e "set terminal png size %d,%d; set output '%s'; set y2tics; set tics out; set tics nomirror; unset xtics; plot '%s' using 2 with l lc 5 title 'price', '' using 4 with l lc 4 title 'predicted', '' using 3 with l lc -1 title 'equity' axes x1y2, '' using 5 with l title 'pnl' axes x1y2, 100000 axes x1y2 title '%s' " ''' % (img_w, img_h, plot_output, plot_input, result_line2)
    #print cmd
    os.system(cmd)

def main():
    the_dir = r'../results/trading-2.py-20130531-174057'
    if len(sys.argv) > 1:
        the_dir = sys.argv[1]
    out_file = os.path.join(the_dir, 'perf.csv')
    out_f = open_for_write(out_file)
    print >>out_f, 'symbol,PNL,TRADES,PNL/TRADE,MAX_DRAWDOWN,MAX_EQUITY,DESC'
    for file in glob.glob(os.path.join(the_dir, '*.csv')):
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
            analyze_result(symbol, file, interval, '%d' % interval, out_f)
        except:
            dump_exception()
            pass

main()

