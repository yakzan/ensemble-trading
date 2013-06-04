from util import *
from perf_metrics import *
import struct

# --------------------------------------------------------------------------------
# Bars
# --------------------------------------------------------------------------------

class Bar:
    def __init__(self,  _date,  _open,  _high,  _low,  _close,  _volume,  _adj_close):
        self.date,  self.open,  self.high,  self.low,  self.close,  self.volume,  self.adj_close = \
            _date,  _open,  _high,  _low,  _close,  _volume,  _adj_close

    def __str__(self):
        return '%d, %.02f, %f, %f, %f, %d, %f' % (
            self.date,  self.open,  self.high,  self.low,  self.close,  self.volume,  self.adj_close)

class OneMinBar:
    def __init__(self,  _date, _time, _open,  _high,  _low,  _close,  _volume):
        self.date, self.open,  self.high,  self.low,  self.close,  self.volume= \
            _date * 10000 + _time, _open,  _high,  _low,  _close,  _volume

    def __str__(self):
        return '%d, %.02f, %f, %f, %f, %d' % (
            self.date,  self.open,  self.high,  self.low,  self.close,  self.volume)

class ShortOneMinBar:
    def __init__(self,  _date, _time, _open,  _high,  _low,  _close,  _volume):
        self.date, self.close= \
            _date * 10000 + _time, _close

    def __str__(self):
        return '%d, %.02f, %f' % (
            self.date, self.close)

# --------------------------------------------------------------------------------
# yahoo
# --------------------------------------------------------------------------------

def yahoo_to_bars(filename):
    f = open(filename)
    bars = []
    for line in f:
        if line.startswith('Date'):
            continue
        try:
            _date,  _open,  _high,  _low,  _close,  _volume,  _adj_close  = line.strip().split(',')
            _date = int(_date.replace('-',  ''))
            _open = float(_open)
            _high = float(_high)
            _low = float(_low)
            _close = float(_close)
            _volume = int(_volume)
            _adj_close = float(_adj_close)
            bar = Bar(_date,  _open,  _high,  _low,  _close,  _volume,  _adj_close)
            bars.append(bar)
        except:
            dump_exception()
            pass
    return bars

# --------------------------------------------------------------------------------
# 1min data
# --------------------------------------------------------------------------------

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
            bar = ShortOneMinBar(_date, _time, _open,  _high,  _low,  _close,  _volume)
            bars.append(bar)
        except ValueError:
            print line
            pass
        except:
            print line
            dump_exception()
            pass
    return bars

def onemincomp_to_bars(filename):
    f = open(filename, 'rb')
    bars = []

    while 1:
        buf = f.read(8*360*700)
        buf_len = len(buf)
        if buf_len <= 0:
            break
        #print buf_len, buf_len / 8 * 8
        buf_len = buf_len/8*8
        for i in range(0, buf_len, 8):
            try:
                dd2, tt2, p1, p2 = struct.unpack('<HHHH', buf[i:i+8])

                # dd2 = ((y - 2000) * 13 + M) * 32 + d
                y = dd2 / 32 / 13 + 2000
                M = dd2 / 32 % 13
                d = dd2 % 32

                h, m = tt2 / 60, tt2 % 60
                price = p1 + p2 * 0.01

                bar = ShortOneMinBar(y * 10000 + M * 100 + d, h * 100 + m,
                    price, price, price, price, 0)
                #print y, M, d, h, m, '####', bar.close, dd2, tt2, p1, p2, '####%d,%x'% (i, i), buf[i:i+8].encode('hex')
                bars.append(bar)
            except ValueError:
                pass
            except:
                dump_exception()
                pass
    f.close()
    return bars

