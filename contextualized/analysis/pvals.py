"""
Analysis tools for generating pvalues from bootstrap replicates.

"""

import numpy as np
import pandas as pd

from contextualized.analysis.effects import (
    get_homogeneous_context_effects,
    get_homogeneous_predictor_effects,
    get_heterogeneous_predictor_effects,
)


def calc_pval_bootstraps_one_sided(estimates, thresh=0, laplace_smoothing=1):
    """
    Calculate p-values from bootstrapped estimates.

    Parameters
    ----------
    estimates : np.ndarray
        Bootstrapped estimates of the test statistic.
    thresh : float, optional
    laplace_smoothing : int, optional
    """

    return (laplace_smoothing + np.sum(estimates < thresh)) / (
        estimates.shape[0] + laplace_smoothing
    )


def calc_pval_bootstraps_one_sided_mean(estimates, laplace_smoothing=1):
    """
    Calculate p-values from bootstrapped estimates.
    The p-value is calculated as the proportion of bootstrapped estimates that are:
        less than 0 if the mean of the estimates is positive,
        greater than 0 if the mean of the estimates is negative.

    Parameters
    ----------
    estimates : np.ndarray
        Bootstrapped estimates of the test statistic.
    laplace_smoothing : int, optional
    """

    return calc_pval_bootstraps_one_sided(
        estimates * np.sign(np.mean(estimates)), 0, laplace_smoothing
    )


def calc_homogeneous_context_effects_pvals(model, C, **kwargs):
    """
    Calculate p-values for the effects of context.

    Parameters
    ----------
    model : contextualized.models.Model
    C : np.ndarray

    Returns
    -------
    pvals : np.ndarray of shape (n_contexts, n_outcomes) testing whether the
        sign is consistent across bootstraps
    """
    _, effects = get_homogeneous_context_effects(model, C, **kwargs)
    # effects.shape: (n_contexts, n_bootstraps, n_context_vals, n_outcomes)
    if len(effects.shape) < 4:
        print("P values are not well defined without multiple bootstrap samples.")
        return None

    diffs = effects[:, :, -1] - effects[:, :, 0]  # Test whether the sign is consistent
    pvals = np.array(
        [
            np.array(
                [
                    calc_pval_bootstraps_one_sided_mean(
                        diffs[i, :, j],
                        laplace_smoothing=kwargs.get("laplace_smoothing", 1),
                    )
                    for j in range(diffs.shape[2])  # n_outcomes
                ]
            )
            for i in range(diffs.shape[0])  # n_contexts
        ]
    )
    return pvals


def calc_homogeneous_predictor_effects_pvals(model, C, **kwargs):
    """
    Calculate p-values for the effects of predictors.

    Parameters
    ----------
    model : contextualized.models.Model
    C : np.ndarray

    Returns
    -------
    pvals : np.ndarray of shape (n_predictors, n_outcomes) testing whether the
        sign is consistent across bootstraps
    """
    _, effects = get_homogeneous_predictor_effects(model, C, **kwargs)
    # effects.shape: (n_predictors, n_bootstraps, n_outcomes)
    if len(effects.shape) < 3:
        print("P values are not well defined without multiple bootstrap samples.")
        return None
    pvals = np.array(
        [
            np.array(
                [
                    calc_pval_bootstraps_one_sided_mean(
                        effects[i, :, j],
                        laplace_smoothing=kwargs.get("laplace_smoothing", 1),
                    )
                    for j in range(effects.shape[2])  # n_outcomes
                ]
            )
            for i in range(effects.shape[0])  # n_predictors
        ]
    )
    return pvals


def calc_heterogeneous_predictor_effects_pvals(model, C, **kwargs):
    """
    Calculate p-values for the heterogeneous effects of predictors.

    Parameters
    ----------
    model : contextualized.models.Model
    C : np.ndarray

    Returns
    -------
    pvals : np.ndarray of shape (n_contexts, n_predictors, n_outcomes) testing
        whether the sign of the change wrt context is consistent across bootstraps
    """
    _, effects = get_heterogeneous_predictor_effects(model, C, **kwargs)
    # effects.shape is (n_contexts, n_predictors, n_bootstraps, n_context_vals, n_outcomes)
    if len(effects.shape) < 5:
        print("P values are not well defined without multiple bootstrap samples.")
        return None
    diffs = (
        effects[:, :, :, -1] - effects[:, :, :, 0]
    )  # Test whether the sign is consistent
    # diffs.shape is (n_contexts, n_predictors, n_bootstraps, n_outcomes)
    pvals = np.array(
        [
            np.array(
                [
                    np.array(
                        [
                            calc_pval_bootstraps_one_sided_mean(
                                diffs[i, j, :, k],
                                laplace_smoothing=kwargs.get("laplace_smoothing", 1),
                            )
                            for k in range(diffs.shape[3])
                        ]
                    )  # n_outcomes
                    for j in range(diffs.shape[1])
                ]
            )  # n_predictors
            for i in range(diffs.shape[0])  # n_contexts
        ]
    )
    return pvals


def test_sequential_contexts(model_constructor, C, X, Y, **kwargs):
    """
    Sequentially test each feature in C using calc_homogeneous_context_effects_pvals.

    Parameters
    ----------
    model_constructor : contextualized.models.Model constructor
        The model to be tested.
    C : pandas DataFrame
        The context data with multiple features.
    X : pandas DataFrame
        The input training data.
    Y : pandas DataFrame
        The output training data.
    **kwargs : 
        Additional arguments for the model constructor.

    Returns
    -------
    pandas.DataFrame
        A DataFrame containing p-values for each combination of context, predictor, and target.
        Columns:
        - 'Context': The context feature being tested.
        - 'Predictor': The predictor feature being tested.
        - 'Target': The target variable for which the effects are analyzed.
        - 'Pvals': The corresponding p-value for the analyzed effect.
    """


    default_fit_params = {
        'encoder_type': 'mlp',
        'max_epochs': 3,
        'learning_rate': 1e-2
    }
    fit_params = {**default_fit_params, **kwargs}
    pvals_dict = {}

    for context in C.columns:
        context_col = C[[context]].values

        for predictor in X.columns:
            predictor_col = X[[predictor]].values

            model = model_constructor(**fit_params)
            model.fit(context_col, predictor_col, Y.values, **fit_params)

            pvals = calc_homogeneous_context_effects_pvals(model, context_col)[0]

            for count, target in enumerate(Y.columns):
                pvals_dict["Context"] = pvals_dict.get("Context", [])
                pvals_dict["Predictor"] = pvals_dict.get("Predictor", [])
                pvals_dict["Target"] = pvals_dict.get("Target", [])
                pvals_dict["Pvals"] = pvals_dict.get("Pvals", [])

                pvals_dict["Context"].append(context)
                pvals_dict["Predictor"].append(predictor)
                pvals_dict["Target"].append(target)
                pvals_dict["Pvals"].append(pvals[count])

    return pd.DataFrame.from_dict(pvals_dict)

