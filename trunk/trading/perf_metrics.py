import math
import glob
from util import *

def get_NMSE(predicted_values, actual_values):
    n = len(predicted_values)
    avg_a = sum(actual_values) / n
    dev_a = sum(map(lambda a_i: (a_i - avg_a)** 2, actual_values)) / (n - 1)
    NMSE = sum(map(lambda (a_i, p_i): (a_i - p_i)** 2, zip(actual_values, predicted_values))) / (dev_a * n)
    return NMSE

def get_RMSE(predicted_values, actual_values):
    n = len(predicted_values)
    RMSE = math.sqrt(sum(map(lambda (a_i, p_i): (a_i - p_i)** 2, zip(actual_values, predicted_values))) / n)
    return RMSE

def get_MAE(predicted_values, actual_values):
    n = len(predicted_values)
    MAE = sum(map(lambda (a_i, p_i): abs(a_i - p_i), zip(actual_values, predicted_values))) / n
    return MAE

def direction_indicator(a_i_1, a_i, p_i_1, p_i):
    if (a_i - a_i_1) * (p_i - p_i_1) >= 0:
        return 1
    else:
        return 0

def get_DS(predicted_values, actual_values):
    n = len(predicted_values)
    a = actual_values
    p = predicted_values

    sum_di = 0
    for i in range(1, n):
        sum_di += direction_indicator(a[i-1], a[i], p[i-1], p[i])

    DS = sum_di * 100 / n
    return DS

def get_WDS(predicted_values, actual_values):
    n = len(predicted_values)
    a = actual_values
    p = predicted_values

    sum_1 = 0
    sum_2 = 0
    for i in range(1, n):
        di = direction_indicator(a[i-1], a[i], p[i-1], p[i])
        di_prime = 1 - di
        sum_1 += abs(a[i] - p[i]) * di
        sum_2 += abs(a[i] - p[i]) * di_prime

    if sum_2 == 0:
        return 0
    WDS = sum_1 / sum_2
    return WDS

def get_perf_metrics_values(predicted_values, actual_values):
    NMSE = get_NMSE(predicted_values, actual_values)
    MAE = get_MAE(predicted_values, actual_values)
    DS = get_DS(predicted_values, actual_values)
    WDS = get_WDS(predicted_values, actual_values)
    RMSE = get_RMSE(predicted_values, actual_values)

    return NMSE, MAE, DS, WDS, RMSE

def get_perf_metrics_values_from_file(symbol, result_file_name=''):
    predicted_values = []
    actual_values = []

    if not result_file_name:
        result_file_name = '../output/%s-testing-result.txt' % symbol
    result_file = open(result_file_name)
    for result_line in result_file:
        #predicted = float(result_line.strip())
        predicted = float(result_line.strip().split(',')[0])
        predicted_values.append(predicted)
    result_file.close()

    testing_file = open('../data/svm/%s-testing.csv' % symbol)
    for testing_line in testing_file:
        actual = float(testing_line.strip().split(',')[0])
        actual_values.append(actual)
    testing_file.close()

    return get_perf_metrics_values(predicted_values, actual_values)

def save_perf_metrics(symbol, NMSE, MAE, DS, WDS, RMSE, svm_train_param=''):
    perf_metrics_file = open_for_write('../data/result/%s-perf-metrics.txt' % symbol, 'a+')
    result_str = '%-10s\tNMSE=%.4f\tMAE=%.4f\tDS=%.4f\tWDS=%.4f\tRMSE=%.4f\t%s' % (symbol, NMSE, MAE, DS, WDS, RMSE, svm_train_param)
    print result_str
    print >>perf_metrics_file, result_str
    perf_metrics_file.close()

def get_and_save_perf_metrics(symbol, predicted_values, actual_values, svm_train_param=''):
    NMSE, MAE, DS, WDS, RMSE = get_perf_metrics_values(predicted_values, actual_values)
    save_perf_metrics(symbol, NMSE, MAE, DS, WDS, RMSE, svm_train_param)

def get_and_save_perf_metrics_from_file(symbol, svm_train_param='', result_file_name=''):
    NMSE, MAE, DS, WDS, RMSE = get_perf_metrics_values_from_file(symbol, result_file_name)
    save_perf_metrics(symbol, NMSE, MAE, DS, WDS, RMSE, svm_train_param)

def get_all():
    for symbol in ['AORD', 'DJI', 'GE', 'HSI', 'KS11', 'Nikkei225']:
        try:
            get_perf_metrics_from_file(symbol)
        except:
            print symbol, 'Failed.'

def glob_for_symbol(symbol):
    #print 'NMSE, MAE, DS, WDS, RMSE, C, gamma'
    metrics = []
    result_files = glob.glob('../output/%s-testing-result_*.txt' % symbol)
    for result_file in result_files:
        arr = result_file.split('_')
        if len(arr) == 3:
            C = int(arr[1])
            gamma = float(arr[2][:-4])
            svm_train_params = '-c %d -g %f -p 0.001 -s 3 -t 2' % (C, gamma)
            NMSE, MAE, DS, WDS, RMSE = get_perf_metrics_values(symbol, svm_train_params, result_file)
            metric = NMSE, MAE, DS, WDS, RMSE, C, gamma
            metrics.append(metric)
            #print ','.join(map(str, metric))
    #print '\n'

    print 'C, gamma, WDS'
    metrics.sort(lambda a, b:  a[6] - b[6])
    last_g = -1
    for metric in metrics:
        NMSE, MAE, DS, WDS, RMSE, C, gamma = metric
        if 0.35 < gamma < 0.45:
            if g != last_g:
                print
            last_g = g
            print '\t'.join(map(str, [C, gamma, WDS]))

if __name__ == '__main__':
    glob_for_symbol('AORD')
