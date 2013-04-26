# partition data in to several overlapping parts.
# the train each partition using SVM, with C, gamma selected using grid search.

from svm_helper import *
from svm_data import *
from random import *
from math import *
import sys
from util import *

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

def test_symbol(data, num_partitions_to_keep=10, fixed_gamma=0.05, fixed_epsilon=0.001, use_random_partition=0, verbose=0, dump_partition_result=0, params=None):
    symbol = data.symbol
    data.prepare_svm_lines(verbose=verbose)
    extended_svm_lines = data.detailed_svm_lines[:]
    num_training = int(len(extended_svm_lines) * 0.8)
    extended_svm_lines_training = extended_svm_lines[:num_training]
    extended_svm_lines_testing = extended_svm_lines[num_training:]
    svm_lines_training = data.extended_to_normal_svm_lines(extended_svm_lines_training)
    svm_lines_testing = data.extended_to_normal_svm_lines(extended_svm_lines_testing)

    f_out = open(r'..\output\trading\%s_%d_%d.csv' % (symbol, data.source, data.interval), 'w')

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

    svm_models = []
    for i, partition in enumerate(partitions):
        # only use the bigger partitions for training
        if i < len(partitions) - num_partitions_to_keep:
            continue

        y, x = svm_problem_from_svm_lines(partition)
        svm_model, C, gamma, epsilon, acc = svm_train_with_stddev_gamma_epsilon(y, x, fixed_gamma, fixed_epsilon, verbose=0)[:5]
        svm_models.append(svm_model)
