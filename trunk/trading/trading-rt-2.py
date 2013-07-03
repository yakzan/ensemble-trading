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

logger = 0
log_dir = ''
total_instances = 4
ensemble_predictors = []
tradebot_client = None
cur_date = 0

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
    def __init__(self, position_manager, symbol, price, size, stoploss, takeprofit, holding_period, setup_time):
        self.position_manager = position_manager
        self.symbol, self.price, self.size, self.stoploss, self.takeprofit, self.holding_period, self.setup_time = \
                symbol, price, size, stoploss, takeprofit, holding_period, setup_time
        self.uuid = str(uuid.uuid1())
        self.setup_id = 0
        self.time_to_live = 120 #FIXME
        self.fill_time = 0
        self.status = ''
        self.is_closing = False
        self.is_chasing = False
        self.pnl = 0
        self.send()
        self.predicted_value = price

    def send(self):
        global tradebot_client
        tradebot_client.send_trade_setup(self)

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

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, my_time = bat
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
        # cancel quicksetups that are not filled for a long time
        if 1: # FIXME: how to cancel setup?
            for qs in self.trades:
                if not qs.status and my_time - qs.setup_time >= qs.time_to_live:
                    qs.status = 'cancelled'
                    tradebot_client.cancel_setup(qs)

        if 1:
            for qs in self.trades:
                if not qs.status and my_time - qs.setup_time >= 60 and not qs.is_chasing:

                    if qs.size > 0 and self.ask > 0 and qs.predicted_value >= self.ask or \
                            qs.size < 0 and self.bid > 0 and qs.predicted_value <= self.bid:

                        chase_price = self.ask
                        if qs.size < 0:
                            chase_price = self.bid

                        comment += 'CH_%02d:%02d:%02d %.3f ' % (qs.setup_time / 3600, qs.setup_time % 3600 / 60, qs.setup_time % 60, chase_price)
                        qs.is_chasing = True
                        tradebot_client.chase_setup(qs, chase_price)

        if not comment:
            return

        cur_price = price
        predicted_value = 0
        atr = 0
        diff = 0
        stoploss = 0
        takeprofit = 0
        size_per_trade = 0
        cur_size = 0
        trade_size = 0
        close_size = 0
        cur_pnl = 0
        pnl_per_share = 0
        if self.total_shares != 0:
            pnl_per_share = self.total_pnl / abs(self.total_shares)
        print >>self.f_out, '%4d/%02d/%02d %02d:%02d:%02d, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %d, %d, %d, %d, %d, %.4f, %.4f, %.4f, %s' % (
            cur_date / 10000, cur_date % 10000 / 100, cur_date % 100, my_time / 3600, my_time % 3600 / 60, my_time % 60,
            cur_price, predicted_value, atr, diff, cur_price, stoploss, takeprofit,
            size_per_trade, cur_size, trade_size, close_size, self.open_position_size,
            self.total_pnl, pnl_per_share, cur_pnl, comment)
        self.f_out.flush()


    def handle_trade_signal(self, atr, avg_price, predicted_value, cur_price, cur_time):

        if atr <= 0.00001:
            atr = 0.00001
        size_per_trade = int(min(self.equity * 0.2 / avg_price, self.equity * 0.05 / atr)) / 10 * 10
        if size_per_trade <= 0:
            size_per_trade = 1
        if size_per_trade >= tradebot_client.max_size_per_trade:
            size_per_trade = tradebot_client.max_size_per_trade

        cur_size = 0
        stoploss = 0
        takeprofit = 0
        change = abs(atr) / 3
        atr = ceil(atr * 100 - 0.01) / 100
        if (predicted_value - cur_price > change): # predicted UP
            cur_size += size_per_trade
            stoploss = cur_price - atr * 2
            takeprofit = cur_price + atr * 2
        elif cur_price - predicted_value > change: # predicted DOWN
            cur_size -= size_per_trade
            stoploss = cur_price + atr * 2
            takeprofit = cur_price - atr * 2

        comment = ''

        buy_price = cur_price
        if self.bid > 0:
            buy_price = min(self.bid, ceil(predicted_value * 100 - 0.001) / 100)

        sell_price = cur_price
        if self.ask > 0:
            sell_price = max(self.ask, ceil(predicted_value * 100 - 0.001) / 100)

        if cur_size != 0 and \
                abs(self.open_position_size + cur_size) < tradebot_client.max_size_per_trade and \
                cur_time <= 15*3600 + 30*60:

            logger.debug('%02d:%02d:%02d, symbol=%s, cur_price=%.2f, cur_size=%d, stoploss=%.2f, takeprofit=%.2f, holding_period=%d' % (
                cur_time / 3600, cur_time % 3600 / 60, cur_time % 60,
                self.symbol, cur_price, cur_size, stoploss, takeprofit, self.holding_period))

            close_size = 0
            if self.open_position_size != 0 and self.open_position_size * cur_size < 0:
                # new trade => close
                size_to_close = cur_size
                for qs in self.trades:
                    if qs.status != 'filled' or qs.is_closing:
                        continue

                    qs.is_closing = True
                    close_price = sell_price
                    if qs.size < 0:
                        close_price = buy_price
                    comment += 'CA_%02d:%02d:%02d_%.3f_%d (bid %.3f ask %.3f) ' % (qs.setup_time / 3600, qs.setup_time % 3600 / 60, qs.setup_time % 60, close_price, -qs.size, self.bid, self.ask)
                    tradebot_client.close_position(qs, close_price)

                    close_size += (-qs.size)
                    size_to_close -= (-qs.size)
                    if size_to_close <= 0:
                        break

            trade_size = cur_size - close_size
            if cur_size > 0 and trade_size < 0 or cur_size < 0 and trade_size > 0:
                trade_size = 0
            if trade_size != 0:
                trade_price = buy_price
                if trade_size < 0:
                    trade_price = sell_price
                comment += 'NT_%02d:%02d:%02d_%.3f %d (bid %.3f ask %.3f) ' % (cur_time / 3600, cur_time % 3600 / 60, cur_time % 60, trade_price, trade_size, self.bid, self.ask)
                trade = TradeSetup(self, self.symbol, trade_price, trade_size, stoploss, takeprofit, self.holding_period, cur_time)
                trade.predicted_value = predicted_value
                self.trades.append(trade)

            cur_size = close_size + trade_size

        elif cur_time > 15*3600 + 30*60:

            trade_size = 0
            close_size = 0

            for qs in self.trades:
                if qs.status != 'filled' or qs.is_closing:
                    continue

                qs.is_closing = True
                close_price = sell_price
                if qs.size < 0:
                    close_price = buy_price
                comment += 'CA_%02d:%02d:%02d_%.3f_%d (bid %.3f ask %.3f) ' % (qs.setup_time / 3600, qs.setup_time % 3600 / 60, qs.setup_time % 60, close_price, -qs.size, self.bid, self.ask)
                tradebot_client.close_position(qs, close_price)

                close_size += (-qs.size)

            cur_size = close_size + trade_size

        else:
            close_size = trade_size = cur_size = 0
            return

        diff = predicted_value - cur_price
        cur_pnl = 0
        pnl_per_share = 0
        if self.total_shares != 0:
            pnl_per_share = self.total_pnl / abs(self.total_shares)
        print >>self.f_out, '%4d/%02d/%02d %02d:%02d:%02d, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %d, %d, %d, %d, %d, %.4f, %.4f, %.4f, %s' % (
            cur_date / 10000, cur_date % 10000 / 100, cur_date % 100, cur_time / 3600, cur_time % 3600 / 60, cur_time % 60,
            cur_price, predicted_value, atr, diff, cur_price, stoploss, takeprofit,
            size_per_trade, cur_size, trade_size, close_size, self.open_position_size,
            self.total_pnl, pnl_per_share, cur_pnl, comment)
        self.f_out.flush()

    def handle_position_update(self, qs, update):
        symbol, shares, price, cur_time, reason = update
        if symbol != self.symbol:
            return

        if not qs.status and shares != 0:
            qs.status = 'filled'
            qs.fill_time = cur_time
            if price > 0:
                qs.fill_price = price
            else:
                qs.fill_price = qs.price
            self.open_position_size += qs.size
            self.total_trades += 1
            self.total_shares += abs(shares)

            cur_price = self.price
            predicted_value = 0
            atr = 0
            diff = 0
            stoploss = 0
            takeprofit = 0
            size_per_trade = 0
            cur_size = 0
            trade_size = 0
            close_size = 0
            cur_pnl = 0
            pnl_per_share = 0
            if self.total_shares != 0:
                pnl_per_share = self.total_pnl / abs(self.total_shares)
                comment = 'PF_%02d:%02d:%02d_%.3f_%d %s ' % (qs.setup_time / 3600, qs.setup_time % 3600 / 60, qs.setup_time % 60, price, shares, reason)

            print >>self.f_out, '%4d/%02d/%02d %02d:%02d:%02d, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %d, %d, %d, %d, %d, %.4f, %.4f, %.4f, %s' % (
                cur_date / 10000, cur_date % 10000 / 100, cur_date % 100, cur_time / 3600, cur_time % 3600 / 60, cur_time % 60,
                cur_price, predicted_value, atr, diff, cur_price, stoploss, takeprofit,
                size_per_trade, cur_size, trade_size, close_size, self.open_position_size,
                self.total_pnl, pnl_per_share, cur_pnl, comment)
            self.f_out.flush()

        elif qs.status == 'filled' and shares == 0:
            qs.status = 'closed'
            qs.pnl = (self.price - qs.fill_price) * qs.size
            self.open_position_size -= qs.size
            self.total_trades += 1
            self.total_shares += abs(qs.size)
            self.total_pnl += qs.pnl
            self.balance += qs.pnl
            self.equity += qs.pnl # FIXME

            cur_price = self.price
            predicted_value = 0
            atr = 0
            diff = 0
            stoploss = 0
            takeprofit = 0
            size_per_trade = 0 #abs(qs.size)
            cur_size = -qs.size
            trade_size = 0
            close_size = 0 #cur_size
            pnl_per_share = 0
            if self.total_shares != 0:
                pnl_per_share = self.total_pnl / abs(self.total_shares)
                comment = 'PC_%02d:%02d:%02d (%.4f -> %.4f) %s ' % (qs.setup_time / 3600, qs.setup_time % 3600 / 60, qs.setup_time % 60,
                    qs.fill_price, self.price, reason)

            print >>self.f_out, '%4d/%02d/%02d %02d:%02d:%02d, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %.4f, %d, %d, %d, %d, %d, %.4f, %.4f, %.4f, %s' % (
                cur_date / 10000, cur_date % 10000 / 100, cur_date % 100, cur_time / 3600, cur_time % 3600 / 60, cur_time % 60,
                cur_price, predicted_value, atr, diff, cur_price, stoploss, takeprofit,
                size_per_trade, cur_size, trade_size, close_size, self.open_position_size,
                self.total_pnl, pnl_per_share, qs.pnl, comment)
            self.f_out.flush()

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
        self.position_manager.f_out = self.f_out

        logger.debug('%s: %d lines' % (f_out_name, len(extended_svm_lines)))

        print >>self.f_out, 'date_str, cur_price, predicted_value, atr, diff, cur_price, stoploss, takeprofit, size_per_trade, cur_size, trade_size, close_size, open_position_size, total_pnl, pnl_per_share, cur_pnl, comment'

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

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, my_time = bat
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
        self.position_manager.handle_trade_signal(atr, self.avg_price, predicted_value, cur_price, my_time)

    def roll_forward_working_date(self, new_date):
        global cur_date
        print 'new date', new_date
        logger.info('new date: %d', new_date)
        self.svm_data.roll_forward_working_date(new_date)
        cur_date = new_date
        self.position_manager.trades = []
        self.position_manager.open_position_size = 0
        self.position_manager.price = 0
        self.position_manager.bid = 0
        self.position_manager.ask = 0

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
            self.sock.bind(('', self.port))

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
                        if my_time < 9*3600 + 29*60:
                            continue
                        if symbol.find('\0') > 0:
                            symbol = symbol.split('\0')[0]
                        price = ceil(price * 100 - 0.01) / 100
                        bat = symbol, ticktype, exchange, price, size, my_time

                        for ensemble_predictor in ensemble_predictors:
                            ensemble_predictor.update_with_bat(bat)
                        if tradebot_client is not None:
                            tradebot_client.update_with_bat(bat)
                elif header == 'DATE':
                    new_date = struct.unpack('i', buf[8:12])[0]
                    for ensemble_predictor in ensemble_predictors:
                        ensemble_predictor.roll_forward_working_date(new_date)

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


    def login(self):
        self.logged_in = True

    def send_trade_setup(self, qs):
        self.trades[qs.uuid] = qs
        self.global_setup_id += 1
        qs.setup_id = self.global_setup_id

    def close_position(self, qs, close_price):
        if qs.setup_id == 0:
            return
        qs.close_price = close_price
        self.close_position_requests[qs.uuid] = qs

    def cancel_setup(self, qs):
        self.cancel_setup_requests[qs.uuid] = qs

    def chase_setup(self, qs, chase_price):
        if qs.setup_id == 0:
            return
        qs.chase_price = chase_price
        self.chase_setup_requests[qs.uuid] = qs

    def update_with_bat(self, bat):
        symbol, ticktype, exchange, price, size, my_time = bat
        if ticktype != 3:
            return

        for qs in self.trades.values():
            if qs.symbol != symbol:
                continue
            if not qs.status:
                if self.cancel_setup_requests.has_key(qs.uuid):
                    qs.status = 'cancelled'
                    del self.cancel_setup_requests[qs.uuid]
                    update = symbol, 0, -1, my_time, 'cancelled'
                    qs.position_manager.handle_position_update(qs, update)
                elif self.chase_setup_requests.has_key(qs.uuid):
                    if (qs.size > 0 and price <= qs.chase_price) or (qs.size < 0 and price >= qs.chase_price):
                        del self.chase_setup_requests[qs.uuid]
                        # fill
                        update = symbol, qs.size, qs.chase_price, my_time, 'chase_filled'
                        qs.position_manager.handle_position_update(qs, update)
                elif (qs.size > 0 and price <= qs.price) or (qs.size < 0 and price >= qs.price):
                    # fill
                    update = symbol, qs.size, qs.price, my_time, 'filled'
                    qs.position_manager.handle_position_update(qs, update)
            elif qs.status == 'filled':
                if my_time - qs.fill_time >= qs.holding_period * 60:
                    # close
                    update = symbol, 0, price, my_time, 'closed_on_time_out'
                    qs.position_manager.handle_position_update(qs, update)
                elif qs.stoploss != 0 and (
                        (qs.size > 0 and qs.stoploss >= price) or
                        (qs.size < 0 and qs.stoploss <= price)):
                    # close
                    update = symbol, 0, qs.stoploss, my_time, 'closed_on_stoploss'
                    qs.position_manager.handle_position_update(qs, update)
                elif qs.takeprofit != 0 and (
                        (qs.size > 0 and qs.takeprofit <= price) or
                        (qs.size < 0 and qs.takeprofit >= price)):
                    # close
                    update = symbol, 0, qs.takeprofit, my_time, 'closed_on_takeprofit'
                    qs.position_manager.handle_position_update(qs, update)
                elif self.close_position_requests.has_key(qs.uuid):
                    close_size = -(qs.size)
                    if (close_size > 0 and price <= qs.close_price) or (close_size < 0 and price >= qs.close_price):
                        del self.close_position_requests[qs.uuid]
                        # close
                        update = symbol, 0, qs.close_price, my_time, 'closed_on_request'
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
        self.trans = TibrvTransport('9922', ';238.10.10.11;', '192.168.137.1:7700')
        self.trans.set_description('ENSEMBLE TRADING')

        self.login_reply_topic = 'ZENITH.TRADEBOT.LOGIN.TBManual.%s' % (user_id)

        self.login_listener = TibrvListener(
            self.trans,
            self.login_reply_topic,
            self.__get_tibrv_callback())

        self.logged_in = False
        self.login()

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

        if 0: # market order
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

        msg.add_string('UUID', qs.uuid)

        print 'Send trade setup', self.om_subject, msg.as_string()
        logger.debug('Send trade setup: %s %s' % (self.om_subject, msg.as_string()))
        self.trans.send(msg)

    def close_position(self, qs, close_price):
        '''
CATEGORY="POSITION"
 ACTION="BIDASK CLOSE POSITION" // OR "LASTPRICE CLOSE POSITION"|"CLOSE POSITION", "MIDPOINT CLOSE POSITION", OR "LIMIT CLOSE POSITION"
 SYMBOL="IBM"
 SETUP_ID=12345

OR

CATEGORY="POSITION"
 ACTION="CLOSE POSITION"
 LIMIT=23.45 //FLOAT VALUE, required if ACTION="LIMIT CLOSE POSITION"
 DESTINATION="BATS" //STRING, the DESTINATION to send the closing order. If empty string, TB will use same exchange used for entry
 SYMBOL="IBM"
 SETUP_ID=12345
 METHOD="ADDLIQ"/"TAKELIQ"/"LASTPRICE"/"MARKET"/"MIDPOINT"/"LIMITPRICE"
 LIMIT=123.45 (if METHOD="LIMITPRICE")
        '''
        if qs.setup_id == 0:
            return
        msg = TibrvMessage()
        msg.set_topic(self.om_subject)
        msg.add_string('CATEGORY', 'POSITION')
        msg.add_string('SYMBOL', qs.symbol)
        msg.add_int('SETUP_ID', qs.setup_id)
        msg.add_string('DESTINATION', '')
        if 0:
            msg.add_string('ACTION', 'LASTPRICE CLOSE POSITION')
        else:
            msg.add_string('ACTION', 'LIMIT CLOSE POSITION')
            msg.add_float('LIMIT', close_price)

        print 'Send close position msg', self.om_subject, msg.as_string()
        logger.debug('Send close position msg: %s %s' % (self.om_subject, msg.as_string()))
        self.trans.send(msg)

    def cancel_setup(self, qs):
        pass

    def chase_setup(self, qs, chase_price):
        if qs.setup_id == 0:
            return
        qs.chase_price = chase_price
        msg = TibrvMessage()
        msg.set_topic(self.om_subject)
        msg.add_string('CATEGORY', 'TRADESETUP')
        msg.add_string('ACTION', 'CHASE TRADESETUP')
        msg.add_string('SYMBOL', qs.symbol)
        #msg.add_int('SETUP_ID', qs.setup_id)
        msg.add_string('SETUP_ID', str(qs.setup_id))
        msg.add_string('UUID', qs.uuid)
        print 'Send chase quicksetup msg', self.om_subject, msg.as_string()
        logger.debug('Send chase quicksetup msg: %s %s' % (self.om_subject, msg.as_string()))
        self.trans.send(msg)

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
                print self.position_update_subject
                print self.pnl_update_subject
                print self.om_subject
                print self.execution_update_subject
                print self.quicksetup_response_suejct
                self.position_update_listener = TibrvListener(self.trans, self.position_update_subject, self.__get_tibrv_callback())
                #self.pnl_update_listener = TibrvListener(self.trans, self.pnl_update_subject, self.__get_tibrv_callback())
                self.execution_update_listener = TibrvListener(self.trans, self.execution_update_subject, self.__get_tibrv_callback())
                self.quicksetup_response_listener = TibrvListener(self.trans, self.quicksetup_response_suejct, self.__get_tibrv_callback())

        elif topic == self.position_update_subject:
            uuid = msg.get_string('UUID', '')
            if not self.trades.has_key(uuid):
                return

            qs = self.trades[uuid]
            qs.setup_id = msg.get_int('SETUP_ID', 0)

            symbol = msg.get_string('SYMBOL', '')
            shares = msg.get_int('SHARES', 0)
            price = msg.get_float('PRICE', 0.0)
            my_time = msg.get_int('UPDATETIME', 0)

            update = symbol, shares, price, my_time, 'FIXME'

            qs.position_manager.handle_position_update(qs, update)


def start_market_data_receiver(port):
    r = MarketDataReceiver(port)
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

    first_day = 20130603
    #configs = [('EWJ', 1, 2)]
    configs = [('EWJ', 1, 2), ('SHY', 1, 2), ('SHV', 1, 2),
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

    tradebot_client = FakeTradebotClient('yzhang', 'charles')
    start_market_data_receiver(19004)
    start_cmdline()

if __name__ == '__main__':
    main()