def old_onemincomp_to_bars(filename):
    f = open(filename, 'rb')
    bars = []
    dates = []

    while 1:
        buf = f.read(8*360*700)
        buf_len = len(buf)
        if buf_len <= 0:
            break
        #print buf_len, buf_len / 8 * 8
        buf_len = buf_len/8*8
        for i in range(0, buf_len, 8):
            try:
                dd2, tt2, p1, p2 = struct.unpack('<HHHH', buf[i:i+8])
                y = dd2 / (13*32) + 2000
                d3 = dd2 - dd2 / (13*32) * (13*32)
                d = d3 % 32
                M = (d3-d) / 12 + 1
                if len(dates) == 0 or dates[-1] != d3:
                    dates.append(d3)
            except ValueError:
                pass
            except:
                dump_exception()
                pass
    f.close()
    #print dates

    last_date = -1
    last_mon = 1
    last_year = 2013
    new_dates = []
    for date in reversed(dates):
        y, M, d = 1, 1, 1
        if last_date == -1:
            y = 2013
            M = 1
            d = date - 13
        elif date > last_date:
            M = last_mon - 1
            y = last_year
            if M <= 0:
                M = 12
                y -= 1
            d = date - M * 13
        else:
            M = last_mon
            y = last_year
            d = date - M * 13
        last_year = y
        last_mon = M
        last_date = date
        new_dates.insert(0, (y, M, d))
    #print new_dates

    f = open(filename, 'rb')
    f2 = open(filename[:-3] + 'bin', 'wb')
    date_i = -1
    dates = []
    while 1:
        buf = f.read(8*360*700)
        buf_len = len(buf)
        if buf_len <= 0:
            break
        #print buf_len, buf_len / 8 * 8
        buf_len = buf_len/8*8
        for i in range(0, buf_len, 8):
            try:
                dd2, tt2, p1, p2 = struct.unpack('<HHHH', buf[i:i+8])

                d3 = dd2 - dd2 / (13*32) * (13*32)
                if len(dates) == 0 or dates[-1] != d3:
                    date_i += 1
                    dates.append(d3)
                y, M, d = new_dates[date_i]

                h, m = tt2 / 60, tt2 % 60
                price = p1 + p2 * 0.01
                bar = ShortOneMinBar(y * 10000 + M * 100 + d, h * 100 + m,
                    price, price, price, price, 0)
                if M * 13 + d != d3:
                    print d3, M*13 + d, M, d
                    raise 119

                #print y, M, d, h, m, '####', bar.close, dd2, tt2, p1, p2, '####%d,%x'% (i, i), buf[i:i+8].encode('hex')
                bars.append(bar)

                dd2 = (y % 100) * (13*32) + M * 32 + d
                f2.write(struct.pack('<HHHH', dd2, tt2, p1, p2))
            except ValueError:
                pass
            except:
                dump_exception()
                pass
    f.close()
    f2.close()
    return bars

def forex_to_bars(filename):
    f = open(filename)
    bars = []
    for line in f:
        # <TICKER>,<DATE>,<TIME>,<OPEN>,<LOW>,<HIGH>,<CLOSE>
        # EURUSD,20010103,00:00:00,0.9507,0.9262,0.9569,0.9271
        # EURUSD,20010104,00:00:00,0.9271,0.9269,0.9515,0.9507
        if line.startswith('<'):
            continue
        try:
            symbol, _date, _time, _open, _low, _high, _close = line.strip().split(',')
            _date = int(_date)
            _open = float(_open)
            _high = float(_high)
            _low = float(_low)
            _close = float(_close)
            _volume = 0
            _adj_close = _close
            bar = Bar(_date,  _open,  _high,  _low,  _close,  _volume,  _adj_close)
            bars.append(bar)
        except 1:
            pass
    return bars

def get_yahoo_file(symbol):
    return '../data/yahoo/table_%s.csv' % symbol

def get_onemin_file(symbol):
    return '../data/1min/%s_1.txt' % symbol

def get_onemincomp_file(symbol):
    return '../data/1min-comp-etf/%s_1.dat' % symbol
    #return '../data/1min-comp/%s_1.bin' % symbol

def get_old_onemincomp_file(symbol):
    return '../data/1min-comp/%s_1.dat' % symbol

def get_forex_file(symbol):
    return '../data/forex/%s_day.csv' % symbol

# --------------------------------------------------------------------------------
# SVM input files
# --------------------------------------------------------------------------------

