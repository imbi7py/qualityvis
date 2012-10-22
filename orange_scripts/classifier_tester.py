import Orange
from Orange import orange
from collections import defaultdict

from data_utils import cast_table
from stats import dist_stats

CLASS_THRESHOLDS = {'FA': (1.01, .7), 'GA': (0.7, 0.4)}

def discrete_status_domain(c_data):
    return_domain = Orange.data.Domain(c_data.domain.attributes, c_data.domain['R_ah_current'])
    return_domain.addmetas(c_data.domain.getmetas())
    return orange.ExampleTable(return_domain, c_data)

def convert_status(c_feature, threshold_map, default_d_value=None, d_feature_name=None):
    kvs = sorted(threshold_map.items(), key=lambda x: x[1], reverse=True)
    if d_feature_name is None:
        d_feature_name = 'D_' + c_feature.variable.name.lstrip('C_')
    if default_d_value is None:
        default_d_value = kvs[-1][0]  # the least-valued threshold label
    if default_d_value not in threshold_map:
        raise ValueError('default_d_value "' + str(default_d_value) + '" must be a member of threshold_map')
    d_feature = Orange.feature.Discrete(d_feature_name, values=threshold_map.keys())
    for label, (max, min) in kvs:
        if c_feature.value < max and c_feature.value >= min:
            return d_feature(label)
    return d_feature(default_d_value)

def get_scores(test_data, classifiers, threshold_map=CLASS_THRESHOLDS, keep_attrs=False):
    if keep_attrs:
        attrs = test_data.domain.attributes.clone()
    else:
        attrs = []
    attr_vars = {}
    for classifier in classifiers:
        name = str(classifier.name)
        attr_vars[name + '_score'] = orange.FloatVariable(name + '_score')
        attr_vars[name + '_abs_error'] = orange.FloatVariable(name + '_abs_error')
        attr_vars[name + '_b_status'] = orange.EnumVariable(name + '_bucketed_status', values=threshold_map.keys())
    attrs += attr_vars.values()
    
    new_domain = Orange.data.Domain(attrs, test_data.domain.class_var)
    new_domain.addmetas(test_data.domain.getmetas())
    threshold_var = orange.FloatVariable('threshold')
    new_meta_id = Orange.feature.Descriptor.new_meta_id()
    new_domain.add_meta(new_meta_id, threshold_var)
    
    ret = orange.ExampleTable(new_domain, test_data)
    for classifier in classifiers:
        name = str(classifier.name)
        for i, inst in enumerate(test_data):
            score = classifier(inst)
            bucketed_status = convert_status(score, threshold_map).value
            threshold_max, threshold_min = threshold_map[inst['R_ah_current'].value]
            ret[i][name + '_score'] = attr_vars[name + '_score'](score.value)
            ret[i][name + '_abs_error'] = attr_vars[name + '_abs_error'](max(0, threshold_min - score.value) + max(0, score.value - threshold_max))
            ret[i][name + '_bucketed_status'] = attr_vars[name + '_b_status'](bucketed_status)
            ret[i]['threshold'] = threshold_var(threshold_min)
    return ret

    
def get_experiment_results(scored_data, classifiers, actual_class_feature='R_ah_current'):
    actual_class_var = scored_data.domain[actual_class_feature]
    num_classifiers = len(classifiers)
    tmp_results = []
    for inst in scored_data:
        te = Orange.evaluation.testing.TestedExample(n=num_classifiers, actual_class=inst[actual_class_feature])
        for j, c in enumerate(classifiers):
            c_name = str(c.name)
            te.set_result(j, actual_class_var(inst[c_name+'_bucketed_status'].value), 1.0)
            tmp_results.append(te)

    ret = Orange.evaluation.testing.ExperimentResults(1, [c.name for c in classifiers], class_values=actual_class_var.values, results=tmp_results)
    return ret

#all_data = in_data[0]
#data_scores = get_scores(all_data, in_classifiers)
#out_data = cast_table(data_scores, new_class_var=data_scores.domain['R_ah_current'])
#out_test_results = get_experiment_results(data_scores, in_classifiers)
#out_data = data_scores

tr = test_on_data(in_classifiers, in_data[0])

def get_one_accuracy_score(scores, target_mean, target_stddev=0.2, target_skewness=0.3, target_kurtosis=2.5):
    s_stats = dist_stats(scores)
    mean_comp = 0.5 * min(1.0, abs((target_mean - s_stats['mean'])/target_mean))
    stddev_comp = 0.25 * min(1.0, abs((target_stddev - s_stats['std_dev'])/target_stddev))
    skew_comp = 0.15 * min(1.0, abs((target_skewness - s_stats['skewness'])/target_skewness))
    kurt_comp = 0.1 * min(1.0, abs((target_kurtosis - s_stats['kurtosis'])/target_kurtosis))
    
    return 1.0 - (mean_comp + stddev_comp + skew_comp + kurt_comp)

from collections import Counter
def get_accuracy_scores(tr, verbose=True):
    "tr = Test Results (an ExperimentResults object)"
    ret = []
    actual_classes = Counter([r.actual_class for r in tr.results])
    if len(actual_classes) > 200:
        raise TypeError("probably too many actual class values for get_accuracy_scores()")
    
    for i, cn in enumerate(tr.classifier_names):
        weighted_c_score_sum = 0.0
        for ac, ac_count in actual_classes.items():
            # separate estimates for each class
            c_estimates = [r.classes[i] for r in tr.results if r.actual_class == ac]
            acc_score = get_one_accuracy_score(c_estimates, ac) # TODO: custom moments for each class?
            if verbose:
                print '   ',cn,'classifier accuracy for',ac,':', acc_score
            weighted_c_score_sum += (acc_score*ac_count)/len(c_estimates)
        classifier_score = weighted_c_score_sum/len(actual_classes)
        ret.append(classifier_score)
        if verbose:
            print 'Overall accuracy for', cn,': ',classifier_score 
    return ret
    

"""
Meta attributes (title, etc.)
Original class
Guessed class
Guessed class score (threshold)
Score
Absolute error

Other stuff:
    Mean squared error
    Root mean squared error (absolute?)
    Mean absolute error
    Relative squared error
    Root relative squared error
    Relative absolute error
    R-Squared
"""

