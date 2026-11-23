# GridRescue Astra audit skill manifest

Windows Codex CLI 0.171.0 discovered the following five skills as enabled at repository scope. Start Astra with GridRescue as the working directory. In Codex, invoke a skill by its `$name` or open the listed `SKILL.md`.

All entries are from `param087/agent-ml-skills` at commit `576ed92fcd2e820accac5ede6bd17171ffc5aa47` under MIT. [Pinned source](https://github.com/param087/agent-ml-skills/tree/576ed92fcd2e820accac5ede6bd17171ffc5aa47).

| Invoke | Repository-relative file | Audit use |
| --- | --- | --- |
| `$feature-engineering` | `.agents/skills/feature-engineering/SKILL.md` | Historical predictors, feature cutoff times, and fold-fitted transformations |
| `$imbalanced-data` | `.agents/skills/imbalanced-data/SKILL.md` | Prevalence, precision, recall, and threshold interpretation |
| `$model-evaluation` | `.agents/skills/model-evaluation/SKILL.md` | Chronological validation, model comparisons, confusion matrices, and calibration |
| `$reproducible-ml` | `.agents/skills/reproducible-ml/SKILL.md` | Input identity, environment, seeds, and artifact provenance |
| `$ml-debugging` | `.agents/skills/ml-debugging/SKILL.md` | Triage implausible metrics, split mistakes, and label alignment |

The five packages from `Emily2040/data-science-agent-skills` are unavailable in this setup. Follow the project's approved chronological split, purge rules, and frozen threshold. Keep 2022 sealed. [Full guide and compatibility notes](ML_SKILLS_GUIDE.md).