class SvmData:
    YAHOO = 0
    ONE_MIN = 1
    FOREX = 2
    ONE_MIN_COMP = 3
    INPUT_RDP = 0
    INPUT_OVER_EMBEDDING = 1
    OUTPUT_RDP_EMA = 0
    OUTPUT_DIFF = 1
    OUTPUT_LOG_RETURN = 2
    OUTPUT_LOG_RETURN_EMA = 3

    def __init__(self, symbol, source, interval=1):
        self.source = source
        self.symbol = symbol
        self.set_settings()
        self.interval = interval
        if source == SvmData.YAHOO:
            self.bars = yahoo_to_bars(get_yahoo_file(symbol))
        elif source == SvmData.ONE_MIN:
            self.bars = onemin_to_bars(get_onemin_file(symbol))
        elif source == SvmData.ONE_MIN_COMP:
            self.bars = onemincomp_to_bars(get_onemincomp_file(symbol))
        elif source == SvmData.FOREX:
            self.bars = forex_to_bars(get_forex_file(symbol))

        if self.interval != 1:
            self.bars = self.convert_bars_to_interval(self.bars, self.interval)

    def convert_bars_to_interval(self, bars, interval):
        new_bars = []
        for i in range(interval-1, len(bars), interval):
            new_bars.append(bars[i])
        return new_bars

    def set_settings(self, portion_training=0.9, output_type=None, input_type=None, skip_front=None, skip_back=None):
        self.portion_training = portion_training

        if input_type is None:
            self.input_type = SvmData.INPUT_RDP
        else:
            self.input_type = input_type

        if output_type is None:
            self.output_type = SvmData.OUTPUT_LOG_RETURN_EMA
        else:
            self.output_type = output_type

        if skip_front is None:
            if self.source == SvmData.YAHOO:
                self.skip_front = 50
            else:
                self.skip_front = 200
        else:
            self.skip_front = skip_front

        if skip_back is None:
            self.skip_back = 5
        else:
            self.skip_back = skip_back

        dimension = 10
        time_delay = 5
        self.set_dimension_delay(dimension, time_delay)

    def set_dimension_delay(self, dimension, time_delay):
        self.dimension = dimension
        self.time_delay = time_delay
        if self.skip_back is None or self.skip_back < self.time_delay:
            self.skip_back = self.time_delay
        if self.skip_front is None or self.skip_front < self.time_delay * self.dimension:
            self.skip_front = self.time_delay * self.dimension

    def prepare_svm_lines(self, write_orig_files=0, write_svm_files=1, normalize=1, verbose=1):
        if verbose: print 'prepare svm files for %s, write_orig_files=%d, write_svm_files=%d, normalize=%d' % (
                self.symbol, write_orig_files, write_svm_files, normalize)
        #if verbose: print '%s: %d bars' % (symbol, len(self.bars))

        symbol = self.symbol

        self.desc = 'symbol=%s, source=%d, input=%d, output=%d, portion_training=%f, dimension=%d, time_delay=%d, num_bars=%d, normalize=%d, interval=%d' % (
                self.symbol, self.source, self.input_type, self.output_type, self.portion_training, self.dimension, self.time_delay, len(self.bars), normalize, self.interval)
        if verbose: print self.desc

        self.svm_lines = self.bars_to_svm_lines(self.bars)
        self.detailed_svm_lines = self.bars_to_svm_lines(self.bars, extended=1)
        self.num_svm_lines = len(self.svm_lines)
        num_training = int(self.portion_training * self.num_svm_lines)
        self.num_training = num_training
        if verbose: print '%s: %d svm lines, %d training' % (self.symbol, self.num_svm_lines, num_training)

        self.orig_svm_lines = self.svm_lines[:]
        self.orig_svm_lines_training = self.orig_svm_lines[0:num_training]
        self.orig_svm_lines_testing = self.orig_svm_lines[num_training:]
        if write_orig_files:
            write_svm_file(self.orig_svm_lines_training, '../data/svm/%s-training-orig.txt' % symbol)
            write_svm_file(self.orig_svm_lines_testing, '../data/svm/%s-testing-orig.txt' % symbol)
            write_svm_file(self.orig_svm_lines, '../data/svm/%s-all-orig.txt' % symbol)
            write_csv_file(self.orig_svm_lines_training, '../data/svm/%s-training-orig.csv' % symbol)
            write_csv_file(self.orig_svm_lines_testing, '../data/svm/%s-testing-orig.csv' % symbol)
            write_csv_file(self.orig_svm_lines, '../data/svm/%s-all-orig.csv' % symbol)

        self.normalize = normalize
        if normalize:
            self.svm_lines, self.scaling_map = normalize_svm_lines(self.svm_lines, '../data/svm/%s-scaling.txt' % self.symbol, verbose)
        else:
            self.svm_lines, self.scaling_map = self.svm_lines, None

        self.svm_lines_training = self.svm_lines[0:num_training]
        self.svm_lines_testing = self.svm_lines[num_training:]
        if write_svm_files:
            write_svm_file(self.svm_lines_training, '../data/svm/%s-training.txt' % symbol)
            write_svm_file(self.svm_lines_testing, '../data/svm/%s-testing.txt' % symbol)
            write_svm_file(self.svm_lines, '../data/svm/%s-all.txt' % symbol)
            write_csv_file(self.svm_lines_training, '../data/svm/%s-training.csv' % symbol)
            write_csv_file(self.svm_lines_testing, '../data/svm/%s-testing.csv' % symbol)
            write_csv_file(self.svm_lines, '../data/svm/%s-all.csv' % symbol)

        return self.bars, self.svm_lines, self.svm_lines_training, self.svm_lines_testing, self.scaling_map

    def bars_to_true_ranges(self, bars):
        true_ranges = []
        i = 0
        for i in range(len(bars)):
            bar = bars[i]
            #true_range = bar.high - bar.low
            true_range = 0
            if i > 0:
                last_bar = bars[i-1]
                pdc = last_bar.close
                #true_range = max(bar.high - bar.low, bar.high - pdc, pdc - bar.low)
                true_range = max(bar.close - pdc, pdc - bar.close)
            true_ranges.append(true_range)
        atrs = []
        for i in range(len(true_ranges)):
            atr = 0
            if i < 20:
                atr = sum(true_ranges[:i+1]) / (i+1)
            else:
                pdn = atrs[-1]
                atr = (19 * pdn + true_ranges[i]) / 20
            atrs.append(atr)
        return true_ranges, atrs

    def bars_to_svm_lines(self, bars, extended=0):
        bars.sort(lambda a, b: cmp(a.date, b.date))
        bar_values = [b.close for b in bars]
        true_ranges, atrs = self.bars_to_true_ranges(bars)
        svm_lines = []
        ema15_values = get_ema_arr(bar_values, 15)
        ema3_values = get_ema_arr(bar_values, 3)
        for i in range(self.skip_front, len(bar_values)-self.skip_back):
            svm_line = []

            # output
            output = 0
            if self.output_type == SvmData.OUTPUT_DIFF:
                output = bar_values[i+self.time_delay] - bar_values[i]
            elif self.output_type == SvmData.OUTPUT_RDP_EMA:
                output = rdp2(ema(ema3_values, i+self.time_delay, 3), ema(ema3_values, i, 3), 1)
            elif self.output_type == SvmData.OUTPUT_LOG_RETURN_EMA:
                output = math.log(ema(ema3_values, i+self.time_delay, 3)) - math.log(ema(ema3_values, i, 3))
            elif self.output_type == SvmData.OUTPUT_LOG_RETURN:
                output = math.log(bar_values[i+self.time_delay]) - math.log(bar_values[i])
            svm_line.append(output)

            # inputs
            if self.input_type == SvmData.INPUT_RDP:
                for j in range(self.time_delay, self.time_delay * self.dimension, self.time_delay):
                #for j in [5, 10, 15, 20, 25, 30, 35, 40, 45]:
                    svm_line.append(rdp(bar_values, i, j))

                ema_15 = rdp2(bar_values[i], ema(ema15_values, i, 15))
                svm_line.append(ema_15)

            elif self.input_type == SvmData.INPUT_OVER_EMBEDDING:
                for j in range(0, self.dimension*self.time_delay, self.time_delay):
                    svm_line.append(bar_values[i-j] - bar_values[i-self.time_delay-j])

            if extended:
                svm_line += [true_ranges[i], atrs[i]]
                if self.output_type == SvmData.OUTPUT_RDP_EMA or self.output_type == SvmData.OUTPUT_LOG_RETURN_EMA:
                    ema3_i5 = ema(ema3_values, i+self.time_delay, 3)
                    ema3_i = ema(ema3_values, i, 3)
                    svm_line += [ ema3_i5, ema3_i ]

                svm_line += [bar_values[i+self.time_delay], bar_values[i], bars[i].date]

            svm_lines.append(svm_line)

        return svm_lines

    def extended_to_normal_svm_lines(self, extended_svm_lines):
        svm_lines = []
        for extended_line in extended_svm_lines:
            if self.output_type == SvmData.OUTPUT_RDP_EMA or self.output_type == SvmData.OUTPUT_LOG_RETURN_EMA:
                svm_lines.append(extended_line[:-5])
            else:
                svm_lines.append(extended_line[:-3])
        return svm_lines

    def scale_back_prediction_results(self, prediction_results):
        scaling = 1
        if self.normalize:
            scaling = self.scaling_map[0]
        results = []
        for result in prediction_results:
            val = result * scaling
            results.append(val)
        return results

    def scale_back_prediction_result(self, prediction_result):
        scaling = 1
        if self.normalize:
            scaling = self.scaling_map[0]
        return prediction_result * scaling

    def convert_prediction_result(self, prediction_result, detailed_svm_line):
        predicted_output = self.scale_back_prediction_result(prediction_result)

        predicted_value = 0
        actual_value = 0
        next_price, cur_price, bar_date = detailed_svm_line[-3:]

        if self.output_type == SvmData.OUTPUT_DIFF:
            #output = bar_values[i+self.time_delay] - bar_values[i]
            predicted_next_price = cur_price + predicted_output
            predicted_value = predicted_next_price
            actual_value = next_price
        elif self.output_type == SvmData.OUTPUT_RDP_EMA:
            #output = rdp2(ema(ema3_values, i+self.time_delay, 3), ema(ema3_values, i, 3), use_rdp)
            ema3_i5, ema3_i = detailed_svm_line[-5:-3]
            predicted_next_price = (predicted_output / 100. + 1) * ema3_i # next ema, not next price
            predicted_value = predicted_next_price
            actual_value= ema3_i5
        elif self.output_type == SvmData.OUTPUT_LOG_RETURN_EMA:
            #output = math.log(ema(ema3_values, i+self.time_delay, 3)) - math.log(ema(ema3_values, i, 3))
            ema3_i5, ema3_i = detailed_svm_line[-5:-3]
            predicted_next_price = math.exp(math.log(ema3_i) + predicted_output) # next ema, not next price
            predicted_value = predicted_next_price
            actual_value = ema3_i5
        elif self.output_type == SvmData.OUTPUT_LOG_RETURN:
            #output = math.log(bar_values[i+self.time_delay]) - math.log(bar_values[i])
            predicted_next_price = math.exp(math.log(cur_price) + predicted_output)
            predicted_value = predicted_next_price
            actual_value = next_price

        return predicted_value, actual_value, cur_price, bar_date

    def convert_prediction_results_2(self, prediction_results, extended_svm_lines_testing, svm_train_param=''):
        actual_values = []
        for svm_line in extended_svm_lines_testing:
            actual_values.append(svm_line[0])
        get_and_save_perf_metrics(self.symbol, prediction_results, actual_values, svm_train_param=svm_train_param+', '+self.desc)

        prediction_results = self.scale_back_prediction_results(prediction_results)

        cmp_f = open_for_write(r'../data/result/%s-result-cmp.csv' % self.symbol, 'w')
        cmp_f.write('Date,Price(1+),Predicted Price(1+)\n')

        predicted_values = []
        actual_values = []
        for predicted_output, detailed_svm_line in zip(prediction_results, extended_svm_lines_testing):
            # svm_line += [bar_values[i+self.time_delay], bar_values[i], bars[i].date]
            next_price, cur_price, bar_date = detailed_svm_line[-3:]
            date_str = '%04d/%02d/%02d' % (bar_date/10000, bar_date%10000/100, bar_date%100)

            if self.output_type == SvmData.OUTPUT_DIFF:
                #output = bar_values[i+self.time_delay] - bar_values[i]
                predicted_next_price = cur_price + predicted_output
                predicted_values.append(predicted_next_price)
                actual_values.append(next_price)
            elif self.output_type == SvmData.OUTPUT_RDP_EMA:
                #output = rdp2(ema(ema3_values, i+self.time_delay, 3), ema(ema3_values, i, 3), use_rdp)
                ema3_i5, ema3_i = detailed_svm_line[-5:-3]
                predicted_next_price = (predicted_output / 100. + 1) * ema3_i # next ema, not next price
                predicted_values.append(predicted_next_price)
                actual_values.append(ema3_i5)
            elif self.output_type == SvmData.OUTPUT_LOG_RETURN_EMA:
                #output = math.log(ema(ema3_values, i+self.time_delay, 3)) - math.log(ema(ema3_values, i, 3))
                ema3_i5, ema3_i = detailed_svm_line[-5:-3]
                predicted_next_price = math.exp(math.log(ema3_i) + predicted_output) # next ema, not next price
                predicted_values.append(predicted_next_price)
                actual_values.append(ema3_i5)
            elif self.output_type == SvmData.OUTPUT_LOG_RETURN:
                #output = math.log(bar_values[i+self.time_delay]) - math.log(bar_values[i])
                predicted_next_price = math.exp(math.log(cur_price) + predicted_output)
                predicted_values.append(predicted_next_price)
                actual_values.append(next_price)

            cmp_line = [ date_str, actual_values[-1], predicted_values[-1] ]
            cmp_line_str = ','.join(map(str, cmp_line))
            cmp_f.write('%s\n' % (cmp_line_str))

        cmp_f.close()

        get_and_save_perf_metrics(self.symbol, predicted_values, actual_values, svm_train_param='CONVERTED, '+svm_train_param+', '+self.desc)

    def convert_prediction_results(self, prediction_results, svm_train_param=''):
        actual_values = []
        for svm_line in self.svm_lines_testing:
            actual_values.append(svm_line[0])
        get_and_save_perf_metrics(self.symbol, prediction_results, actual_values, svm_train_param=svm_train_param+', '+self.desc)

        prediction_results = self.scale_back_prediction_results(prediction_results)

        cmp_f = open_for_write(r'../data/result/%s-result-cmp.csv' % self.symbol, 'w')
        cmp_f.write('Date,Price(1+),Predicted Price(1+)\n')

        predicted_values = []
        actual_values = []
        for predicted_output, detailed_svm_line in zip(prediction_results, self.detailed_svm_lines[self.num_training:]):
            # svm_line += [bar_values[i+self.time_delay], bar_values[i], bars[i].date]
            next_price, cur_price, bar_date = detailed_svm_line[-3:]
            date_str = '%04d/%02d/%02d' % (bar_date/10000, bar_date%10000/100, bar_date%100)

            if self.output_type == SvmData.OUTPUT_DIFF:
                #output = bar_values[i+self.time_delay] - bar_values[i]
                predicted_next_price = cur_price + predicted_output
                predicted_values.append(predicted_next_price)
                actual_values.append(next_price)
            elif self.output_type == SvmData.OUTPUT_RDP_EMA:
                #output = rdp2(ema(ema3_values, i+self.time_delay, 3), ema(ema3_values, i, 3), use_rdp)
                ema3_i5, ema3_i = detailed_svm_line[-5:-3]
                predicted_next_price = (predicted_output / 100. + 1) * ema3_i # next ema, not next price
                predicted_values.append(predicted_next_price)
                actual_values.append(ema3_i5)
            elif self.output_type == SvmData.OUTPUT_LOG_RETURN_EMA:
                #output = math.log(ema(ema3_values, i+self.time_delay, 3)) - math.log(ema(ema3_values, i, 3))
                ema3_i5, ema3_i = detailed_svm_line[-5:-3]
                predicted_next_price = math.exp(math.log(ema3_i) + predicted_output) # next ema, not next price
                predicted_values.append(predicted_next_price)
                actual_values.append(ema3_i5)
            elif self.output_type == SvmData.OUTPUT_LOG_RETURN:
                #output = math.log(bar_values[i+self.time_delay]) - math.log(bar_values[i])
                predicted_next_price = math.exp(math.log(cur_price) + predicted_output)
                predicted_values.append(predicted_next_price)
                actual_values.append(next_price)

            cmp_line = [ date_str, actual_values[-1], predicted_values[-1] ]
            cmp_line_str = ','.join(map(str, cmp_line))
            cmp_f.write('%s\n' % (cmp_line_str))

        cmp_f.close()

        get_and_save_perf_metrics(self.symbol, predicted_values, actual_values, svm_train_param='CONVERTED, '+svm_train_param+', '+self.desc)

