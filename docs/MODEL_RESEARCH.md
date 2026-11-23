# Three classifiers for the approved university experiment

The same 13 known-at-anchor numeric features predict the same approved three-hour reported-escalation label in the same three counties. These explanations are algorithm research, not claimed model results.

| Model | How to explain it | Why include it | Strengths | Limitations | Important parameters |
|---|---|---|---|---|---|
| Logistic Regression | Multiply each standardized feature by a learned weight, add them, and pass the score through a sigmoid to obtain a class probability. | A simple regularized linear probability baseline. | Fast, compact, coefficients describe direction in standardized units. | Linear log-odds cannot represent every nonlinear interaction; correlated features complicate coefficient interpretation; probabilities are not automatically calibrated operational risks. | C controls inverse regularization strength; solver/max_iter control numerical optimization. |
| Decision Tree Classifier | Ask a sequence of feature-threshold questions. A leaf reports the training class proportions of rows reaching it. | Transparent nonlinear rules familiar from the course. | Captures interactions without manually writing them; a shallow tree can be explained visually. | A deep default tree can memorize adjacent, correlated windows and generalize poorly; small data changes can alter the tree. | max_depth limits question levels; min_samples_split controls when a node may split; min_samples_leaf prevents tiny leaves. |
| Random Forest Classifier | Fit many trees on bootstrap samples and randomly selected candidate features, then average their class probabilities. | Tests whether averaging diverse trees improves stability over a single tree. | Nonlinear interactions; averaging reduces variance; parallel tree fitting. | Larger/slower artifact; less transparent than one tree; correlated county-time anchors still limit effective information. | n_estimators controls tree count; max_depth limits complexity; min_samples_leaf regularizes leaves. |

## Defaults before tuning

Use sklearn defaults, changing only random_state=17 and Random Forest n_jobs=2 for execution parallelism. In particular, default trees remain unpruned initially and the default forest has 100 trees. Log the installed version and full actual classifier parameters. Median imputation and StandardScaler are fitted within each Pipeline and each training fold. Scaling is useful for Logistic Regression; it is redundant for tree split order, but using the same prepared features keeps this baseline comparison consistent.

## Bounded searches and interpretation

- Logistic Regression: C=0.1 and 10, alongside default C=1. If the actual default reports a convergence warning, give both tuned candidates max_iter=1000 and record that numerical correction; never relabel it as the default.
- Decision Tree: reference candidate (max_depth=12, min_samples_split=2, min_samples_leaf=1), then controlled contrasts for depth=20, split minimum=20, or leaf minimum=10. Compare actual CV changes; do not assume deeper is better.
- Random Forest: reference candidate (n_estimators=100, max_depth=12, min_samples_leaf=5), then controlled contrasts for 200 trees, depth=20, or leaf minimum=10. More trees primarily change averaging/stability and runtime; depth/leaf limits change complexity.
- All candidates use the same three purged chronological folds and the same raw features. Retain the default if it wins training-only CV. Select the final algorithm using the reserved 2021 development validation, not 2022.

The main selection score is **average precision**. Report trapezoidal PR-AUC separately because it is not identical to average precision. Also report ROC-AUC, accuracy, precision, recall, F1, confusion matrices, class prevalence and training times. A high training score with weaker future-period scores is evidence to investigate overfitting/distribution change; it is not proof of physical causal mechanisms. Overlapping windows are not independent outage events.

## Primary references

- [Logistic Regression](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression)
- [Decision Tree Classification](https://scikit-learn.org/stable/modules/tree.html#classification)
- [Random Forests](https://scikit-learn.org/stable/modules/ensemble.html#forest)
- [Avoiding preprocessing leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)
- [Classification metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#classification-metrics)
- [Model persistence](https://scikit-learn.org/stable/model_persistence.html)

Only locally generated, hash-verified joblib artifacts are loaded. Joblib/pickle files from untrusted sources can execute code and are not accepted as project models.
