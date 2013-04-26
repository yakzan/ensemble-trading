import struct
import os
import glob
import operator

class OneMinBar:
    def __init__(self,  _date, _time, _open,  _high,  _low,  _close,  _volume):
        self.date, self.open,  self.high,  self.low,  self.close,  self.volume= \
            _date * 10000 + _time, _open,  _high,  _low,  _close,  _volume

    def __str__(self):
        return '%d, %.02f, %f, %f, %f, %d' % (
            self.date,  self.open,  self.high,  self.low,  self.close,  self.volume)


def onemin_to_bars(filename):
    f = open(filename)
    bars = []
    for line in f:
        # 07/26/2010	09:30	128.18	128.18	127.81	127.95	93489
        try:
            _date, _time, _open,  _high,  _low,  _close,  _volume  = line.strip().split('\t')
            arr = _date.split('/')
            _date = int(arr[2]) * 10000 + int(arr[0]) * 100 + int(arr[1])
            _time = int(_time.replace(':', ''))
            _open = float(_open)
            _high = float(_high)
            _low = float(_low)
            _close = float(_close)
            _volume = int(_volume)
            bar = OneMinBar(_date, _time, _open,  _high,  _low,  _close,  _volume)
            bars.append(bar)
        except ValueError:
            print line
            pass
        except:
            print line
            dump_exception()
            pass
    return bars

def compress_bars(symbol, bars):
    #f = open('../data/1min-comp/%s_1.dat' % symbol, 'wb')
    for bar in bars:
        dd = bar.date / 10000
        tt = bar.date % 10000
        y, M, d = dd / 10000, dd % 10000 / 100, dd % 100
        h, m = tt / 100, tt % 100
        dd2 = (y % 100) * (13*32) + M * 32 + d
        tt2 = h * 60 + m
        p1 = int(bar.close)
        p2 = int((bar.close - int(bar.close)) * 100)
        buf = struct.pack('<HHHH', dd2, tt2, p1, p2)
        print bar.date, bar.close, y, M, d, h, m, dd2, tt2, p1, p2, buf.encode('hex'), '%x,%x' % (dd2, tt2)
        if dd2 > 65535 or tt2 > 65535 or p1 > 65535 or p2 > 65536:
            print bar.date, bar.close, y, M, d, dd2, tt2, p1, p2, buf.encode('hex')
        #f.write(buf)
    #f.close()

flist = glob.glob(r'd:\chimen-snippets\prediction\branches\over-embedding\data\1min\*_1.txt')
for i in range(len(flist)):
    statinfo = os.stat(flist[i])
    flist[i] = [flist[i], statinfo.st_size]
flist.sort(key=lambda tup: tup[1])
for i in range(len(flist)):
    flist[i] = flist[i][0]

for file in reversed(flist[-20:]):
    symbol = os.path.basename(file)[:-6]
    print "'%s', " % symbol,
#if 0:
    #for symbol in ['GLD', 'AMZN', 'DIA', 'BIDU', 'GOOG', 'IBM', 'GS', 'INTC', 'MSFT', 'BAC', 'BBY', 'ORCL']:
    for file in reversed(flist[-500:]):
        symbol = os.path.basename(file)[:-6]
        print symbol
        bars = onemin_to_bars(r'd:\chimen-snippets\prediction\branches\over-embedding\data\1min\%s_1.txt' % symbol)
        compress_bars(symbol, bars)