def rdp(bar_values, index, period, use_rdp=1):
    return rdp2(bar_values[index], bar_values[index-period], use_rdp)

def rdp2(val1, val2, use_rdp=1):
    if not use_rdp:
        # not using RDP: relative difference in percentage
        # because RDP will be too large when val2 is too small
        return val1 - val2
    else:
        if val2 <= 0.000001:
            return 100000;
        return 100 * (val1 - val2) / val2

def svm_line_to_str(svm_line):
    output_str = '%.12f' % svm_line[0]
    input_str = '\t'.join([ '%d:%.12f' % (j+1, a) for j, a in enumerate(svm_line[1:]) ])
    return '%s\t%s' % (output_str, input_str)

def write_svm_file(svm_lines, filename):
    f = open_for_write(filename, 'w')
    for svm_line in svm_lines:
        s = svm_line_to_str(svm_line)
        f.write(s)
        f.write('\n')
    f.close()

def svm_line_to_csv_str(svm_line):
    output_str = '%.12f' % svm_line[0]
    input_str = ','.join([ '%.12f' % (a) for j, a in enumerate(svm_line[1:]) ])
    return '%s,%s' % (output_str, input_str)

def write_csv_file(svm_lines, filename):
    f = open_for_write(filename, 'w')
    for svm_line in svm_lines:
        s = svm_line_to_csv_str(svm_line)
        f.write(s)
        f.write('\n')
    f.close()

