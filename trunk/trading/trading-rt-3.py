# partition data in to several overlapping parts.
# the train each partition using SVM, with C, gamma selected using grid search.

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
from multiprocessing import Process, Queue
import threading
import socket
import uuid
from batreader import *

logger = 0
log_dir = ''
total_instances = 4
ensemble_predictors = []
tradebot_client = None
cur_date = 0
tradable_time_ranges = [('09:40', '11:20'), ('13:10', '15:30')]

MIN_FLOAT = 0.00001
MIN_FILL_DELAY = 1
MIN_FILL_PRICE_GAP = 0.0

def is_zero(price):
    return price <= MIN_FLOAT

def simple_partition_svm_lines(svm_lines_training, MIN_PARTITION_SIZE):
    MIN_PARTITION_SIZE = int(MIN_PARTITION_SIZE)
    partitions = []
    for i in range(0, len(svm_lines_training), MIN_PARTITION_SIZE):
        if i+MIN_PARTITION_SIZE <= len(svm_lines_training) or len(partitions) == 0:
            partitions.append(svm_lines_training[i:i+MIN_PARTITION_SIZE])
        else:
            partitions[-1] += svm_lines_training[i:len(svm_lines_training)]
    return partitions


def simple_partition_svm_lines_random(svm_lines_training, MIN_PARTITION_SIZE):
    MIN_PARTITION_SIZE = int(MIN_PARTITION_SIZE)
    partitions = []
    for i in range(0, len(svm_lines_training), MIN_PARTITION_SIZE):
        partition = []
        for j in range(0, len(svm_lines_training)):
            p = MIN_PARTITION_SIZE * 1.0 / len(svm_lines_training)
            r = random()
            if r <= p:
                partition.append(svm_lines_training[j])
                if len(partition) >= MIN_PARTITION_SIZE:
                    break
        partitions.append(partition)
    return partitions

def save_settings(argv, timestamp, instance_num):

    global logger
    global log_dir

    this_file = argv[0]

    log_dir = '../results/%s-%s' % (
            this_file,
            timestamp)
    log_file = os.path.join(log_dir, 'log.txt')
    if instance_num != -1:
        log_file = os.path.join(log_dir, 'log_%d.txt' % instance_num)
    if instance_num == -1 or instance_num == 0:
        ensure_dir(log_file)
        shutil.copy(this_file, log_dir)
        shutil.copy('settings.py', log_dir)
        if len(sys.argv) > 1:
            shutil.copy(sys.argv[1], log_dir)

    if logger == 0:
        logger = logging.getLogger()
        hdlr = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s %(message)s')
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr)
        logger.setLevel(logging.DEBUG)

        logger.info(repr(argv))

class QuickSetup:

    def __init__(self, position_manager, symbol, price, size, stoploss, takeprofit,
            holding_period, setup_time, predicted_value):

        self.position_manager = position_manager
        self.symbol, self.price, self.size, self.stoploss, self.takeprofit, \
                self.holding_period, self.setup_time, self.predicted_value = \
                symbol, price, size, stoploss, takeprofit, \
                holding_period, setup_time, predicted_value

        self.uuid = str(uuid.uuid1())
        self.time_to_live = 120 #FIXME

        self.status = 'init'

        self.setup_id = 0
        self.broker_order_id = ''
        self.order_id = 0

        self.fill_time = 0
        self.fill_price = 0

        self.closing_time = 0
        self.close_price = 0

        self.closed_time = 0
        self.closed_price = 0
        self.pnl = 0

        self.send()

    def send(self):
        global tradebot_client
        tradebot_client.send_trade_setup(self)

    def try_cancel(self, cur_time):
        if self.status in ['init', 'chasing'] and cur_time - self.setup_time >= self.time_to_live:
            self.status = 'cancelling'
            tradebot_client.cancel_setup(self)
            return 'CT_%s_at_%s ' % (stime(self.setup_time), stime(cur_time))
        return ''

    def try_chase(self, cur_time, bid, ask):
        if self.status in ['init'] and cur_time - self.setup_time >= 30:
            if (self.size > 0 and ask > 0 and self.predicted_value >= ask) or \
                    (self.size < 0 and bid > 0 and self.predicted_value <= bid):
                self.status = 'chasing'
                self.chase_price = ask
                if self.size < 0:
                    self.chase_price = bid
                self.chasing_time = cur_time
                tradebot_client.chase_setup(self, self.chase_price)
                return 'CH_%s_%.3f_%d_at_%s ' % (
                        stime(self.setup_time), self.chase_price, self.size,
                        stime(cur_time))
        return ''

    def try_time_stop(self, cur_time, bid, ask):
        if (self.status in ['filled'] and cur_time - self.fill_time >= self.holding_period * 60 + 60) or \
                (self.status in ['closing'] and cur_time - self.closing_time >= 60):

                close_price = bid
                if self.status == 'closing':
                    # more greedy
                    if 0:
                        if self.size > 0: # close long
                            close_price = bid
                        else:
                            close_price = ask
                    else:
                        close_price = 0
                else:
                    if self.size > 0: # close long
                        close_price = ask
                    else:
                        close_price = bid

                self.try_close(cur_time, close_price)
                return 'CA_%s_%.3f_%d_at_%s ' % (
                        stime(self.setup_time), close_price, self.size,
                        stime(cur_time))
        return ''

    def try_close(self, cur_time, close_price):
        self.status = 'closing'
        self.closing_time = cur_time
        self.close_price = close_price
        tradebot_client.close_position(self, self.close_price)