# prediction using SVM.

    num_models = len(svm_models)
    model_weights = [1.0/num_models] * num_models

    fake_prediction_results = []
    prediction_results = []
    actual_values = []

    trades = []
    initial_buying_power = 1000000
    buying_power = initial_buying_power
    balance = initial_buying_power
    equity = initial_buying_power
    positions_size = 0
    positions_price = 0
    pnl = 0
    holding_period = data.time_delay * 5

    normal_price = extended_svm_lines_testing[0][-2]
    size_per_trade = int(initial_buying_power * 0.05 / extended_svm_lines_testing[0][-2]) / 10 * 10
    if size_per_trade > 5000:
        size_per_trade = 5000
    if size_per_trade <= 0:
        size_per_trade = 1
        initial_buying_power = extended_svm_lines_testing[0][-2] * 1000
        buying_power = initial_buying_power

    change = data.scaling_map[1] / 500000
    total_trades = 0

    for svm_line, extended_svm_line in zip(svm_lines_testing, extended_svm_lines_testing):

        # predict using only models with relatively high weights

        # set weights (rule out some models)
        real_weights = model_weights[:]
        real_weights.sort()
        pivot_weight = real_weights[-num_models/4]
        #pivot_weight = 0
        for i, weight in enumerate(model_weights):
            if weight >= pivot_weight:
                real_weights[i] = weight # use it
            else:
                real_weights[i] = 0 # don't use it

        # normalize weights
        sum_weights = sum(real_weights)
        if sum_weights == 0:
            real_weights = [1.0/num_models] * num_models
        else:
            for i in range(num_models):
                real_weights[i] = real_weights[i] / sum_weights

        # predict: weighted sum of the prediction results
        predicted = 0
        temp_results = []
        for i in range(len(svm_models)):
            temp_result = svm_predict_svm_line(svm_line, svm_models[i], verbose=0)
            temp_results.append(temp_result)
            predicted += temp_result * real_weights[i]

        # update model weights
        #signed_diffs = []
        abs_diffs = []

        #min_diff = -1
        #min_diff_index = -1
        for i in range(num_models):
            #signed_diff = temp_results[i] - svm_line[0]
            #signed_diffs.append(signed_diff)

            abs_diff = abs(temp_results[i] - svm_line[0])
            abs_diffs.append(abs_diff)
            #if min_diff == -1 or abs_diff < min_diff:
                #min_diff = abs_diff
                #min_diff_index = i

        sum_diffs = sum(abs_diffs)
        if sum_diffs == 0:
            sum_diffs = 0.1
        avg_diff = sum_diffs / num_models

        for i in range(num_models):
            model_weights[i] += 1.0 / num_models - (abs_diffs[i] ** 2 - avg_diff ** 2) / (avg_diff ** 2)
            if model_weights[i] < 0:
                model_weights[i] = 0

        # normalize weights
        sum_weights = sum(model_weights)
        if sum_weights == 0:
            model_weights = [1.0/num_models] * num_models
        else:
            for i in range(len(svm_models)):
                model_weights[i] = model_weights[i] / sum_weights

        # print result,
        #result_line = '%f,%s,%d,weights,%s,diff,%s,%f' % (predicted, ','.join(map(str, svm_line[0:1])), min_diff_index, ','.join(map(str, model_weights)), ','.join(map(str, signed_diffs)), predicted - svm_line[0])
        #print >>log_f, result_line

        # save result
        prediction_results.append(predicted)
        #fake_prediction_results.append(temp_results[min_diff_index])
        actual_values.append(svm_line[0])

        predicted_value, actual_value, cur_price, bar_date = data.convert_prediction_result(predicted, extended_svm_line)
        date_str = '%04d/%02d/%02d' % (bar_date/10000, bar_date%10000/100, bar_date%100)
        if data.source == SvmData.ONE_MIN or data.source == SvmData.ONE_MIN_COMP:
            d = bar_date / 10000
            t = bar_date % 10000
            date_str = '%04d/%02d/%02d %02d:%02d' % (d/10000, d%10000/100, d%100, t/100, t%100)

        cur_size = 0
        for i in range(len(trades)-1, -1, -1):
            old_size, old_holding_period, old_stoploss = trades[i]
            if old_holding_period <= 1:
                cur_size -= old_size
                del trades[i]
            else:
                trades[i][1] -= 1
        close_size = cur_size

        if (predicted_value - cur_price > cur_price * change): # predicted UP
            if abs((positions_size+cur_price) * positions_price + size_per_trade * cur_price) <= buying_power: # can buy
                cur_size += size_per_trade
        elif cur_price - predicted_value > cur_price * change: # predicted DOWN
            if abs((positions_size+cur_price) * positions_price - size_per_trade * cur_price) <= buying_power: # can sell
                cur_size -= size_per_trade

        cur_pnl = 0
        if positions_size > 0: # was long
            if cur_size > 0: # long again
                positions_price = (positions_size * positions_price + cur_size * cur_price) / (positions_size + cur_size)
            elif cur_size < 0: # short
                cur_pnl = (cur_price - positions_price) * abs(cur_size)
        elif positions_size < 0: # was short
            if cur_size < 0: # short again
                positions_price = abs((positions_size * positions_price + cur_size * cur_price) / (positions_size + cur_size))
            elif cur_size > 0: # long
                cur_pnl = (positions_price - cur_price) * cur_size
        else:
            positions_price = cur_price

        pnl += cur_pnl
        positions_size += cur_size
        balance += cur_pnl
        equity = balance + (cur_price - positions_price) * (positions_size)
        buying_power = balance - abs(cur_price * cur_size)

        if cur_size-close_size != 0:
            stoploss = 0
            if cur_size-close_size > 0: # buy
                stoploss = cur_price - abs(predicted_value - cur_price)
            else: # sell
                stoploss = cur_price + abs(predicted_value - cur_price)
            trades.append([cur_size-close_size, holding_period, stoploss])
        total_trades += abs(cur_size)

        #print >>f_out, ','.join(map(str, [date_str, pnl, positions_size, positions_price, cur_size, close_size, cur_size-close_size, cur_price, predicted_value, buying_power, balance, equity, total_trades, pnl / total_trades]))
        print >>f_out, ','.join(map(str, [date_str, positions_size, positions_price, cur_size, cur_price, (cur_price - positions_price) * (positions_size), pnl, equity, predicted_value]))
    print '-' * 20
    f_out.close()
    print pnl, total_trades, pnl / total_trades
    print '-' * 20
    #print '=' * 20

    # show/save result
    svm_train_param = 'pt, PAPER-5-2, MIN_PARTITION_SIZE=%d, num_partitions_to_keep=%d, gamma=%.6f, epsilon=%f random=%d' % (MIN_PARTITION_SIZE, num_partitions_to_keep, fixed_gamma, fixed_epsilon, use_random_partition)
    #data.convert_prediction_results(fake_prediction_results, svm_train_param='FAKE ' + svm_train_param)
    data.convert_prediction_results_2(prediction_results, extended_svm_lines_testing, svm_train_param=svm_train_param)
    print '-' * 20

if __name__ == '__main__':
    dimension = 5
    delay = 2
    num_partitions = 200
    epsilon = 0.001
    gamma = 0.0001
    flist = glob.glob(r'../data/1min-comp/*_1.dat')
    for interval in [10, 15]:
        #i = 0
        for file in flist:
            #i += 1
            #if interval == 10 and i < 38:
                #continue
            symbol = os.path.basename(file)[:-6]
            try:
                print "'%s', " % symbol,
                print 'testing symbol:', symbol
                svm_data = SvmData(symbol, SvmData.ONE_MIN_COMP, interval)
                svm_data.set_settings(portion_training=0.8)
                svm_data.set_dimension_delay(dimension, delay)
                test_symbol(svm_data, num_partitions_to_keep=num_partitions, fixed_gamma=gamma, fixed_epsilon=epsilon, verbose=1, use_random_partition=0)
            except:
                print symbol, 'failed'
                dump_exception()
                pass