# --------------------------------------------------------------------------------
# normalize svm lines
# --------------------------------------------------------------------------------
import math

def normalize_svm_lines(svm_lines, scaling_filename='', verbose=0):
    line_count = len(svm_lines)
    if line_count == 0:
        return svm_lines

    line_size = len(svm_lines[0])
    scaling_map = [1 for _ in range(line_size)]
    for j in range(line_size): # for each column
        svm_column = [b[j] for b in svm_lines] # series for the j-th column
        avg_a = sum(svm_column) / line_count
        stddev_a = math.sqrt(sum([(b - avg_a)**2 for b in svm_column]) / (line_count - 1))
        upper_a = avg_a + 2*stddev_a
        lower_a = avg_a - 2*stddev_a

        # replace outliers
        max_abs_a = 0
        for i in range(line_count):
            if svm_column[i] > upper_a:
                svm_column[i] = upper_a
            elif svm_column[i] < lower_a:
                svm_column[i] = lower_a
            if abs(svm_column[i]) > max_abs_a:
                max_abs_a = abs(svm_column[i])

        scaling_map[j] = max_abs_a / 0.9

        # scale to [-0.9, 0.9]
        for i in range(line_count):
            svm_column[i] = svm_column[i] * 0.9 / max_abs_a
            svm_lines[i][j] = svm_column[i]

    scaling_str = ','.join(map(str, scaling_map))
    if verbose: print 'scaling: %s' % ',\t'.join(map(str, scaling_map))
    if scaling_filename:
        f = open_for_write(scaling_filename, 'a+')
        f.write('%s\n' % scaling_str)
        f.close()

    return svm_lines, scaling_map