class PositionManager:
    """ manager positions for an ensemble predictor """

    def __init__(self, symbol, holding_period):
        self.symbol = symbol
        self.holding_period = holding_period # in minute
        self.trades = []
        self.initial_buying_power = 100000
        self.balance = self.initial_buying_power
        self.equity = self.initial_buying_power
        self.open_position_size = 0
        self.positions_size = 0
        self.positions_price = 0
        self.total_pnl = 0
        self.total_trades = 0
        self.total_shares = 0
        self.price = 0
        self.bid = 0
        self.ask = 0

    def roll_forward_working_date(self, new_date):
        self.trades = []
        self.open_position_size = 0
        self.price = 0
        self.bid = 0
        self.ask = 0

    def write_line(self, cur_time, cur_price, predicted_value=0,
            atr=0, stoploss=0, takeprofit=0,
            size_per_trade=0, cur_size=0, trade_size=0,
            cur_pnl=0, comment=''):

        diff = 0
        if predicted_value > 0:
            diff = predicted_value - cur_price
        pnl_per_share = 0
        if self.total_shares != 0:
            pnl_per_share = self.total_pnl / abs(self.total_shares)

        line = '%s %s, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %d, %d, %d, %d, %.4f, %.4f, %.4f, %s' % (
            sdate(cur_date), stime(cur_time),
            cur_price, predicted_value, atr, diff, cur_price, stoploss, takeprofit,
            size_per_trade, cur_size, trade_size, self.open_position_size,
            self.total_pnl, pnl_per_share, cur_pnl, comment)
        print >>self.f_out, line
        self.f_out.flush()

        if comment:
            line = self.symbol + ',' + line
            logger.debug(line)
            print line

    def write_trade(self, cur_time, price, size):
        print >>self.f_trade, '%s %s, %s, %.4f, %d, %d' % (
                sdate(cur_date), stime(cur_time),
                self.symbol, price, size, self.open_position_size)
        self.f_trade.flush()

    def write_order(self, cur_time, price, size):
        print >>self.f_order, '%s %s, %s, %.4f, %d' % (
                sdate(cur_date), stime(cur_time),
                self.symbol, price, size)
        self.f_order.flush()

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, cur_time = bat
        if symbol != self.symbol:
            return ''
        if ticktype == 1:
            self.bid = price
            return
        if ticktype == 2:
            self.ask = price
            return
        if ticktype != 3:
            return
        self.price = price

        comment = ''
        for qs in self.trades:
            ret = qs.try_cancel(cur_time)
            if ret:
                comment += ret

            ret = qs.try_chase(cur_time, self.bid, self.ask)
            if ret:
                comment += ret

            ret = qs.try_time_stop(cur_time, self.bid, self.ask)
            if ret:
                comment += ret

        if not comment:
            return

        self.write_line(cur_time, price, comment=comment)

    def is_tradable_time(self, cur_time):
        for t_begin, t_end in tradable_time_ranges:
            if cur_time >= t_begin and cur_time <= t_end:
                return True
        return False


    def handle_trade_signal(self, atr, avg_price, predicted_value, cur_price, cur_time):
        #print 'trade signal:', atr, avg_price, predicted_value, cur_price, cur_time
        if atr <= MIN_FLOAT:
            atr = MIN_FLOAT

        size_per_trade = self.size_per_trade

        buy_price = cur_price
        if self.bid > MIN_FLOAT and self.bid < self.ask:
            buy_price = min(self.bid, ceil(predicted_value * 100 - 0.001) / 100)
        #buy_price += 0.01

        sell_price = cur_price
        if self.ask > MIN_FLOAT and self.bid < self.ask:
            sell_price = max(self.ask, ceil(predicted_value * 100 - 0.001) / 100)
        #sell_price -= 0.01

        cur_size = 0
        stoploss = 0
        takeprofit = 0
        atr = abs(atr)
        min_change = atr / 3
        max_change = atr * 3
        diff = predicted_value - cur_price
        if diff > 0 and diff >= min_change and diff < max_change:
            # predicted UP, then buy
            cur_size += size_per_trade
            stoploss   = ceil ((buy_price - atr * 3) * 100 - 0.001) / 100
            takeprofit = floor((buy_price + atr * 3) * 100 + 0.001) / 100
        elif diff < 0 and abs(diff) >= min_change and abs(diff) < max_change:
            # predicted DOWN, then sell
            cur_size -= size_per_trade
            stoploss   = floor((sell_price + atr * 3) * 100 - 0.001) / 100
            takeprofit = ceil ((sell_price - atr * 3) * 100 + 0.001) / 100

        comment = ''
        trade_size = 0

        if cur_size != 0 and self.is_tradable_time(cur_time):
            logger.debug('%s, symbol=%s, cur_price=%f, cur_size=%d, stoploss=%f, takeprofit=%f, holding_period=%d' % (
                stime(cur_time), self.symbol, cur_price, cur_size, stoploss, takeprofit, self.holding_period))
            trade_size = cur_size
            trade_price = buy_price
            if trade_size < 0:
                trade_price = sell_price
            comment += 'NT_%s_%.3f_%d (bid %.3f ask %.3f) ' % (
                    stime(cur_time), trade_price, trade_size, self.bid, self.ask)
            self.write_order(cur_time, trade_price, trade_size)
            trade = QuickSetup(self, self.symbol, trade_price, trade_size, stoploss, takeprofit, self.holding_period, cur_time, predicted_value)
            self.trades.append(trade)

        cur_pnl = 0
        self.write_line(cur_time, cur_price, predicted_value, atr, stoploss, takeprofit,
                size_per_trade, cur_size, trade_size,
                cur_pnl, comment)


    def handle_position_update(self, qs, update):
        symbol, shares, price, cur_time, reason = update
        if symbol != self.symbol:
            return

        if shares != 0 and qs.status in ['init', 'chasing', 'cancelling']:
            qs.status = 'filled'
            qs.fill_time = cur_time
            if price > MIN_FLOAT:
                qs.fill_price = price
            elif self.price > MIN_FLOAT:
                qs.fill_price = self.price
            else:
                qs.fill_price = qs.price
            self.open_position_size += qs.size
            self.total_trades += 1
            self.total_shares += abs(shares)

            comment = 'PF_%s_%.3f_%d_%s_at_%s ' % (
                stime(qs.setup_time), price, shares, reason,
                stime(cur_time))

            self.write_line(cur_time, self.price, comment=comment)
            self.write_trade(cur_time, price, shares)

        elif shares == 0 and qs.status in ['filled', 'closing']:
            qs.status = 'closed'
            qs.closed_time = cur_time
            qs.closed_price = self.price # FIXME:
            qs.pnl = (qs.closed_price - qs.fill_price) * qs.size
            self.open_position_size -= qs.size
            self.total_trades += 1
            self.total_shares += abs(qs.size)
            self.total_pnl += qs.pnl
            self.balance += qs.pnl
            self.equity += qs.pnl # FIXME

            comment = 'PC_%s_(%.4f->%.4f)_%d_%s_at_%s ' % (
                    stime(qs.setup_time),
                    qs.fill_price, qs.closed_price, qs.size, reason,
                    stime(cur_time))

            self.write_line(cur_time, self.price, cur_size=(-qs.size), cur_pnl=qs.pnl, comment=comment)
            self.write_trade(cur_time, price, -qs.size)

        #FIXME: calculate positions_price, equity


