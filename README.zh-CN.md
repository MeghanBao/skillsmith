# Skillsmith 🔨

[English](README.md) · **中文**

**把企业里散落的原始知识——SOP、内部文档、聊天/Slack 记录、录屏笔记——锻造成可复用的 agent skill，并测试、迭代、交付。**

Skillsmith 是一条流水线的三层结构：

```
原始知识（SOP / 文档 / 转录）
        │
        ▼
核心引擎   ── 生成 → 测试 → 评估 → 迭代        （对标 skill-creator 方法论）
        │
        ▼
批量层     ── 一次跑完整个文件夹，并行，附带 review 报告
        │
        ▼
输出层     ── 同一份 SkillIR → 多种目标格式（Claude Code、AdaL @skills…）
```

核心洞察：这不是三个独立功能，而是同一条流水线的三层。内核是**单个生成+评估引擎**；批量只是在它外面包一层调度；跨格式导出只是一组渲染器，作用在**同一份中间表示**（`SkillIR`）上。加一个目标格式 = 加一个渲染器，永远不碰生成/评估逻辑。

## 安装

```bash
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-...
```

## 使用

```bash
# 单文档 → 单 skill，渲染成所有格式，输出到 ./dist
skillsmith forge examples/reset-password-sop.md

# 只导出 Claude Code 的 SKILL.md，并打印中间表示
skillsmith forge examples/reset-password-sop.md -f claude-code --json

# 整个文件夹 → 多个 skill + dist/report.json（标出哪些需人工 review）
skillsmith batch ./sops --workers 8

# 支持哪些输出格式 / 输入格式？
skillsmith formats
skillsmith inputs
```

## 核心循环怎么跑

`forge_skill()`（在 `pipeline.py`）就是整套方法论：

1. **生成** —— 把源文档蒸馏成候选 `SkillIR`（`generate.py`）
2. **评估** —— LLM critic 从「忠实 / 原子 / 可执行 / 可触发 / 有护栏」五个维度打分（`evaluate.py`）
3. **迭代** —— 判定为 `revise` 时，critic 的修改建议回灌给下一轮生成，直到 `pass` 或用尽迭代预算
4. 最终置信度由 critic 决定，批量报告会把任何低于 `high` 的产物标出来待人工 review

## 架构

| 模块 | 职责 |
|------|------|
| `ir.py` | `SkillIR` —— 与格式无关的中间表示 |
| `generate.py` | 源文档 → 候选 `SkillIR` |
| `evaluate.py` | 候选 → 结构化判定 + 修改建议 |
| `pipeline.py` | 生成→评估→迭代 循环 |
| `batch.py` | 文件夹级调度 + 汇总报告 |
| `loaders/` | 源文件 → 干净纯文本（`.md`、`.pdf`、`.html`、`.vtt`/`.srt`、Slack `.json`） |
| `renderers/` | `SkillIR` → 目标文件（`claude-code`、`adal`…） |
| `evalset.py` | critic 的 golden 回归测试 harness |
| `llm.py` | 唯一 import Anthropic SDK 的模块 |
| `cli.py` | `forge` / `batch` / `formats` / `inputs` / `eval-critic` 命令 |

## 输入格式

加载器（loader）会在蒸馏前先把每种输入统一成纯文本。`skillsmith inputs` 可列出全部。

| 加载器 | 扩展名 | 说明 |
|--------|--------|------|
| text | `.md` `.markdown` `.txt` `.rst` | 直通 |
| pdf | `.pdf` | 逐页抽取文本（pypdf） |
| html | `.html` `.htm` | 剥离 script/style/nav 等噪音（BeautifulSoup） |
| vtt | `.vtt` `.srt` | 字幕 → 正文；去掉时间轴和自动字幕的滚动重复行 |
| slack | `.json` | Slack 导出 → `姓名: 消息` 转录；通过同级 `users.json` 解析 `@提及`；非 Slack 的 JSON 原样返回 |

## 配置

| 环境变量 | 默认值 | 用途 |
|----------|--------|------|
| `ANTHROPIC_API_KEY` | —— | 真实运行必需 |
| `SKILLSMITH_MODEL` | `claude-sonnet-4-6` | 蒸馏模型；难源可升到 `claude-opus-4-8` |

## 加一个输出格式

1. 在 `renderers/` 里继承 `Renderer`，设 `format_id`，实现 `render()`。
2. 在 `renderers/__init__.py` 里注册实例。

就这些——生成和评估引擎完全不动。

## 加一个输入格式

1. 在 `loaders/` 里继承 `Loader`，设 `suffixes`，实现 `load()`。
2. 在 `loaders/__init__.py` 里注册实例。

和渲染器同理——生成和评估永远不变。

## 给评委出考卷（golden 回归集）

critic 本身是个 LLM，一旦你改 `prompts/eval_skill.md` 或换模型，它的判断可能悄悄变差。`evals/golden/` 存的就是**人工标注好标准答案的考题**——每条是 `(源文档, 候选 skill, 应有的判定)` 外加「本该扣分的维度」——`eval-critic` 让真实评委重做一遍：

```bash
skillsmith eval-critic                      # 需要 ANTHROPIC_API_KEY
skillsmith eval-critic --threshold 0.9      # 更严的门槛
```

它输出**判定一致率、弱维度召回率、混淆矩阵**，回归时以非零码退出，可用来卡 CI：

```
Critic golden eval — 12 case(s)
  verdict agreement : 92% (threshold 85%)  ✅ PASS
  weak-dim recall   : 100%

  confusion (rows=expected, cols=actual):
                 pass   revise   reject
       pass         3        1        0
     revise         0        6        0
     reject         0        0        2
```

往 `evals/golden/` 里丢一个 JSON 对象（或数组）就能加样本。种子集覆盖了 忠实/原子/可执行/可触发/有护栏 各类失败模式，外加「源太薄」和「跑题」两类 reject。

## 测试

```bash
pytest -v          # 全程离线：用 fake completer 脚本化 LLM 响应
```

## 路线图

- [x] 核心 生成→评估→迭代 引擎 + `SkillIR`
- [x] 批量调度 + review 报告
- [x] 渲染器：Claude Code `SKILL.md`、AdaL `@skills`
- [x] 源加载器：PDF、HTML、Slack 导出、VTT/SRT 转录
- [x] Golden eval 集 + critic 回归测试
- [ ] OpenCode 渲染器
- [ ]「企业知识沉淀即服务」面向中小企业的产品化

## License

MIT
