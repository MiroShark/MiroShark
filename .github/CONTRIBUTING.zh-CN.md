<sup>[English](CONTRIBUTING.md) · 中文</sup>

# 为 MiroShark 做贡献

感谢你帮助让群体智能模拟更便宜、更可信。本指南涵盖本地环境搭建、测试套件，以及如何提交 PR。

## 贡献方式

- **修复缺陷或新增功能** —— Flask 后端（`backend/`）或 Next.js 前端（`frontend/`）。
- **新增 API 端点** —— 见下方清单；OpenAPI 规范与一个漂移测试会让代码和文档保持同步。
- **文档与翻译** —— README 和本文件都有 `*.zh-CN.md` / `*.ja.md` / `*.fr.md` 对应版本，请保持同步。

## 开始之前

- **从 `main` 切出分支**，使用带类型前缀的分支名：`feat/…`、`fix/…`、`docs/…`、`test/…` 或 `chore/…`。
- **一个 PR 只做一件事。** 不要把不相关的改动捆绑在一起。
- **标题遵循 [Conventional Commit](https://www.conventionalcommits.org/) 规范** —— `feat: …`、`fix: …`、`docs: …`；需要时加上 scope 以更清晰地表达意图（`feat(api): …`）。PR 采用 squash 合并，因此标题会成为提交主题。

## 开发环境搭建

**前置条件：** Node.js ≥ 18、用于 Python 后端的 [uv](https://docs.astral.sh/uv/)，以及 Docker（用于 Neo4j）。

1. 一步安装前端和后端依赖（`npm install`、`frontend/` 依赖，然后 `cd backend && uv sync`）：

   ```bash
   npm run setup:all
   ```

2. 创建环境文件并至少填入一个 LLM 密钥：

   ```bash
   cp .env.example .env
   ```

   默认面向 OpenRouter —— 将密钥粘贴到 `*_API_KEY` 各处，或使用 `.env.example` 中的“Alternatives”块切换到完全本地的 Ollama 方案。每个变量都记录在 [docs/CONFIGURATION.md](../docs/CONFIGURATION.md)。

3. 启动 Neo4j（需先在 `.env` 中设置 `NEO4J_PASSWORD`）：

   ```bash
   docker compose up -d neo4j
   ```

4. 同时运行后端（`:5001`）和前端（`:3000`）（`predev` 会在有陈旧进程占用端口时先释放它们）：

   ```bash
   npm run dev
   ```

## 测试与 CI

pytest 测试套件位于 `backend/tests/`。

```bash
cd backend && pytest -m "not integration"      # 快速的离线单元测试
pytest -m integration                           # 端点契约测试（需要运行中的后端）
pytest -m "integration and slow"                # 完整流水线冒烟测试（数分钟）
```

集成测试会访问位于 `MIROSHARK_API_URL`（默认 `http://localhost:5001`）的运行中后端；部分测试需要通过 `MIROSHARK_TEST_SIM_ID=sim_xxx` 提供一个已存在的模拟。`.github/workflows/tests.yml` 工作流会在每次向 `main` 推送和提 PR 时运行单元套件（`pytest -m "not integration"`），因此**本地单元测试跑通是让 PR 变绿最快的方式。**

### 新增 API 端点

后端的 HTTP 接口记录在 `backend/openapi.yaml`，一个漂移测试（`backend/tests/test_unit_openapi.py`）**会在规范与真实 Flask 路由不一致时让 CI 失败。** 新增端点的步骤：

1. **注册路由** —— 在 `backend/app/api/` 中对应的 blueprint 上注册。全新的 blueprint 必须在 `backend/app/__init__.py` 中注册，并在漂移测试的 `_BLUEPRINT_PREFIXES` 映射中加入前缀。
2. **记录路径** —— 在 `backend/openapi.yaml` 的 `paths:` 下，使用顶层已声明的 tag。内部/调试路由改为放入测试的 `_UNDOCUMENTED_ALLOWLIST`。
3. **添加离线单元测试** —— 在 `backend/tests/test_unit_<feature>.py`（无需运行 Flask、无需 Neo4j），可参照现有的 `test_unit_*.py`。

已记录的端点会自动出现在 `/api/docs` 的 Swagger UI 中。

## 提交 Pull Request

- 保持改动聚焦、标题符合规范；它会成为 squash 后的提交主题。
- 在描述中说明**改了什么**以及**为什么**；关联相关 issue（`Fixes #123`）。
- **推送前先跑一遍快速单元套件** —— CI 跑的是同一套。
- **保持翻译同步。** 如果你改动了带 `*.zh-CN.md` / `*.ja.md` / `*.fr.md` 对应版本的文档，请一并更新 —— 或在 PR 中注明它仍需翻译。

## 报告缺陷与提出功能需求

提交 issue，包含复现步骤、你的预期、实际结果，以及你的环境（操作系统、Node/Python 版本、部署目标）。

**发现安全问题？** 不要提 issue —— 请遵循 [`SECURITY.md`](SECURITY.md) 私下报告。

## 许可证

提交贡献即表示你同意你的贡献按仓库的 [LICENSE](../LICENSE) 授权。