class EnsemblePredictor:
    def __init__(self, first_day, symbol, interval=1, delay=1, dimension=5, gamma=0.0001, epsilon=0.001, num_partitions=200):
        self.symbol, self.interval, self.delay, dimension = symbol, interval, delay, dimension
        self.gamma, self.epsilon = gamma, epsilon
        self.num_partitions_to_keep = num_partitions

        self.svm_data = SvmData(symbol, SvmData.ONE_MIN, interval, first_day)
        self.svm_data.set_settings(portion_training=1)
        self.svm_data.set_dimension_delay(dimension, delay)

        self.position_manager = PositionManager(self.symbol, self.delay * 2)

    def train(self):
        fixed_gamma = self.gamma
        fixed_epsilon = self.epsilon
        use_random_partition = 0
        verbose = 0

        symbol = self.symbol
        data = self.svm_data
        if len(data.bars) > 20000:
            data.bars = data.bars[-20000:]
        data.prepare_svm_lines(verbose=verbose)

        extended_svm_lines = data.detailed_svm_lines[:]
        num_training = int(len(extended_svm_lines) * data.portion_training)
        extended_svm_lines_training = extended_svm_lines[:num_training]
        extended_svm_lines_testing = extended_svm_lines[num_training:]

        svm_lines_training = data.extended_to_normal_svm_lines(extended_svm_lines_training)
        svm_lines_testing = data.extended_to_normal_svm_lines(extended_svm_lines_testing)

        prices = [line[-2] for line in extended_svm_lines]
        self.avg_price = sum(prices) / len(prices)
        changes = [abs(line[-3] - line[-2]) / line[-2] for line in extended_svm_lines]
        self.max_change = max(changes)

        logger.info('%s: avg_price=%.4f, max_change=%.4f, num_svm_lines=%d' % (
            self.symbol, self.avg_price, self.max_change, len(extended_svm_lines)))

        arr_atr = [abs(line[-6]) for line in extended_svm_lines]
        self.avg_atr = sum(arr_atr) / len(arr_atr)
        self.stddev_atr = math.sqrt(sum([(b - self.avg_atr) ** 2 for b in arr_atr]) / len(arr_atr))

        if 1:
            if self.avg_atr <= 0.005:
                self.lower_atr = min(0.002, self.avg_atr)
            elif self.avg_atr <= 0.010:
                self.lower_atr = 0.009
            else:
                self.lower_atr = 0.015

            if self.stddev_atr > 0.004 and self.stddev_atr < 0.01:
                self.upper_atr = 0.100
            else:
                self.upper_atr = 0.080
            if self.upper_atr < self.avg_atr:
                self.upper_atr = self.avg_atr + 3 * self.stddev_atr

        logger.info('%s: avg_atr=%.4f, lower_atr=%.4f, upper_atr=%.4f (stddev_atr=%.4f)' % (self.symbol, self.avg_atr, self.lower_atr, self.upper_atr, self.stddev_atr))
        print '%s: avg_atr=%.4f, lower_atr=%.4f, upper_atr=%.4f (stddev_atr=%.4f)' % (self.symbol, self.avg_atr, self.lower_atr, self.upper_atr, self.stddev_atr)

        size_per_trade = int(min(10000 / self.avg_price, 100000 * 0.05 / self.avg_atr)) / 10 * 10
        if size_per_trade <= 50:
            size_per_trade = 50
        if size_per_trade >= 300:
            size_per_trade = 300
        self.position_manager.size_per_trade = size_per_trade
        logger.info('%s: size_per_trade=%d' % (self.symbol, size_per_trade))

        f_out_name = os.path.join(log_dir, '%s_i%d_d%d_g%f_e%f.csv' % (
            symbol, data.interval, data.time_delay, fixed_gamma, fixed_epsilon))
        self.f_out = open(f_out_name, 'w')
        self.position_manager.f_out = self.f_out

        logger.debug('%s: %d lines' % (f_out_name, len(extended_svm_lines)))

        print >>self.f_out, 'date_str, cur_price, predicted_value, atr, diff, cur_price, stoploss, takeprofit, size_per_trade, cur_size, trade_size, open_position_size, total_pnl, pnl_per_share, cur_pnl, comment'

        f_order_name = os.path.join(log_dir, '%s_i%d_d%d_g%f_e%f_orders.csv' % (
            symbol, data.interval, data.time_delay, fixed_gamma, fixed_epsilon))
        self.f_order = open(f_order_name, 'w')
        self.position_manager.f_order = self.f_order
        print >>self.f_order, 'time, symbol, price, qty, curr pty'

        f_trade_name = os.path.join(log_dir, '%s_i%d_d%d_g%f_e%f_trades.csv' % (
            symbol, data.interval, data.time_delay, fixed_gamma, fixed_epsilon))
        self.f_trade = open(f_trade_name, 'w')
        self.position_manager.f_trade = self.f_trade
        print >>self.f_trade, 'time, symbol, price, qty'

        MIN_PARTITION_SIZE = 30
        if MIN_PARTITION_SIZE > len(svm_lines_training):
            MIN_PARTITION_SIZE = len(svm_lines_training)

        # choose subsets from the training data

        partitions = []
        i = 1
        while MIN_PARTITION_SIZE * i <= len(svm_lines_training):
            new_partitions = []
            if use_random_partition:
                new_partitions = simple_partition_svm_lines_random(svm_lines_training, MIN_PARTITION_SIZE * i)
                partitions += new_partitions
            else:
                new_partitions = simple_partition_svm_lines(svm_lines_training, MIN_PARTITION_SIZE * i)
                partitions += new_partitions
            if len(new_partitions) == 1:
                break
            i *= 1.5

        # train each partition using SVM

        self.svm_models = []
        for i, partition in enumerate(partitions):
            # only use the bigger partitions for training
            if i < len(partitions) - self.num_partitions_to_keep:
                continue

            y, x = svm_problem_from_svm_lines(partition)
            svm_model, C, gamma, epsilon, acc = svm_train_with_stddev_gamma_epsilon(y, x, fixed_gamma, fixed_epsilon, verbose=0)[:5]
            self.svm_models.append(svm_model)

        self.num_models = len(self.svm_models)
        self.model_weights = [1.0/self.num_models] * self.num_models

        data.bars = data.bars[-300:]
        data.bars_in_cur_date = 0
        data.svm_lines = []
        data.svm_lines_training = []
        data.svm_lines_testing = []
        data.detailed_svm_lines = []
        data.orig_svm_lines = []
        data.orig_svm_lines_training = []
        data.orig_svm_lines_testing = []

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, cur_time = bat
        if symbol != self.symbol:
            return
        #print bat

        self.position_manager.update_with_bat(bat)

        r = self.svm_data.update_with_bat(bat)
        # skip the first few bars. FIXME: how many?
        if r is None or self.svm_data.bars_in_cur_date <= 5:
            return
        svm_line, extended_svm_line = r
        #print self.symbol, svm_line, extended_svm_line

        # predict using only models with relatively high weights

        # set weights (rule out some models)
        real_weights = self.model_weights[:]
        real_weights.sort()
        pivot_weight = real_weights[-self.num_models/4]
        for i, weight in enumerate(self.model_weights):
            if weight >= pivot_weight:
                real_weights[i] = weight # use it
            else:
                real_weights[i] = 0 # don't use it

        # normalize weights
        sum_weights = sum(real_weights)
        if sum_weights == 0:
            real_weights = [1.0/self.num_models] * self.num_models
        else:
            for i in range(self.num_models):
                real_weights[i] = real_weights[i] / sum_weights


        # predict: weighted sum of the prediction results
        predicted = 0
        temp_results = []
        for i in range(len(self.svm_models)):
            temp_result = svm_predict_svm_line(svm_line, self.svm_models[i], verbose=0)
            temp_results.append(temp_result)
            predicted += temp_result * real_weights[i]

        # update model weights
        abs_diffs = []
        for i in range(self.num_models):
            abs_diff = abs(temp_results[i] - svm_line[0])
            abs_diffs.append(abs_diff)
        sum_diffs = sum(abs_diffs)
        if sum_diffs == 0:
            sum_diffs = 0.1
        avg_diff = sum_diffs / self.num_models

        for i in range(self.num_models):
            self.model_weights[i] += 1.0 / self.num_models - (abs_diffs[i] ** 2 - avg_diff ** 2) / (avg_diff ** 2)
            if self.model_weights[i] < 0:
                self.model_weights[i] = 0

        # normalize weights
        sum_weights = sum(self.model_weights)
        if sum_weights == 0:
            self.model_weights = [1.0 / self.num_models] * self.num_models
        else:
            for i in range(self.num_models):
                self.model_weights[i] = self.model_weights[i] / sum_weights

        predicted_value, fake_actual_value, cur_price, bar_date = self.svm_data.convert_prediction_result(predicted, extended_svm_line)

        # trading
        atr = abs(extended_svm_line[-6])
        #if atr < 0.015 or atr > 0.070: return
        if atr >= self.lower_atr and atr <= self.upper_atr:
            self.position_manager.handle_trade_signal(atr, self.avg_price, predicted_value, price, cur_time)

    def roll_forward_working_date(self, new_date):
        global cur_date
        print 'new date', new_date
        logger.info('new date: %d', new_date)
        cur_date = new_date
        self.svm_data.roll_forward_working_date(new_date)
        self.position_manager.roll_forward_working_date(new_date)