def load_scaling_map(symbol, filename=None):
    if filename is None:
        filename = '../data/svm/%s-scaling.txt' % symbol
    scaling_f = open(filename)
    scaling_map = scaling_f.readlines()[-1].strip().split(',')
    scaling_map = map(float, scaling_map)
    scaling_f.close()
    return scaling_map

def get_ema_arr(s, n):
    """
    returns an n period exponential moving average for
    the time series s

    s is a list ordered from oldest (index 0) to most
    recent (index -1)
    n is an integer

    returns a numeric array of the exponential
    moving average
    """
    ema = []
    j = 1

    #get n sma first and calculate the next n period ema
    sma = sum(s[:n]) / n
    multiplier = 2 / float(1 + n)
    ema.append(sma)

    #EMA(current) = ( (Price(current) - EMA(prev) ) x Multiplier) + EMA(prev)
    ema.append(( (s[n] - sma) * multiplier) + sma)

    #now calculate the rest of the values
    for i in s[n+1:]:
        tmp = ( (i - ema[j]) * multiplier) + ema[j]
        j = j + 1
        ema.append(tmp)

    return ema

def ema(ema_values, i, period):
    return ema_values[i - period + 1]

if __name__ == '__main__':
    data = SvmData('AGG', source=SvmData.ONE_MIN_COMP)
    bars = data.bars
    #data.prepare_svm_lines()
    for bar in bars:
        print bar
    raise 1

    for symbol in ['AORD', 'DJI', 'GE', 'HSI', 'KS11', 'Nikkei225']:
        try:
            data = SvmData(symbol, source=SvmData.YAHOO)
            bars = data.bars
            data.prepare_svm_lines()
        except:
            print symbol, 'Failed.'
            dump_exception(0)
    for symbol in ['IBM', 'AAPL', 'SPY']:
        try:
            data = SvmData(symbol, source=SvmData.ONE_MIN)
            bars = data.bars
            data.prepare_svm_lines()
        except:
            print symbol, 'Failed.'
            dump_exception(0)
