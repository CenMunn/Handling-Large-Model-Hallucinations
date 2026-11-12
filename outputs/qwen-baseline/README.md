# Qwen3-8B 本地基线

当前工作区：D:/幻觉比赛。完整运行状态以 status.json 为准；程序已生成不等于模型已启动或比赛已提交。

## 配置

- 模型：Qwen 官方 Qwen3-8B-GGUF，Q4_K_M，5,027,783,488 bytes。
- SHA-256：d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785。
- llama.cpp：b11985 Windows x64 Vulkan。明确选择 Vulkan1（RTX 5060），避免误用 Intel 核显。
- 初始服务：127.0.0.1:8080，单槽，8192 token 总上下文，最多输出384 token，关闭思考，不静默移动上下文。
- 8192 是本机实验配置，不是已确认的赛事上限。正式输入过长必须调整部署，禁止擅自丢弃题目。
- 初始并发1仅用于基线验收；正式提交前必须压测并调整，最多16。
- 请求通过子进程限定50秒总耗时，不自动重试。服务失败与证据不足分别记录。

## 文件

- launch.py：启动本机GPU推理，记录PID和日志，生成专用API key。
- platform/：平台调用目录，run.py逐字复制官方版本，run.sh仅增加MAX_WORKERS。
- test_adapter.py：结果对齐、中文写盘、缺失结果、错误分类与墙钟超时测试。
- dev_cases.json：120条模板化合成开发题；答案由构造规则得到，尚需人工审阅，不能代表正式集。
- evaluate.py：记录原始回答、耗时、token用量、截断和关键词检查结果。proxy_pass不是官方评分或人工准确率。
- start-ngrok.ps1：使用已获授权的旧域名转发8080；若已有ngrok进程会停止并提示，避免冲突。
- finish_setup.py：模型下载校验后运行本地链路与两组14题smoke，再验证授权的公网API。未自动提交竞赛平台。
- .local/：本地密钥、进程记录和日志，不要公开或加入源码仓库。
- platform-model.zip：仅在公网验证通过后生成，含平台按要求写死的专用API key，不要公开分享。

## 重启或恢复

Python 路径：C:/Users/g'g/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe。

在工作区运行：

```powershell
& "C:/Users/g'g/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" work/download_parallel.py
& "C:/Users/g'g/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe" outputs/qwen-baseline/finish_setup.py
```

finish_setup.py不是重复启动入口：如本地服务已运行，先检查.local/server-process.json与监听端口。不要重复启动覆盖日志。

## 平台接入

公网验证通过后，把platform目录中的4个文件放入实验室工作区根目录的model目录（与input/output/project同级），使用Python3.10。

```bash
python3.10 model/run.py input output/result.json
```

检查result.json条数、id、问题原文和列表格式的回答，再保存镜像、等待构建完成，进行测试阶段提交。接口验收、并发压测与平台实际提交缺一不可。

## 当前验收进展

官方模型已完整下载并通过SHA-256校验，RTX 5060 GPU服务与ngrok公网API已运行。平台包使用4并发；实际平台实验室尚待上传与测试提交。

原始与v2提示词均通过120条简单合成题的修订诊断检查，尚未证明准确率提升。v1提示词曾在否定前提题过度拒答，已修正。系统代理路径的公网请求曾偶发断连，当前客户端改为直接HTTPS，不修改系统代理设置。详见results/concurrency-4-direct.json。

## 保持服务在线（平台超时排查后新增）

请在Windows资源管理器中双击START-SERVICES.cmd，看到READY后保持窗口打开、电脑开机联网。此入口由用户控制台持有模型与ngrok服务，避免依赖Codex工具会话的进程生命周期。之前21题超时时，本机模型与ngrok均已不在运行；恢复后仍需从平台验证公网健康接口，不能仅凭本机测试认定整条链路已修复。