def main_worker(timestamp, instance_num):
    global logger
    global ensemble_predictors

    save_settings(sys.argv, timestamp, instance_num)

    my_ensemble_predictors = ensemble_predictors[:]
    if instance_num != -1:
        n = len(ensemble_predictors)
        n2 = n / total_instances
        if n % total_instances != 0:
            n2 += 1
        my_ensemble_predictors = ensemble_predictors[instance_num * n2 : instance_num * n2 + n2]

    print 'main_worker %d, %d ensemble predictors' % (instance_num, len(my_ensemble_predictors))
    logger.info('main_worker %d, %d ensemble predictors' % (instance_num, len(my_ensemble_predictors)))
    logger.debug('\n'.join(['%s, interval=%d, delay=%d' % (p.symbol, p.interval, p.delay) for p in my_ensemble_predictors]))

    for ensemble_predictor in my_ensemble_predictors:
        ensemble_predictor.train()

    print 'main_worker %d done!' % instance_num

class FakeMarketDataReceiver(threading.Thread):
    def __init__(self, port):
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        orig_files = glob.glob(settings.playback_bat_file_glob)
        if len(orig_files) == 1:
            working_date = cur_date
            f = orig_files[0]
            print working_date, f
            self.play_batfile(f, working_date)
        else:
            first_date = settings.first_date_of_playback
            last_date  = settings.last_date_of_playback

            orig_files.sort()
            for f in orig_files:
                working_date = int(os.path.basename(f)[:8])
                print working_date, f
                if working_date >= first_date and working_date <= last_date:
                    self.play_batfile(f, working_date)
                    time.sleep(2)

    def play_batfile(self, batfile, working_date):

        self.flag_pause = 0
        self.flag_stop = 0

        self.reader = BATReader(batfile)
        if 0 != self.reader.init():
            print 'Failed to open BAT file.'
            return

        for ensemble_predictor in ensemble_predictors:
            ensemble_predictor.roll_forward_working_date(working_date)
        tradebot_client.roll_forward_working_date(working_date)

        while not self.flag_stop:
            if self.flag_pause:
                time.sleep(0.1)
                continue

            (data_len, buf) = self.reader.read_data()
            if data_len <= 8:
                break

            head = buf[:8].split('\0')[0]
            if head == 'BAT':
                for i in range(8, data_len, 20): # 20: length of a BAT structure
                    if i+20 > data_len:
                        continue
                    (symbol, ticktype, exchange, price, size, cur_time) = \
                        unpack("6sccfli", buf[i:i+20])
                    ticktype = ord(ticktype)
                    if cur_time < 9*3600 + 29*60:
                        continue
                    if symbol.find('\0') > 0:
                        symbol = symbol.split('\0')[0]
                    price = ceil(price * 100 - 0.01) / 100
                    bat = symbol, ticktype, exchange, price, size, cur_time

                    for ensemble_predictor in ensemble_predictors:
                        ensemble_predictor.update_with_bat(bat)
                    if tradebot_client is not None:
                        tradebot_client.update_with_bat(bat)

        print 'Finished reading BAT file.'

        self.reader.term()


