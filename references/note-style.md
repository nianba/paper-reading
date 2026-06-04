# Note Style Preferences

Use this reference when creating final notes, recap tables, or polished Markdown artifacts.

## Defaults

- Write body text in Simplified Chinese.
- Keep standard technical terms in English when translation would reduce clarity.
- Keep Markdown self-contained and copyable.
- Do not default to HTML, standalone pages, or presentation-style output.
- Do not force a fixed note template.
- Do not number headings unless the user asks.

## Structure Selection

Choose the structure from the user's intent:

- "慢慢来", "完全读懂": start with a reading map, then explain one layer at a time.
- "整理成笔记": produce a structured Markdown note whose detail level follows the user request and paper complexity; make it compact only when the user asks.
- "整理成表格", "适合回顾": use Markdown tables or method-grouped short notes.
- "相关工作", "调研": separate directly related work, broader comparators, and engineering options.
- "训练监督", "输入输出", "硬件": answer in causal slices and separate recorded data, reconstructed state, supervision labels, model input, and model output.

## Useful Content Atoms

Use only the atoms that fit the paper and request:

- 元信息：title, authors, year, venue, arXiv ID, DOI, code, dataset.
- 论文要解决的问题。
- 核心方法结构。
- 输入、输出、动作空间、观测空间。
- 数据来源和数据处理。
- 训练目标、监督标签、loss、sampling 或 rollout 方式。
- 硬件、传感器、控制频率、部署假设。
- 实验任务、指标、baseline、ablation、失败案例。
- 与已有方法的区别。
- 复现价值和工程风险。
- 明确的未知或论文未说明部分。

## Robotics/VLA Emphasis

For robotics, VLA, imitation learning, or post-training papers, preserve these distinctions:

- Upstream base model facts vs current paper adaptation facts.
- Demonstration data vs recovered states vs training labels.
- High-level policy output vs low-level controller behavior.
- Action chunking vs single-step actions.
- Real robot setup vs simulation setup.
- Published result vs engineering recommendation.

## Table Patterns

These are optional shapes, not templates.

```markdown
| 维度 | 内容 |
|---|---|
| 解决问题 |  |
| 核心思路 |  |
| 输入输出 |  |
| 训练监督 |  |
| 实验结论 |  |
| 适用边界 |  |
```

```markdown
| 方法 | 解决问题 | 核心机制 | 训练/数据 | 关键边界 |
|---|---|---|---|---|
|  |  |  |  |  |
```

## Avoid

- Long generic summaries before understanding the mechanism.
- Treating speculative implementation details as paper facts.
- Mixing related work, user-proposed engineering ideas, and published results into one bucket.
- Adding empty conclusion sections just to make the note look complete.
- Leaving process artifacts when the user only asked for final paper notes.
