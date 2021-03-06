import sys, os, collections, copy
import numpy as np
import pandas as pd
from pandas import DataFrame, Series
import sklearn
from sklearn.cross_validation import train_test_split
from sklearn import metrics

class EMNaiveBayes(object):
    '''
    Implementation of Unsupervised Naive Bayes with EM Algorithm.
    Some evaluation approaches are also implemented:
    - Feature Entropy
    - Correspondence Analysis
    - Accuracy Improvement
    '''
    def __init__(self, epsilon=1e-5):
        self.epsilon = epsilon

    def _init_params(self, X, K):
        self.X, self.K = X, K
        self.N, self.M = X.shape
        self.num_iter = 0
        self.q = [sorted(list(set(X[:, j]))) for j in range(self.M)]
        self.nq = np.array([len(v) for v in self.q])
        self.q2number = [Series(range(self.nq[j]), index=self.q[j]) for j in range(self.M)]
        # self.X_number is some kind of onehot encoding. Use natural numbers instead of {0, 1}
        self.X_number = np.array([self.q2number[j][self.X[:, j]] for j in range(self.M)]).T
        # self.X_onehot = pd.get_dummies(DataFrame(self.X)) # ok?
        self.X_onehot = np.zeros((self.N, sum(self.nq)))
        col_idx = 0
        for j in range(self.M):
            for l in range(self.nq[j]):
                self.X_onehot[:, col_idx + l] = (self.X_number[:, j] == l).astype(int)
            col_idx += self.nq[j]
        return self

    def _init_theta(self, random_state=0):
        self.theta_dim = self.K + self.K * sum(self.nq)
        if random_state == None:
            return self._init_theta_uniform()
        elif random_state < 0:
            return self._init_theta_uniform_plus_normal()
        else:
            return self._init_theta_random(random_state)

    def _init_theta_random(self, random_state):
        '''
        \theta = (pyk, A)
        pyk is a 1d array, and A is a list of 2d array
        A[j][k, l] means: for the kth class, the probability that the jth feature's value is the lth value of the feature.
                        i.e. P(a_jl | y_k)
        '''
        eps = 1e-2
        tmp = np.random.rand(self.K) + eps
        self.pyk = tmp / tmp.sum()
        self.A = list()
        for j in range(self.M):
            tmp = np.random.rand(self.K, self.nq[j]) + eps
            self.A.append((tmp.T / tmp.sum(axis=1)).T)
        return self # return self. enables chain call

    def _init_theta_uniform(self):
        '''
        This initialization does not work, since the theta will not change after one iteration.
        '''
        self.pyk = np.ones(self.K) / self.K
        self.A = list()
        for j in range(self.M):
            # A[j][k, l] = P(a_jl | y_k)
            pj = pd.value_counts(self.X_number[:, j]).sort_index() / float(self.N)
            self.A.append(np.array([copy.deepcopy(pj) for _ in range(self.K)]))
        return self

    def _init_theta_uniform_plus_normal(self):
        tmp = np.ones(self.K) / self.K + np.random.randn(self.K)
        self.pyk = tmp / tmp.sum()
        self.A = list()
        for j in range(self.M):
            # A[j][k, l] = P(a_jl | y_k)
            pj = pd.value_counts(self.X_number[:, j]).sort_index() / float(self.N)
            tmp = np.array([copy.deepcopy(pj) for _ in range(self.K)])
            tmp += np.random.randn(self.K, self.nq[j])
            tmp = (tmp.T / tmp.sum(axis=1)).T # normalize
            self.A.append(tmp)
        return self

    def _iterate(self):
        '''
        E(v_{ik}) = P(y_k | x_i, \theta^{(t)})
        P(y_k) = \frac{\Sigma_{i=1}^{N} E(v_{ik})}{N}
        P(a_{jl} | y_k) = \frac{\Sigma_{i=1}^{N} E(v_{ik}) * u_i^{(j, l)}}{\Sigma_{i=1}^{N} E(v_{ik})}
        u_i^{(j, l)} =  1, if the ith sample's jth feafure took the lth value of the feature
                        0, otherwise
        '''
        self.num_iter += 1
        self.pyk_old = copy.deepcopy(self.pyk)
        self.A_old = copy.deepcopy(self.A)

        Ev = np.ones((self.N, self.K))
        for j in range(self.M):
            Ev *= (self.A[j][:, self.X_number[:, j]]).T

        Ev *= self.pyk
        self.Ev = (Ev.T / Ev.sum(axis=1).astype(float)).T # normalize

        # update theta
        Ev_k = self.Ev.sum(axis=0).astype(float)
        self.pyk = Ev_k / float(self.N)
        EvT = self.Ev.T
        col_idx = 0
        for j in range(self.M):
            for l in range(self.nq[j]):
                self.A[j][:, l] = (EvT * self.X_onehot[:, col_idx + l]).sum(axis=1) / Ev_k
            col_idx += self.nq[j]
        return self

    def _is_convergent(self):
        '''
        check if || \theta - \theta_old || < \epsilon
        '''
        delta = np.zeros(self.theta_dim)
        delta[:self.K] = self.pyk - self.pyk_old
        delta_idx = self.K
        for j in range(self.M):
            k_nqj = self.K * self.nq[j]
            new_delta_idx = delta_idx + k_nqj
            delta[delta_idx:new_delta_idx] = (self.A[j] - self.A_old[j]).reshape(k_nqj)
            delta_idx = new_delta_idx
        sq_delta = (delta ** 2).sum()
        return sq_delta < self.epsilon

    def _get_encoding(self, Y):
        N, K = len(Y), len(set(Y))
        yk = sorted(list(set(Y)))
        y2number = Series(range(len(yk)), index=yk)
        Y_number = np.array(y2number[Y])
        Y_onehot = np.zeros((N, K))
        for k in range(K):
            Y_onehot[:, k] = (Y_number == k).astype(int)
        nk = np.array(pd.value_counts(Y_number).sort_index())
        pyk = nk / float(N)
        res = {}
        for key in ['Y', 'N', 'K', 'yk', 'y2number', 'Y_number', 'Y_onehot', 'nk', 'pyk']:
            res[key] = eval(key)
        return res

    def _init_evaluation(self, Y):
        # ground
        res = self._get_encoding(Y)
        for key in res:
            setattr(self, key + '_g', res[key])
        # clustered
        res = self._get_encoding(self.Ev.argmax(axis=1))
        for key in res:
            setattr(self, key + '_p', res[key])
        return self

    def _calc_overall_feature_entropy(self):
        '''
        overall feature entropy
        \Sigma_{j=1}^M \Sigma_{l=1}^{nq_j} - \frac{ \Sigma_{i=1}^N u_i^{(j, l)} }{N} * log( \frac{ \Sigma_{i=1}^N u_i^{(j, l)} }{N} )
        '''
        tmp = self.X_onehot.sum(axis=0).astype(float) / self.N
        self.overall_feature_entropy = 0 - (tmp * np.log(np.where(tmp == 0, 1, tmp))).sum()
        return self

    def _calc_clustered_feature_entropy(self):
        '''
        clustered feature entropy
        partition the samples into K classes, calculate overall feature entropy for each class
        and then calculate weighted sum of these entropy
        '''
        tmp = 0
        for j in range(self.M):
            tmp -= (self.pyk * (self.A[j] * np.log(np.where(self.A[j] == 0, 1, self.A[j]))).T).sum()
        self.clustered_feature_entropy = tmp
        return self

    def _calc_ground_feature_entropy(self):
        '''
        ground feature entropy
        same as clustered feature entropy, except that the partition is done by using ground truth Y
        '''
        tmp = 0
        for k in range(self.K_g):
            p_ajl_yk = (self.X_onehot.T * self.Y_onehot_g[:, k]).sum(axis=1) / float(self.nk_g[k])
            tmp -= self.pyk_g[k] * (p_ajl_yk * np.log(np.where(p_ajl_yk == 0, 1, p_ajl_yk))).sum()
        self.ground_feature_entropy = tmp
        return self

    def _correspondence_analysis(self):
        try:
            import mca
        except Exception, e:
            print e
            return self
        self.count = DataFrame(self.Y_onehot_p.T.dot(self.Y_onehot_g), columns=self.yk_g)
        self.freq = self.count.values / float(self.count.values.sum())
        self.Dn = np.diag(self.freq.sum(axis=1))
        self.Dp = np.diag(self.freq.sum(axis=0))
        self.Dn1_F_Dp1_FT = np.linalg.inv(self.Dn).dot(self.freq).dot(np.linalg.inv(self.Dp).dot(self.freq.T))
        self.chi_square_dist = np.trace(self.Dn1_F_Dp1_FT)
        self.ca = mca.mca(self.count)
        return self

    def _calc_model_accuracy(self, model, X_onehot, Y):
        X_train_onehot, X_test_onehot, Y_train, Y_test = train_test_split(X_onehot, Y, test_size=0.2, random_state=0)
        model.fit(X_train_onehot, Y_train)
        pred = model.predict(X_test_onehot)
        accuracy = metrics.accuracy_score(Y_test, pred)
        return accuracy

    def _calc_accuracy_improvement(self):
        '''
        accuracy_g: model accuracy with original X as features and Y_g as ground truth
        accuracy_p: model accuracy with clustered Y as features and Y_g as ground truth
        accuracy_c: model accuracy with combination of X and clustered Y as features and Y_g as ground truth
        '''
        from sklearn.naive_bayes import BernoulliNB
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.svm import SVC
        X_onehot_c = np.concatenate((self.X_onehot, self.Y_onehot_p), axis=1)
        X_onehot_Ev_c = np.concatenate((self.X_onehot, self.Ev), axis=1)
        self.accuracy_g, self.accuracy_p, self.accuracy_c = dict(), dict(), dict()
        for model_name, flag in zip(['BernoulliNB', 'RandomForestClassifier', 'SVC'], ['winall', 'prob', 'prob']):
            self.accuracy_g[model_name] = self._calc_model_accuracy(eval(model_name + '()'), self.X_onehot, self.Y_g)
            self.accuracy_p[model_name] = self._calc_model_accuracy(eval(model_name + '()'), self.Y_onehot_p if flag == 'winall' else self.Ev, self.Y_g)
            self.accuracy_c[model_name] = self._calc_model_accuracy(eval(model_name + '()'), X_onehot_c if flag == 'winall' else X_onehot_Ev_c, self.Y_g)
        return self

    def _print_evaluation(self):
        print '\nNumber of iterations: %d\n' % self.num_iter
        print '''Feature Entropy:\n
        Overall:\t%.4f\n
        Ground: \t%.4f\n
        Clustered:\t%.4f\n''' % (
            self.overall_feature_entropy,
            self.ground_feature_entropy,
            self.clustered_feature_entropy)
        print '\nAccuracy'
        print 'Ground:\n', self.accuracy_g
        print 'Clustered:\n', self.accuracy_p
        print 'Combined:\n', self.accuracy_c
        return self

    def fit(self, X, K, max_iter=500):
        self._init_params(X, K)
        self._init_theta()
        for t in range(max_iter):
            self._iterate()
            if self._is_convergent():
                break
        return self

    def evaluate(self, Y):
        self._init_evaluation(Y)
        self._calc_overall_feature_entropy()
        self._calc_ground_feature_entropy()
        self._calc_clustered_feature_entropy()
        self._correspondence_analysis()
        self._calc_accuracy_improvement()
        self._print_evaluation()
        return self

if __name__ == '__main__':
    # toy data as an example. For more, please go to main.py
    X = np.array([['A', 'B', 'A'], ['B', 'A', 'A'], ['B', 'A', 'C']])
    Y = np.array(['P', 'Q', 'P'])
    K = len(set(Y))
    m = EMNaiveBayes(epsilon=1e-5)
    m.fit(X, K)
    m.evaluate(Y)