class MarketDataReceiver(threading.Thread):
    def __init__(self, port):
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('', self.port))
            self.f_packet = open_for_write(os.path.join(log_dir, 'logBAT.dat'), 'wb')
            self.symbols = [p.symbol for p in ensemble_predictors]

            print 'Market data receiver has been started on port %d' % self.port
            while True:
                buf = self.sock.recv(10240)
                dataLen = len(buf)
                if dataLen <= 8:
                    continue
                should_write = 0
                header = buf[:8].split('\0')[0]
                if header == 'BAT':
                    for i in range(8, dataLen, 20):
                        if i+20 > dataLen:
                            continue
                        symbol, ticktype, exchange, price, size, cur_time = \
                                struct.unpack('6sccfli', buf[i:i+20])
                        ticktype = ord(ticktype)
                        if cur_time < 9*3600 + 29*60:
                            continue
                        if symbol.find('\0') > 0:
                            symbol = symbol.split('\0')[0]
                        if symbol in self.symbols:
                            should_write = 1
                        else:
                            continue
                        price = ceil(price * 100 - 0.01) / 100
                        bat = symbol, ticktype, exchange, price, size, cur_time

                        for ensemble_predictor in ensemble_predictors:
                            ensemble_predictor.update_with_bat(bat)
                        if tradebot_client is not None:
                            tradebot_client.update_with_bat(bat)
                elif header == 'DATE':
                    new_date = struct.unpack('i', buf[8:12])[0]
                    for ensemble_predictor in ensemble_predictors:
                        ensemble_predictor.roll_forward_working_date(new_date)
                    tradebot_client.roll_forward_working_date(new_date)

                if should_write:
                    self.f_packet.write(struct.pack('i', dataLen) + buf)
                    self.f_packet.flush()
        except:
            dump_exception()

