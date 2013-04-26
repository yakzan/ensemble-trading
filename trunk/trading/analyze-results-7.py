import os
import glob

def analyze_result(symbol, filename, desc='DESC'):
    max_equity = -1
    max_drawdown = 0
    trades = 0
    total_pnl = 0
    initial_balance = -1

    f = open(filename)
    f3 = None
    for line in f:
        line = line.strip()
        if not line or line.startswith('date_str'):
            continue
        arr = line.split(',')
        dt, position_size, position_price, cur_size, cur_price, cur_pnl, pnl, balance, equity, predicted_value = arr[:10]
        position_size = int(position_size)
        position_price = float(position_price)
        cur_size = int(cur_size)
        cur_price = float(cur_price)
        cur_pnl = float(cur_pnl)
        pnl = float(pnl)
        balance = float(balance)
        equity = float(equity)
        predicted_value = float(predicted_value)
        dt2 = dt.replace(' ', '').replace('/', '').replace(':', '')
        if initial_balance == -1:
            initial_balance = balance

        if not f3:
            f3 = open('../output/plot-7/%s.txt' % (symbol), 'w')
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
    print '%s\t%.4f\t%d\t%.6f\t%.2f\t%.2f\t%.2f\t%s' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, max_equity, total_pnl / initial_balance * 100, desc)

    f2 = open('../data/trading-results/%s.txt' % (symbol), 'a+')
    result_line = '%s\tPNL=%.4f\tTRADES=%d\tPNL/TRADE=%.6f\tMAX_DRAWDOWN=%.2f\tMAX_EQUITY=%.2f\t%%PNL=%.2f\t%s' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, max_equity, total_pnl / initial_balance * 100, desc)
    print >> f2, result_line
    f2.close()

    result_line2 = '<STOPLOSS> %s PNL=%.4f TRADES=%d PNL/TRADE=%.6f MAX_DD=%.2f%% %%PNL=%.f' % (
        symbol, total_pnl, trades, total_pnl / trades, max_drawdown * 100, total_pnl / initial_balance * 100) #set y2range [100000:300000];
    cmd = '''gnuplot -e "set terminal png size 1800,800; set output '../output/plot-7/%s.jpg'; set y2tics; set tics out; set tics nomirror; unset xtics; plot '../output/plot-7/%s.txt' using 2 with l lc 5 title 'price', '' using 4 with l lc 4 title 'predicted', '' using 3 with l lc -1 axes x1y2 title 'equitity %s' " ''' % (symbol, symbol, result_line2)
    #print cmd
    os.system(cmd)

def main():
    print 'symbol\tPNL\tTRADES\tPNL/TRADE\tMAX_DRAWDOWN\tMAX_EQUITY\tDESC'
    for file in glob.glob(r'd:\chimen-snippets\prediction\branches\over-embedding\output\trading-7\*.csv'):
        basename = os.path.basename(file)
        symbol = basename[:-6]
        #print file, symbol
        analyze_result(symbol, file, '0.8 for training, holding 10, stoploss, different size')

main()

def main1():
    print 'symbol\tPNL\tTRADES\tPNL/TRADE\tMAX_DRAWDOWN\tMAX_EQUITY\tDESC'
    for symbol in ['XLP']:
        interval = 10
        #print file, symbol, interval
        file = r'd:\chimen-snippets\prediction\branches\over-embedding\output\trading-7\%s_0.csv' % (symbol, interval)
        analyze_result(symbol, file, interval, 'interval=%d, 0.9 for training, holding 10, stoploss, different size' % interval)

#main1()
