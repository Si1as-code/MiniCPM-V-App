# Learnings

Corrections, insights, and knowledge gaps captured during development.

**Categories**: correction | insight | knowledge_gap | best_practice

---

## [LRN-20260723-001] best_practice

**Logged**: 2026-07-23T14:03:00+08:00
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
MiniCPM-V 4.6 必须使用 transformers >= 5.7.0，低版本会导致多种难以定位的报错，优先检查版本而非修改代码。

### Details
在调试 MiniCPM-V 4.6 的过程中，多次遇到以下报错：

1. **AutoModelForImageTextToText 导入失败**（ImportError）
   - 根因：transformers 4.x 版本中没有 `AutoModelForImageTextToText` 类
   - 解决：`pip install "transformers>=5.7.0"`

2. **processor_kwargs 参数不被识别**
   - 根因：低版本 `apply_chat_template()` 不支持 `processor_kwargs` 参数
   - 解决：升级 transformers 到 5.7.0+

3. **大尺寸图片切片时 shape 不匹配**
   - 报错：`shape '[3, 1045, 1152]' invalid for input of size 3612672`
   - 根因：低版本对 LLaVA-UHD v4 的切片处理不支持
   - 解决：升级 transformers 到 5.7.0+

**关键洞察**：这三种看似不同的报错，实际上有相同的根因——transformers 版本过低。用户反馈"找到问题了，是 transformers 版本问题，我重新安装了 5.7 版本的，现在正常了"。

### Suggested Action
遇到 transformers 相关报错时，执行以下检查顺序：
1. `pip show transformers` 确认版本 >= 5.7.0
2. 如果版本过低，优先升级而非修改代码逻辑
3. 升级后重新测试，确认问题是否解决

### Metadata
- Source: user_feedback
- Related Files: app/engine/model_loader.py, app/engine/inference_engine.py
- Tags: transformers, minicpmv, version-compatibility, debugging
- Pattern-Key: deps.version-conflict
- Recurrence-Count: 1
- First-Seen: 2026-07-23
- Last-Seen: 2026-07-23

---