class FakeTradebotClient:
    def __init__(self, user_id, password):
        self.user_id = user_id
        self.password = password

        self.trades = {}
        self.close_position_requests = {}
        self.cancel_setup_requests = {}
        self.chase_setup_requests = {}
        self.position_update_subject = ''
        self.pnl_update_subject = ''
        self.om_subject = ''
        self.execution_update_subject = ''
        self.quicksetup_response_suejct = ''
        self.max_size_per_trade = 3000

        self.global_setup_id = 0

        self.logged_in = False
        self.login()

    def roll_forward_working_date(self, new_date):
        self.trades = {}
        self.close_position_requests = {}
        self.cancel_setup_requests = {}
        self.chase_setup_requests = {}

    def login(self):
        self.logged_in = True

    def send_trade_setup(self, qs):
        self.trades[qs.uuid] = qs
        self.global_setup_id += 1
        qs.setup_id = self.global_setup_id

    def close_position(self, qs, close_price):
        if qs.setup_id == 0:
            return
        self.close_position_requests[qs.uuid] = qs

    def cancel_setup(self, qs):
        self.cancel_setup_requests[qs.uuid] = qs

    def chase_setup(self, qs, chase_price):
        if qs.setup_id == 0:
            return
        self.chase_setup_requests[qs.uuid] = qs

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, cur_time = bat
        if ticktype != 3:
            return

        for qs in self.trades.values():
            if qs.symbol != symbol:
                continue
            if qs.status in ['init', 'chasing']:
                if self.cancel_setup_requests.has_key(qs.uuid):
                    qs.status = 'cancelled'
                    del self.cancel_setup_requests[qs.uuid]
                    update = symbol, 0, -1, cur_time, 'cancelled'
                    qs.position_manager.handle_position_update(qs, update)
                elif self.chase_setup_requests.has_key(qs.uuid):
                    if cur_time - qs.chasing_time >= MIN_FILL_DELAY and \
                            ticktype == 3 and \
                            size >= abs(qs.size) and \
                            (is_zero(qs.chase_price) or
                            (qs.size > 0 and price <= qs.chase_price - MIN_FILL_PRICE_GAP) or
                            (qs.size < 0 and price >= qs.chase_price + MIN_FILL_PRICE_GAP)):
                        del self.chase_setup_requests[qs.uuid]
                        # fill
                        #update = symbol, qs.size, qs.chase_price, cur_time, 'chase_filled'
                        fill_price = qs.chase_price
                        if qs.chase_price <= MIN_FILL_PRICE_GAP:
                            fill_price = price
                        update = symbol, qs.size, fill_price, cur_time, 'chase_filled'
                        qs.position_manager.handle_position_update(qs, update)
                elif cur_time - qs.setup_time >= MIN_FILL_DELAY and \
                        ticktype == 3 and \
                        size >= abs(qs.size) and \
                        (is_zero(qs.price) or
                        (qs.size > 0 and price <= qs.price - MIN_FILL_PRICE_GAP) or
                        (qs.size < 0 and price >= qs.price + MIN_FILL_PRICE_GAP)):
                    # fill
                    #update = symbol, qs.size, qs.price, cur_time, 'filled'
                    fill_price = qs.price
                    if is_zero(fill_price):
                        fill_price = price
                    update = symbol, qs.size, fill_price, cur_time, 'filled'
                    qs.position_manager.handle_position_update(qs, update)
            elif qs.status == 'filled':
                if qs.stoploss != 0 and \
                        ticktype == 3 and \
                        size >= abs(qs.size) and \
                        cur_time - qs.fill_time >= MIN_FILL_DELAY and \
                        ((qs.size > 0 and qs.stoploss >= price + MIN_FILL_PRICE_GAP) or
                        (qs.size < 0 and qs.stoploss <= price - MIN_FILL_PRICE_GAP)):
                    # close
                    #update = symbol, 0, qs.stoploss, cur_time, 'closed_on_stoploss'
                    fill_price = qs.stoploss
                    update = symbol, 0, fill_price, cur_time, 'closed_on_stoploss'
                    qs.position_manager.handle_position_update(qs, update)
                elif qs.takeprofit != 0 and \
                        ticktype == 3 and \
                        cur_time - qs.fill_time >= MIN_FILL_DELAY and \
                        size >= abs(qs.size) and \
                        ((qs.size > 0 and qs.takeprofit <= price - MIN_FILL_PRICE_GAP) or
                        (qs.size < 0 and qs.takeprofit >= price + MIN_FILL_PRICE_GAP)):
                    # close
                    #update = symbol, 0, qs.takeprofit, cur_time, 'closed_on_takeprofit'
                    fill_price = qs.takeprofit
                    update = symbol, 0, price, cur_time, 'closed_on_takeprofit'
                    qs.position_manager.handle_position_update(qs, update)
                elif cur_time - qs.fill_time >= qs.holding_period * 60:
                    # close
                    update = symbol, 0, price, cur_time, 'closed_on_time_out'
                    #FIXME: disable or not
                    qs.position_manager.handle_position_update(qs, update)
            elif qs.status == 'closing':
                if self.close_position_requests.has_key(qs.uuid):
                    close_size = -(qs.size)
                    if cur_time - qs.closing_time >= MIN_FILL_DELAY and \
                            ticktype == 3 and \
                            size >= abs(qs.size) and \
                            (is_zero(qs.close_price) or
                            (close_size > 0 and price <= qs.close_price - MIN_FILL_PRICE_GAP) or
                            (close_size < 0 and price >= qs.close_price + MIN_FILL_PRICE_GAP)):
                        del self.close_position_requests[qs.uuid]
                        # close
                        #update = symbol, 0, qs.close_price, cur_time, 'closed_on_request'
                        fill_price = qs.close_price
                        if is_zero(fill_price):
                            fill_price = price
                        update = symbol, 0, fill_price, cur_time, 'closed_on_request'
                        qs.position_manager.handle_position_update(qs, update)

