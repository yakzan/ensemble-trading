# partition data in to several overlapping parts.
# the train each partition using SVM, with C, gamma selected using grid search.

from svm_helper import *
from svm_data import *
from random import *
from math import *
from util import *
import sys
import os
import time
import shutil
import logging
from multiprocessing import Process, Queue
import threading
import socket

logger = 0
log_dir = ''
total_instances = 4
ensemble_predictors = []

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

    if logger == 0:
        logger = logging.getLogger()
        hdlr = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s %(message)s')
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr)
        logger.setLevel(logging.DEBUG)

        logger.info(repr(argv))

class TradeSetup:
    def __init__(self, symbol, price, size, stoploss, takeprofit, holding_period, setup_time):
        self.symbol, self.price, self.size, self.stoploss, self.takeprofit, self.holding_period, self.setup_time = \
                symbol, price, size, stoploss, takeprofit, holding_period, setup_time
        self.time_to_live = 60 #FIXME
        self.fill_time = 0
        self.status = ''

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, my_time = bat
        if symbol != self.symbol or ticktype != 3:
            return ''

        if self.status == 'filled':
            if my_time - self.fill_time >= self.holding_period * 60:
                self.status = 'time_to_close'
                return self.status

            elif self.stoploss != 0 and (
                (self.size > 0 and self.stoploss > price) or
                (self.size < 0 and self.stoploss < price)):
                self.status = 'stoploss'
                return self.status

        elif not self.status and my_time - self.setup_time >= self.time_to_live:
            self.status = 'cancelled'
            return self.status

        elif not self.status and self.size > 0 and price <= self.price or self.size < 0 and price >= self.price:
            self.status = 'filled'
            self.fill_time = my_time
            return self.status

        return ''

class PositionManager:
    """ manager positions for an ensemble predictor """

    def __init__(self, symbol, holding_period):
        self.symbol = symbol
        self.holding_period = holding_period # in minute
        self.trades = []
        self.initial_buying_power = 100000
        self.balance = self.initial_buying_power
        self.equity = self.initial_buying_power
        self.positions_size = 0
        self.positions_price = 0
        self.total_pnl = 0
        self.total_trades = 0
        self.total_shares = 0

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, my_time = bat
        if symbol != self.symbol and ticktype != 3:
            return ''

        for trade in self.trades[:]:
            result = trade.update_with_bat(bat)

            if result == 'filled' or \
               result == 'time_to_close' or \
               result == 'stoploss':

                cur_price = price
                cur_size = trade.size
                if result != 'filled':
                    cur_size = 0 - trade.size # close existing position
                cur_pnl = 0

                if self.positions_size > 0: # was long
                    if cur_size > 0: # long again
                        self.positions_price = (self.positions_size * self.positions_price + cur_size * cur_price) / (self.positions_size + cur_size)
                    elif cur_size < 0: # short
                        cur_pnl = (cur_price - self.positions_price) * abs(cur_size)
                elif self.positions_size < 0: # was short
                    if cur_size < 0: # short again
                        self.positions_price = abs((self.positions_size * self.positions_price + cur_size * cur_price) / (self.positions_size + cur_size))
                    elif cur_size > 0: # long
                        cur_pnl = (self.positions_price - cur_price) * cur_size
                else:
                    self.positions_price = cur_price

                self.positions_size += cur_price
                self.total_trades += 1
                self.total_shares += abs(cur_price)
                self.total_pnl += cur_pnl
                self.balance += cur_pnl
                self.equity = self.balance + (cur_price - self.positions_price) * (self.positions_size)

                logger.debug('%02d:%02d, symbol=%s, cur_price=%.2f, cur_size=%d, total_pnl=%.2f, total_trades=%d, total_shares=%d' % (
                    my_time / 3600, my_time % 3600 / 60, self.symbol, cur_price, cur_size, self.total_pnl, self.total_trades, self.total_shares))

                if result != 'filled':
                    self.trades.remove(trade)

            elif result == 'cancelled':
                self.trades.remove(trade)

    def handle_trade_signal(self, atr, avg_price, predicted_value, cur_price, cur_time):

        size_per_trade = int(min(self.equity * 0.5 / avg_price, self.equity * 0.05 / atr)) / 10 * 10
        if size_per_trade <= 0:
            size_per_trade = 1

        cur_size = 0
        stoploss = 0
        takeprofit = 0
        change = abs(atr) / 3
        if (predicted_value - cur_price > change): # predicted UP
            cur_size += size_per_trade
            stoploss = cur_price - atr * 2
            takeprofit = cur_price + atr * 2
        elif cur_price - predicted_value > change: # predicted DOWN
            cur_size -= size_per_trade
            stoploss = cur_price + atr * 2
            takeprofit = cur_price - atr * 2

        if cur_size == 0:
            return

        trade = TradeSetup(self.symbol, cur_price, cur_size, stoploss, takeprofit, self.holding_period, cur_time)
        self.trades.append(trade)
        logger.debug('%02d:%02d, symbol=%s, cur_price=%.2f, cur_size=%d, stoploss=%.2f, takeprofit=%d, holding_period=%d' % (
            cur_time / 3600, cur_time % 3600 / 60, self.symbol, cur_price, cur_size, stoploss, takeprofit, self.holding_period))

