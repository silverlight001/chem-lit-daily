# Chem Lit Daily

一个本地运行的化学文献日报应用。你输入关键词和感兴趣期刊，应用会从 OpenAlex 抓取最近发表的论文，给出影响潜力评分、简短摘要、原文链接，并支持兴趣评分、历史记录和收藏夹。

## 运行

先安装依赖：

```powershell
python -m pip install -r requirements.txt
```

最简单的方式：双击项目里的 `双击打开文献日报.bat`。

它会在后台启动应用，并自动打开：

```text
http://localhost:8501
```

```powershell
streamlit run app.py
```

如果 `streamlit` 命令不可用：

```powershell
python -m streamlit run app.py
```

命令行跑一次日报抓取：

```powershell
python run_once.py
```

## 使用流程

1. 在左侧输入关键词和期刊名，每行一个，也可以用逗号分隔。
2. 点击“保存设置”。
3. 点击“运行今日文献扫描”。
4. 在“今日筛选”里给文献打 1-5 分，加入收藏夹，或点开原文。
5. 在“历史文献”和“收藏夹”里管理积累下来的文献。

## 评分说明

当前影响分不是官方影响因子，而是一个本地启发式分数，综合了：

- 是否命中关键词
- 是否来自你关注的期刊
- 是否属于常见高影响化学期刊
- OpenAlex 引用数
- 是否有摘要

## AI 总结

应用会为每篇文献显示原始摘要，并生成一个中文 AI 总结，说明文章做了什么、核心方法/结果是什么、创新点在哪里。

如果你想启用真正的 OpenAI 总结，请在系统环境变量中设置 `OPENAI_API_KEY`。可选设置：

```powershell
$env:OPENAI_API_KEY="你的 API key"
$env:OPENAI_SUMMARY_MODEL="gpt-5-mini"
```

没有配置 `OPENAI_API_KEY` 时，应用会使用本地规则生成简短总结，页面仍然可以正常运行。