class TradebotClient:
    def __init__(self, user_id, password):
        self.user_id = user_id
        self.password = password

        self.trades = {}
        self.position_update_subject = ''
        self.pnl_update_subject = ''
        self.om_subject = ''
        self.execution_update_subject = ''
        self.quicksetup_response_suejct = ''
        self.max_size_per_trade = 3000

        tibrv_open()
        self.trans = TibrvTransport(settings.tibrv_service,
                                    settings.tibrv_network,
                                    settings.tibrv_daemon)
        self.trans.set_description('ENSEMBLE TRADING')

        self.login_reply_topic = 'ZENITH.TRADEBOT.LOGIN.TBManual.%s' % (user_id)

        self.login_listener = TibrvListener(
            self.trans,
            self.login_reply_topic,
            self.__get_tibrv_callback())

        self.logged_in = False
        self.login()

    def roll_forward_working_date(self, new_date):
        pass

    def login(self):
        msg = TibrvMessage()
        msg.set_topic('ZENITH.TRADEBOT.LOGIN.TBManual')
        msg.set_reply_topic(self.login_reply_topic)
        msg.add_string('CATEGORY', 'LOGIN')
        msg.add_string('ACTION', 'LOGIN')
        msg.add_string('USERID', self.user_id)
        msg.add_string('PWD', self.password)
        msg.add_int('SMART OM1 MAJOR VERSION', 1)
        msg.add_int('SMART OM1 MINOR VERSION', 3)
        print 'Send tradebot login', msg.as_string()
        logger.debug('Send tradebot login: %s' % (msg.as_string()))
        self.trans.send(msg)

    def send_trade_setup(self, qs):
        #symbol, price, size, stoploss, takeprofit, holding_period, setup_time

        self.trades[qs.uuid] = qs

        msg = TibrvMessage()
        msg.set_topic(self.om_subject)
        msg.add_string('UUID', qs.uuid)
        msg.add_string('CATEGORY', 'QUICKSETUP')
        msg.add_string('ACTION', 'NEW')
        msg.add_string('SECTYPE', 'Stock')
        msg.add_string('SYMBOL', qs.symbol)
        msg.add_string('EXCHANGE', 'ARCA')

        if qs.size > 0:
            msg.add_string('DIRECTION', 'Long')
        else:
            msg.add_string('DIRECTION', 'Short')

        msg.add_int('ENTRY_SHARE', abs(qs.size))

        if is_zero(qs.price): # market order
            msg.add_int('ENTRY_TYPE', 2) # LIMIT=1, MARKET=2
        else:
            msg.add_int('ENTRY_TYPE', 1) # LIMIT=1, MARKET=2
            #msg.add_int('LIMIT_TYPE', 3) # 1: Absolute, 2: Bid+, 3: Last+, 4: Ask+
            #msg.add_float('LIMIT_AMOUNT', 0.0)
            msg.add_int('LIMIT_TYPE', 1) # 1: Absolute, 2: Bid+, 3: Last+, 4: Ask+
            msg.add_float('LIMIT_AMOUNT', qs.price)

        msg.add_string('DELTA_PRICE', '0')
        if qs.stoploss > 0:
            msg.add_float('STOPLOSS', qs.stoploss)
        if qs.takeprofit > 0:
            msg.add_float('TARGET1', qs.takeprofit)
            msg.add_int('TARGET1_SHARE', abs(qs.size))

        msg.add_int('AUTOTRAIL', 0)

        if qs.holding_period > 0:
            msg.add_int('HOLDPERIOD', qs.holding_period)
            msg.add_string('HOLDPERIODUNIT', 'minute')

        print 'Send trade setup', self.om_subject, msg.as_string()
        logger.debug('Send trade setup: %s %s' % (self.om_subject, msg.as_string()))
        self.trans.send(msg)

    def close_position(self, qs, close_price):
        if qs.setup_id == 0:
            return

        msg = TibrvMessage()
        msg.set_topic(self.om_subject)
        msg.add_string('UUID', qs.uuid)
        msg.add_string('CATEGORY', 'POSITION')
        msg.add_string('SYMBOL', qs.symbol)
        msg.add_int('SETUP_ID', qs.setup_id)
        msg.add_string('DESTINATION', 'BATS')
        if is_zero(close_price):
            msg.add_string('ACTION', 'LIMIT CLOSE POSITION')
            msg.add_float('LIMIT', close_price)
        else:
            msg.add_string('ACTION', 'CLOSE POSITION')
            msg.add_string('METHOD', 'MARKET')
        print 'Send close position msg', self.om_subject, msg.as_string()
        logger.debug('Send close position msg: %s %s' % (self.om_subject, msg.as_string()))
        self.trans.send(msg)

    def cancel_setup(self, qs):
        if qs.setup_id == 0:
            return

        msg = TibrvMessage()
        subject = self.om_subject
        #subject = self.cancel_order_subject
        msg.set_topic(subject)

        msg.add_string('UUID', qs.uuid)
        msg.add_string('CATEGORY', 'TRADESETUP')
        msg.add_string('ACTION', 'CANCEL TRADESETUP')
        msg.add_string('SYMBOL', qs.symbol)
        msg.add_string('SETUP_ID', str(qs.setup_id))

        print 'Send cancel setup msg', subject, msg.as_string()
        logger.debug('Send cancel setup msg: %s %s' % (subject, msg.as_string()))
        self.trans.send(msg)


    def chase_setup(self, qs, chase_price):
        if qs.setup_id == 0:
            return
        msg = TibrvMessage()
        msg.set_topic(self.om_subject)
        msg.add_string('UUID', qs.uuid)
        msg.add_string('CATEGORY', 'TRADESETUP')
        msg.add_string('ACTION', 'CHASE TRADESETUP')
        msg.add_string('SYMBOL', qs.symbol)
        #msg.add_int('SETUP_ID', qs.setup_id)
        msg.add_string('SETUP_ID', str(qs.setup_id))
        msg.add_string('DESTINATION', 'BATS')
        if is_zero(chase_price):
            pass
        else:
            msg.add_string('METHOD', 'LIMITPRICE')
            msg.add_float('LIMIT', chase_price)
        print 'Send chase quicksetup msg', self.om_subject, msg.as_string()
        logger.debug('Send chase quicksetup msg: %s %s' % (self.om_subject, msg.as_string()))
        self.trans.send(msg)

    def update_with_bat(self, bat):
        pass

    def __get_tibrv_callback(self):
        def process_msg_func(transport, msg):
            self.process_tibrv_msg(msg)
        self.__tibrv_callback = process_msg_func
        return self.__tibrv_callback

    def process_tibrv_msg(self, msg):
        topic = msg.get_topic()
        print 'received tibrv msg:', topic, msg.as_string()
        logger.debug('received tibrv msg: %s %s' % (topic, msg.as_string()))

        if topic == self.login_reply_topic:

            type_ = msg.get_string('TYPE', 'LOGINRESPONSE')
            if type_ == 'LOGINRESPONSE':
                status = msg.get_int('STATUS', -1)
                print 'status', status
                if status != 0:
                    return

                self.logged_in = True
                self.position_update_subject = msg.get_string('POSITION UPDATE')
                self.pnl_update_subject = msg.get_string('PNL UPDATE')
                self.om_subject = msg.get_string('OM LISTENER SUBJECT')
                self.execution_update_subject = msg.get_string('EXECUTION UPDATE')
                self.quicksetup_response_suejct = msg.get_string('QUICKSETUPRESPONSE')
                self.order_status_update_subject = msg.get_string('ORDERSTATUS UPDATE')
                self.cancel_order_subject = msg.get_string('CANCEL ORDER')

                print self.position_update_subject
                print self.pnl_update_subject
                print self.om_subject
                print self.execution_update_subject
                print self.quicksetup_response_suejct

                self.position_update_listener = TibrvListener(self.trans,
                        self.position_update_subject, self.__get_tibrv_callback())
                #self.pnl_update_listener = TibrvListener(self.trans,
                        #self.pnl_update_subject, self.__get_tibrv_callback())
                self.execution_update_listener = TibrvListener(self.trans,
                        self.execution_update_subject, self.__get_tibrv_callback())
                self.quicksetup_response_listener = TibrvListener(self.trans,
                        self.quicksetup_response_suejct, self.__get_tibrv_callback())
                self.order_status_update_listener = TibrvListener(self.trans,
                        self.order_status_update_subject,
                        self.__get_tibrv_callback())

        elif topic == self.position_update_subject:
            uuid = msg.get_string('UUID', '')
            if not self.trades.has_key(uuid):
                return

            qs = self.trades[uuid]
            qs.setup_id = msg.get_int('SETUP_ID', 0)

            symbol = msg.get_string('SYMBOL', '')
            shares = msg.get_int('SHARES', 0)
            price = msg.get_float('PRICE', 0.0)
            price = ceil(price * 100 - 0.001) / 100
            cur_time = msg.get_int('UPDATETIME', 0)
            pnl = msg.get_float('PnL', 0.0)
            pnl = ceil(pnl * 100 - 0.001) / 100

            update = symbol, shares, price, cur_time, '%.02f' % (pnl)

            qs.position_manager.handle_position_update(qs, update)

        elif topic == self.order_status_update_subject:

            status = msg.get_string('STATUS', 'CONFIRMED')
            if status != 'CONFIRMED':
                return
            uuid = msg.get_string('UUID', '')
            if not self.trades.has_key(uuid):
                return

            qs = self.trades[uuid]
            qs.broker_order_id = msg.get_string('BROKER_ORDERID', '')
            qs.order_id = msg.get_int('ORDERID', 0)

        elif topic == self.quicksetup_response_suejct:
            uuid = msg.get_string('UUID', '')
            if not self.trades.has_key(uuid):
                return

            qs = self.trades[uuid]
            errorcode = msg.get_int('ERRORCODE', 0)
            if errorcode < 0:
                qs.status = 'error'

