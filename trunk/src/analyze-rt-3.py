import os
import glob
from util import *
import sys

def analyze_result(symbol, filename, interval, desc='DESC', out_f=sys.stdout, stat=None):
    if stat is None:
        stat = [0, 0, 0, 0, 0]
    max_equity = -1
    max_drawdown = 0
    trades = 0
    shares = 0
    total_pnl = 0

    f3 = None
    plot_input = filename.replace('csv', 'txt')
    first_dt = None
    last_dt = None
    equity = 1000000
    last_predicted_value = 0
    last_price = 0
    last_date = None

    data_count = 0
    f = open(filename)
    for line in f:
        line = line.strip()
        if not line:
            continue
        arr = line.split(',')
        if len(arr) != 16:
            continue
        arr = map((lambda s: s.strip()), arr)
        dt, cur_price, predicted_value, atr, diff, cur_price_, stoploss, takeprofit, size_per_trade, cur_size, trade_size, open_position_size, cur_total_pnl, pnl_per_share, cur_pnl, comment = arr
        try:
            int(cur_size)
        except:
            continue
        cur_date = int(dt.split(' ')[0].replace('/', ''))
        cur_size = int(cur_size)
        cur_price = float(cur_price)
        cur_total_pnl = float(cur_total_pnl)
        predicted_value = float(predicted_value)
        cur_pnl = float(cur_pnl)
        open_position_size = int(open_position_size)

        if last_price > 0 and abs(cur_price - last_price) > 0.2:
            continue
        last_price = cur_price

        if predicted_value == 0:
            predicted_value = last_predicted_value
        else:
            last_predicted_value = predicted_value

        if last_date is not None and cur_date > last_date:
            if cur_total_pnl == 0:
                last_total_pnl = 0
        last_date = cur_date
        #cur_pnl = cur_total_pnl - last_total_pnl
        last_total_pnl = cur_total_pnl
        total_pnl += cur_pnl
        equity += cur_pnl # FIXME

        dt2 = dt.replace(' ', '').replace('/', '').replace(':', '')
        if first_dt is None:
            first_dt = dt
        last_dt = dt

        if comment.startswith('PF_'):
        #if not comment or comment.startswith('PF_'):
        #if not comment.startswith('PC_'):
            continue
        if not f3:
            f3 = open_for_write(plot_input, 'w')
        print >> f3, dt2, cur_price, total_pnl, predicted_value#, open_position_size
        data_count += 1

        if max_equity == -1:
            max_equity = equity
        elif equity > max_equity:
            max_equity = equity
        elif max_equity > 0:
            cur_drawdown = (max_equity - equity) / max_equity
            if cur_drawdown > max_drawdown:
                max_drawdown = cur_drawdown

        if comment.startswith('PC_'):
            shares += abs(cur_size) * 2
            trades += 2

    f.close()
    if f3:
        f3.close()
    else:
        print '%s empty' % symbol
        return

    if trades == 0:
        trades = 1
    if shares == 0:
        shares = 1
    perf_line = '%s,%.4f,%d,%.6f,%d,%.6f,%.4f,%.2f,%s,%s' % (
        symbol, total_pnl, trades, total_pnl / trades, shares, total_pnl / shares, max_drawdown * 100, max_equity, desc,
        ','.join(map(str, stat)))
    print >>out_f, perf_line
    print perf_line

    f2 = open_for_write('../data/trading-results/%s.txt' % (symbol), 'a+')
    result_line = '%s\tPNL=%.4f\tTRADES=%d\tPNL/TRADE=%.6f\tSHARES=%d\tPNL/SHARE=%.6f\tMMAX_DRAWDOWN=%.2f\tMAX_EQUITY=%.2f\t%s\t%s' % (
        symbol, total_pnl, trades, total_pnl / trades, shares, total_pnl / shares, max_drawdown * 100, max_equity, desc,
        ','.join(map(str, stat)))
    print >> f2, result_line
    f2.close()

    result_line2 = '<STOPLOSS>(%s -> %s) %s PNL=%.4f TRADES=%d PNL/TRADE=%.6f SHARES=%d PNL/SHARE=%.6f MAX_DD=%.2f%% %d %s' % (
        first_dt, last_dt, symbol, total_pnl, trades, total_pnl / trades, shares, total_pnl / shares, max_drawdown * 100, interval,
        ','.join(map(str, stat))) #set y2range [100000:300000];
    plot_output = plot_input.replace('txt', 'jpg')
    # dt2, cur_price, equity, predicted_value, pnl+100000
    img_w, img_h = min(3600, max(1800, data_count * 2)), 800
    cmd = '''gnuplot -e "set terminal png size %d,%d; set output '%s'; set y2tics; set tics out; set tics nomirror; unset xtics; plot '%s' using 2 with l lc 5 title 'price', '' using 4 with l lc 2 title 'predicted', '' using 3 with l lc -1 title 'pnl' axes x1y2, 0 axes x1y2 title '%s' " ''' % (img_w, img_h, plot_output, plot_input, result_line2)
    #print cmd
    os.system(cmd)
    cmd = '''del %s''' % (plot_input)
    os.system(cmd)

def main():
    the_dir = r'../results/trading-rt-2.py-20130629-042858'
    if len(sys.argv) > 1:
        the_dir = sys.argv[1]
    out_file = os.path.join(the_dir, 'perf.csv')
    out_f = open_for_write(out_file)

    stat_line = ''
    stats = {}
    f = open('stat.csv')
    for line in f:
        arr = line.strip().split(', ')
        if arr[0] == 'symbol':
            stat_line = ','.join(arr[1:])
            continue
        symbol = arr[0]
        stat = map(float, arr[1:])
        stats[symbol] = stat
    f.close()

    print >>out_f, 'symbol,PNL,TRADES,PNL/TRADE,SHARES,PNL/SHARE,MAX_DRAWDOWN,MAX_EQUITY,DESC' + ',' + stat_line
    print 'symbol,PNL,TRADES,PNL/TRADE,SHARES,PNL/SHARE,MAX_DRAWDOWN,MAX_EQUITY,DESC' + ',' + stat_line

    for file in glob.glob(os.path.join(the_dir, '*.csv')):
        basename = os.path.basename(file)
        if basename.endswith('orders.csv') or basename.endswith('trades.csv'):
            continue
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
            stat = None
            if stats.has_key(symbol):
                stat = stats[symbol]
            analyze_result(symbol, file, interval, '%d' % interval, out_f, stat)
        except:
            dump_exception()
            pass

main()

