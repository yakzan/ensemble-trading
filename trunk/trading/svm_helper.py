from svmutil import *
from util import *

def svm_cross_validate_epsilon(y, x, C, gamma, epsilon, fold=5, verbose=1):
    # cross validation: -v
    svm_train_params = '-s 3 -t 2 -h 0 -c %f -g %f -p %f -v %d' % (C, gamma, epsilon, fold)
    if verbose < 2:
        svm_train_params += ' -q'
    if verbose:
        print svm_train_params
    acc = svm_train(y, x, svm_train_params)
    if verbose:
        print 'svm cross validation %s => %f' % (svm_train_params, acc)
    return acc

def svm_cross_validate(y, x, C, gamma, fold=5, verbose=1):
    # cross validation: -v
    svm_train_params = '-s 3 -t 2 -h 0 -c %f -g %f -p 0.001 -v %d' % (C, gamma, fold)
    if verbose < 2:
        svm_train_params += ' -q'
    if verbose:
        print svm_train_params
    acc = svm_train(y, x, svm_train_params)
    if verbose:
        print 'svm cross validation %s => %f' % (svm_train_params, acc)
    return acc

def get_svm_model(y, x, C, gamma, verbose=1):
    svm_train_params = '-s 3 -t 2 -h 0 -c %f -g %f -p 0.001' % (C, gamma)
    if verbose < 2:
        svm_train_params += ' -q'
    if verbose:
        print 'svm train %s' % (svm_train_params)
    m = svm_train(y, x, svm_train_params)
    return m

def get_svm_model_epsilon(y, x, C, gamma, epsilon, verbose=1):
    svm_train_params = '-s 3 -t 2 -h 0 -c %f -g %f -p %f' % (C, gamma, epsilon)
    if verbose < 2:
        svm_train_params += ' -q'
    if verbose:
        print 'svm train %s' % (svm_train_params)
    m = svm_train(y, x, svm_train_params)
    return m

def svm_train_with_grid_search(y, x, C_set=[1000, 750, 500, 100, 50, 2], gamma_set=[2, 1, 0.3, 0.1, 0.01, 0.001, 0.0001], fold=5, verbose=1):
    """ using grid search to find optimal C, gamma for SVM, and return the best svm model."""
    best_acc, best_C, best_gamma = 10, 100, 0.01
    for gamma in gamma_set:
        for C in C_set:
            acc = svm_cross_validate(y, x, C, gamma, fold, verbose)
            if acc < best_acc:
                best_C, best_gamma = C, gamma
                best_acc = acc
    return get_svm_model(y, x, best_C, best_gamma, verbose), best_C, best_gamma, best_acc

def svm_train_with_grid_search_epsilon(y, x, C_set=[100, 2, 0.1], gamma_set=[2, 1, 0.1, 0.01, 0.001, 0.0001, 0.00001], epsilon_set=[0.001, 0.01, 0.0001, 0.1, 0.00001], fold=5, verbose=1):
    """ using grid search to find optimal C, gamma for SVM, and return the best svm model."""
    best_acc, best_C, best_gamma, best_epsilon = 10, 100, 0.01, 0.001
    for epsilon in epsilon_set:
        for gamma in gamma_set:
            for C in C_set:
                acc = svm_cross_validate_epsilon(y, x, C, gamma, epsilon, fold, verbose)
                if acc < best_acc:
                    best_C, best_gamma, best_epsilon = C, gamma, epsilon
                    best_acc = acc
    return get_svm_model_epsilon(y, x, best_C, best_gamma, best_epsilon, verbose), best_C, best_gamma, best_epsilon, best_acc

def svm_train_with_stddev(y, x, verbose=1):
    """ find optimal C, gamma for SVM based on stddev, and return the best svm model."""
    import math
    avg_y = sum(y) / len(y)
    stddev_y = math.sqrt(sum([(b - avg_y)**2 for b in y]) / (len(y)- 1))

    best_acc, best_C, best_gamma = 10, 3.0 * stddev_y, 0.005
    for gamma in [0.001]:# [0.01, 0.005, 0.001]:
        acc = svm_cross_validate(y, x, best_C, gamma, 2, verbose)
        if acc < best_acc:
            best_gamma = gamma
            best_acc = acc
    return get_svm_model(y, x, best_C, best_gamma, verbose), best_C, best_gamma, best_acc

def svm_train_with_stddev_gamma(y, x, gamma, verbose=1):
    """ find optimal C, gamma for SVM based on stddev, and return the best svm model."""
    import math
    avg_y = sum(y) / len(y)
    stddev_y = math.sqrt(sum([(b - avg_y)**2 for b in y]) / (len(y)- 1))

    best_acc, best_C, best_gamma = 10, 3.0 * stddev_y, gamma
    return get_svm_model(y, x, best_C, best_gamma, verbose), best_C, best_gamma, best_acc

def svm_train_with_stddev_gamma_epsilon(y, x, gamma, epsilon, verbose=1):
    """ find optimal C, gamma for SVM based on stddev, and return the best svm model."""
    import math
    avg_y = sum(y) / len(y)
    stddev_y = math.sqrt(sum([(b - avg_y)**2 for b in y]) / (len(y)- 1))

    best_acc, best_C, best_gamma = 10, 3.0 * stddev_y, gamma
    return get_svm_model_epsilon(y, x, best_C, best_gamma, epsilon, verbose), best_C, best_gamma, epsilon, best_acc

# --------------------------------------------------------------------------------
# SVM prediction
# --------------------------------------------------------------------------------
def svm_predict_svm_line(svm_line, svm_model, verbose=1):
    y, x = svm_problem_from_svm_lines([svm_line])
    label, acc, val = svm_predict(y, x, svm_model, verbose=verbose)
    return label[0]

def svm_predict_svm_lines(svm_lines, svm_model, verbose=1):
    prediction_results = []
    actual_values = []
    for svm_line in svm_lines:
        actual_values.append(svm_line[0])
        prediction = svm_predict_svm_line(svm_line, svm_model, verbose)
        prediction_results.append(prediction)
    return prediction_results, actual_values

# --------------------------------------------------------------------------------
# data conversion
# --------------------------------------------------------------------------------

def svm_problem_from_svm_lines(svm_lines):
    y = []
    x = []
    for svm_line in svm_lines:
        y.append(svm_line[0])

        xi = {}
        for i, val in enumerate(svm_line[1:]):
            xi[i+1] = val
        x.append(xi)
    return y, x

def svm_problem_from_svm_file(filename):
    y, x = svm_read_problem(filename)
    return y, x

if __name__ == '__main__':
    y, x = svm_problem_from_svm_file(r'../data/svm/KS11-testing.txt')
    m_pso, C_pso, gamma_pso, acc_pso = svm_train_with_pso(y, x, verbose=1)
    print 'PSO:', m_pso, C_pso, gamma_pso, acc_pso
    m_grid, C_grid, gamma_grid, acc_grid = svm_train_with_grid_search(y, x, verbose=0)
    print 'Grid search:', m_grid, C_grid, gamma_grid, acc_grid