def start_market_data_receiver():
    if not settings.use_fake_market_data_receiver:
        r = MarketDataReceiver(settings.market_data_port)
        r.start()
    else:
        r = FakeMarketDataReceiver(0)
        r.start()

def start_cmdline():
    while True:
        line = raw_input('$')
        if line == 'exit':
            break
        elif line == 'tl':
            tradebot_client.login()

def main():
    global ensemble_predictors
    global tradebot_client

    timestamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())

    configs_1 = [('EWJ', 1, 1), ('CSJ', 1, 1),
            ('CFT', 1, 1), ('AGG', 1, 1),
            ('GVI', 1, 1), ('RWX', 1, 1),
            ('IEI', 1, 1), ('IFN', 1, 1)]
    configs_2 = [('IEI', 1, 1), ('CFT', 1, 1)]
    configs_3 = [('EWJ', 1, 1)]
    configs = configs_1

    if hasattr(settings, 'symbols'):
        copy_1min_data = False
        if hasattr(settings, 'copy_1min_data'):
            copy_1min_data = settings.copy_1min_data
        new_configs = []
        for symbol in settings.symbols:
            new_configs.append((symbol, 1, 1))
            if copy_1min_data:
                print '//192.168.137.1/MarketData/US/1Min/Data/1minuteMin/%s_1.txt' % symbol
                shutil.copy('//192.168.137.1/MarketData/US/1Min/Data/1minuteMin/%s_1.txt' % symbol, '../data/1min')
        configs = new_configs

    print configs

    for symbol, interval, delay in configs:
        ensemble_predictor = EnsemblePredictor(cur_date, symbol, interval, delay)
        ensemble_predictors.append(ensemble_predictor)

    print '%d ensemble predictors' % (len(ensemble_predictors))

    for i in range(total_instances):
        #p = Process(target=main_worker, args=(timestamp, i))
        #p.start()
        main_worker(timestamp, i)

    if not settings.use_fake_tradebot_client:
        tradebot_client = TradebotClient(settings.tradebot_user_id, settings.tradebot_password)
    else:
        tradebot_client = FakeTradebotClient('', '')

    start_market_data_receiver()
    start_cmdline()

if __name__ == '__main__':
    # load settings
    import sys
    settings_file_name = 'settings.py'
    if len(sys.argv) > 1:
        settings_file_name = sys.argv[1]

    import imp
    try:
        settings = imp.load_source('settings', settings_file_name)
        print 'loaded settings from', settings_file_name
    except:
        dump_exception(0)
        import settings
        print 'loaded settings from default settings file'

    if settings.first_day == 0 or (hasattr(settings, 'auto_set_date') and settings.auto_set_date):
        import calendar
        t0 = time.gmtime() # UTC time
        secs0 = calendar.timegm(t0)
        market_time_zone = -5
        if hasattr(settings, 'market_time_zone'):
            market_time_zone = settings.market_time_zone
        secs1 = secs0 + settings.market_time_zone * 3600
        t1 = time.gmtime(secs1) # market time

        cur_date = t1.tm_year * 10000 + t1.tm_mon * 100 + t1.tm_mday
    else:
        cur_date = settings.first_day

    if hasattr(settings, 'tradable_time_ranges'):
        tradable_time_ranges = settings.tradable_time_ranges
    new_tradable_time_ranges = []
    for t_begin, t_end in tradable_time_ranges:
        secs_begin = get_secs(t_begin)
        secs_end = get_secs(t_end)
        new_tradable_time_ranges.append((secs_begin, secs_end))
    tradable_time_ranges = new_tradable_time_ranges

    if hasattr(settings, 'min_fill_delay'):
        MIN_FILL_DELAY = settings.min_fill_delay

    main()