class EnsemblePredictor:
    def __init__(self, first_day, symbol, interval=1, delay=1, dimension=5, gamma=0.0001, epsilon=0.001, num_partitions=200):
        self.symbol, self.interval, self.delay, dimension = symbol, interval, delay, dimension
        self.gamma, self.epsilon = gamma, epsilon
        self.num_partitions_to_keep = num_partitions

        self.svm_data = SvmData(symbol, SvmData.ONE_MIN, interval, first_day)
        self.svm_data.set_settings(portion_training=1)
        self.svm_data.set_dimension_delay(dimension, delay)

        self.cur_date = 0

        self.position_manager = PositionManager(self.symbol, self.delay * 2)

    def train(self):
        fixed_gamma = self.gamma
        fixed_epsilon = self.epsilon
        use_random_partition = 0
        verbose = 0

        symbol = self.symbol
        data = self.svm_data
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
        self.max_changes = max(changes)

        f_out_name = os.path.join(log_dir, '%s_i%d_d%d_g%f_e%f.csv' % (
            symbol, data.interval, data.time_delay, fixed_gamma, fixed_epsilon))
        self.f_out = open(f_out_name, 'w')

        logger.debug('%s: %d lines' % (f_out_name, len(extended_svm_lines)))

        print >>self.f_out, 'date_str, cur_size, cur_price, predicted_value, change, atr, diff, size_per_trade, stoploss'

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
        self.initial_buying_power = 100000

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, my_time = bat
        if symbol != self.symbol:
            return
        #print bat

        self.position_manager.update_with_bat(bat)

        r = self.svm_data.update_with_bat(bat)
        if r is None:
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
        self.position_manager.handle_trade_signal(atr, self.avg_price, predicted_value, cur_price, my_time)

    def roll_forward_working_date(self, new_date):
        print 'new date', new_date
        logger.info('new date: %d', new_date)
        self.svm_data.roll_forward_working_date(new_date)

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

class MarketDataReceiver(threading.Thread):
    def __init__(self, port):
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('localhost', self.port))

            print 'Market data receiver has been started on port %d' % self.port
            while True:
                buf = self.sock.recv(10240)
                dataLen = len(buf)
                if dataLen <= 8:
                    continue
                header = buf[:8].split('\0')[0]
                if header == 'BAT':
                    for i in range(8, dataLen, 20):
                        if i+20 > dataLen:
                            continue
                        symbol, ticktype, exchange, price, size, my_time = \
                                struct.unpack('6sccfli', buf[i:i+20])
                        ticktype = ord(ticktype)
                        if ticktype != 3 or my_time < 9*3600 + 30*60:
                            continue
                        if symbol.find('\0') > 0:
                            symbol = symbol.split('\0')[0]
                        bat = symbol, ticktype, exchange, price, size, my_time

                        for ensemble_predictor in ensemble_predictors:
                            ensemble_predictor.update_with_bat(bat)
                elif header == 'DATE':
                    new_date = struct.unpack('i', buf[8:12])[0]
                    for ensemble_predictor in ensemble_predictors:
                        ensemble_predictor.roll_forward_working_date(new_date)

        except:
            dump_exception()



def start_market_data_receiver(port):
    r = MarketDataReceiver(port)
    r.start()

def start_cmdline():
    while True:
        line = raw_input('$')
        if line == 'exit':
            break

def main():
    global ensemble_predictors

    timestamp = time.strftime('%Y%m%d-%H%M%S', time.localtime())

    first_day = 20130531
    configs = [('EWJ', 1, 2)]
    configs_0 = [('EWJ', 1, 2), ('SHY', 1, 2), ('SHV', 1, 2),
               ('CSJ', 1, 2), ('CFT', 1, 2), ('CIU', 1, 2),
               ('AGG', 1, 2), ('GVI', 1, 2), ('RWX', 1, 2),
               ('TIP', 1, 2), ('IEI', 1, 2), ('EWL', 1, 2)]
    for symbol, interval, delay in configs:
        ensemble_predictor = EnsemblePredictor(first_day, symbol, interval, delay)
        ensemble_predictors.append(ensemble_predictor)

    print '%d ensemble predictors' % (len(ensemble_predictors))

    for i in range(total_instances):
        #p = Process(target=main_worker, args=(timestamp, i))
        #p.start()
        main_worker(timestamp, i)

    start_market_data_receiver(19004)
    start_cmdline()

if __name__ == '__main__':
    main()

