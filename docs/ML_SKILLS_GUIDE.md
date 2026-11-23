# GridRescue ML skills guide

Start with the [Astra skill manifest](ML_AUDIT_SKILL_MANIFEST.md) for the names Codex can load. Sol can use these skills to plan and review implementation. Astra can use them to challenge the assumptions and evidence in a separately authorized scientific audit.

## Installed skills

All five skills come from `param087/agent-ml-skills` at commit `576ed92fcd2e820accac5ede6bd17171ffc5aa47`. Each directory contains its original `SKILL.md` and the upstream MIT license. The packages contain only text, with no runtime dependency or required companion file. [Pinned source](https://github.com/param087/agent-ml-skills/tree/576ed92fcd2e820accac5ede6bd17171ffc5aa47), [MIT license](https://github.com/param087/agent-ml-skills/blob/576ed92fcd2e820accac5ede6bd17171ffc5aa47/LICENSE).

| Skill | Local path | When Sol or Astra should use it | GridRescue components |
| --- | --- | --- | --- |
| `feature-engineering` | `.agents/skills/feature-engineering/SKILL.md` | Sol designs or reviews feature transformations. Astra verifies timestamp alignment, past-only windows, predictor availability, and fold-fitted preprocessing. | `src/gridrescue/pipeline.py`, `scripts/feature_feasibility.py` |
| `imbalanced-data` | `.agents/skills/imbalanced-data/SKILL.md` | Sol checks prevalence, precision, recall, class weights, or threshold policy. Astra checks split-level prevalence and how the operating point affects rare-event errors. | `src/gridrescue/modeling.py`, `reports/modeling/` |
| `model-evaluation` | `.agents/skills/model-evaluation/SKILL.md` | Sol defines comparable scoring and reporting. Astra checks chronology, confusion matrices, probability reliability, and baseline comparisons under common folds. | `src/gridrescue/modeling.py`, `src/gridrescue/experiment.py`, `reports/modeling/` |
| `reproducible-ml` | `.agents/skills/reproducible-ml/SKILL.md` | Sol documents environment versions, seeds, and artifact identities. Astra traces reported results to authorized development inputs, configuration, and reload evidence. | `requirements-lock.txt`, `src/gridrescue/experiment.py`, `scripts/reload_model.py`, `reports/modeling/` |
| `ml-debugging` | `.agents/skills/ml-debugging/SKILL.md` | Sol or Astra triages suspicious performance by checking label alignment, predictor leakage, split design, and data-to-model wiring. | `scripts/check_label_traces.py`, `src/gridrescue/pipeline.py`, `src/gridrescue/modeling.py` |

## Apply the GridRescue protocol

- Use the project's purged chronological development folds and fold-fitted preprocessing. Treat the upstream shuffled cross-validation and target-encoding snippets as illustrative. If target encoding is ever in scope, compute category statistics and the fallback prior from each training fold. Review county overlap against the generalization claim being tested.
- Keep average precision distinct from trapezoidal PR-AUC. Use the approved frozen 0.5 threshold for the current protocol. Threshold selection, resampling, or model changes require a separately authorized change to the experiment scope.
- Apply generic reproducibility guidance to GridRescue's existing Spark and scikit-learn stack. PyTorch, CUDA, DVC, Docker, and imbalanced-learn are examples in the upstream prose. Set `PYTHONHASHSEED` before starting Python if hash determinism is required. Use only approved development inputs for provenance checks. The 2022 holdout remains sealed.
- The installed skill triggers overlap on rare-event scoring and suspicious metrics. Use `imbalanced-data` for prevalence and operating-point questions, `model-evaluation` for evaluation design and interpretation, and `ml-debugging` for ML-specific diagnostics. The existing `systematic-debugging` skill supplies the general root-cause workflow. Existing testing and verification skills still apply to their respective tasks. The upstream handoffs to `model-serving` and `experiment-tracking` are conceptual and no packages for those siblings were added.

See the documented data and experiment constraints before applying an example. [GridRescue README](../README.md), [modeling design](MODELING_IMPLEMENTATION_DESIGN.md).

## Skipped candidates

The review found no explicit reuse license in the repository or selected packages at commit `f6a146581a847c3cde648aff0b7e6a399834e47a` of `Emily2040/data-science-agent-skills`. The five packages below were skipped on that basis. Their upstream catalog installer also recursively deletes an existing destination skill directory before copying. The skill-specific Python helpers use the standard library and expect particular input schemas. Their results would need independent interpretation against GridRescue's protocol. [Pinned catalog](https://github.com/Emily2040/data-science-agent-skills/blob/f6a146581a847c3cde648aff0b7e6a399834e47a/catalog.json), [pinned installer](https://github.com/Emily2040/data-science-agent-skills/blob/f6a146581a847c3cde648aff0b7e6a399834e47a/scripts/catalog_cli.py).

| Candidate | Exact upstream directory |
| --- | --- |
| Leakage Adversary | `data-science-agent-skills/leakage-adversary` |
| Evaluation Reality Check | `data-science-agent-skills/evaluation-reality-check` |
| Experiment Provenance Ledger | `data-science-agent-skills/experiment-provenance-ledger` |
| Baseline Ablation Lab | `data-science-agent-skills/baseline-ablation-lab` |
| Missingness Mechanism Investigator | `data-science-agent-skills/missingness-mechanism-investigator` |

## Verification

Installation used Codex's documented local folder layout. All five packages matched their pinned Git blobs and passed frontmatter and local reference checks. Windows Codex CLI 0.171.0 returned all five once, enabled with `repo` scope, via App Server `skills/list` with `forceReload: true`. GridRescue returned zero discovery errors and its parent directory listed none of the five. [Codex skill locations and refresh behavior](https://learn.chatgpt.com/docs/build-skills), [App Server skill discovery](https://learn.chatgpt.com/docs/app-server#skills).

Codex detects local additions automatically. Open the independent Astra session from this GridRescue folder or a workspace copy containing these files. Restart Codex only if the skill picker fails to refresh. No downloaded script ran during setup. The bundled OpenAI Python validator requires PyYAML, which was absent from the project environment. The Codex loader and dependency-free file checks supplied validation.
