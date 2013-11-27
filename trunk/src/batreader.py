import sys
from struct import unpack

class BATReader:
    def __init__(self, file_name):
        self.file_name = file_name

    def init(self):
        try:
            self.f = open(self.file_name, "rb")
            return 0
        except IOError:
            return -1

    def term(self):
        self.f.close()

    def read_data(self):
        try:
            buf = self.f.read(4)
            if (len(buf) != 4):
                print "if (len(buf) != 4):", len(buf)
                return (0, "")
            num = unpack("l", buf)[0]
            if (num <= 0):
                print "(num <= 0):", num
                return (0, "")

            dataBuf = self.f.read(num)
            return (len(dataBuf), dataBuf)

        except IOError, err1:
            print err1
            return (-1, "")
        except MemoryError, err2:
            print err2, "num = ", num
            return (-2, "")
        except:
            print "Unexpected error:", sys.exc_info()[0]
            return (-3, "")


if __name__ == '__main__':
    #reader = BATReader("h:/MarketData/20081008bat.dat")
    reader = BATReader(r"g:\users\chenzg\workspace\TrlmMDC\branches\GndtMdc\testMinBar.dat")
    if 0 != reader.init():
        exit(1)

    packet_count = 0
    symbol_to_count = {}
    (dataLen, buf) = reader.read_data()
    while dataLen > 8:
        packet_count += 1
        head = buf[:8].split('\0')[0]
        if head == 'MINBAR':
            for i in range(8, dataLen, 36):
                if i+36 > dataLen:
                    continue
                (symbol, HHMMSS, open, hi, lo, close, denom, volume) = \
                    unpack("8sIIIIIII", buf[i:i+36])
                symbol = symbol.split('\0')[0]
                print symbol, HHMMSS, open, hi, lo, close, denom, volume

        else:
            for i in range(8, dataLen, 20):
                if i+20 > dataLen:
                    continue
                (symbol, ticktype, exchange, price, size, my_time) = \
                    unpack("6sccfli", buf[i:i+20])
                symbol = symbol.split('\0')[0]
                if ord(ticktype) == 3: # TRADE
                    if symbol_to_count.has_key(symbol):
                        symbol_to_count[symbol] += 1
                    else:
                        symbol_to_count[symbol] = 1

        if packet_count > 5000000:
            break
        (dataLen, buf) = reader.read_data()



    symbols = symbol_to_count.keys()
    symbols.sort(lambda a, b: symbol_to_count[b] - symbol_to_count[a])

    i = 1
    for symbol in symbols:
        print symbol
        #print i
        if (i == 500):
            break
        i += 1
