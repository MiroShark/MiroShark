<sup>[English](CONTRIBUTING.md) · 中文</sup>

# 贡献指南

感谢你帮助让群体智能模拟更便宜、更可信。本指南涵盖本地环境搭建、测试套件，以及如何提交 PR。

## 开发环境搭建

**前置条件：** Node.js ≥ 18、用于 Python 后端的 [uv](https://docs.astral.sh/uv/)，以及 Docker（用于 Neo4j）。

1. 一步安装前端和后端依赖：

   ```bash
   npm run setup:all
   ```

   该命令会运行 `npm install`、安装 `frontend/` 依赖，然后执行 `cd backend && uv sync`。

2. 创建环境变量文件，并至少填入一个 LLM 密钥：

   ```bash
   cp .env.example .env
   ```

   默认配置面向 OpenRouter —— 将密钥粘贴到 `*_API_KEY` 槽位中，或参照 `.env.example` 中的「Alternatives」部分切换到完全本地的 Ollama 方案。每个变量都记录在 [docs/CONFIGURATION.md](docs/CONFIGURATION.md) 中。

3. 启动 Neo4j（记忆流水线背后的图数据库）。需先在 `.env` 中设置 `NEO4J_PASSWORD`：

   ```bash
   docker compose up -d neo4j
   ```

4. 同时运行后端（`:5001`）和前端（`:3000`）：

   ```bash
   npm run dev
   ```

   `predev` 会先释放被陈旧进程占用的 3000 和 5001 端口。

## 测试

pytest 测试套件位于 `backend/tests/`。

### 快速离线单元测试套件

```bash
cd backend && pytest -m "not integration"
```

### 集成测试

集成测试会访问位于 `MIROSHARK_API_URL`（默认为 `http://localhost:5001`）的实时后端。旧版 E2E 脚本被封装为 `slow` 测试：

```bash
pytest -m integration                # 端点契约（秒级）
pytest -m "integration and slow"     # 完整流水线烟雾测试（分钟级）
```

某些集成测试需要一个预先存在的模拟 —— 请设置 `MIROSHARK_TEST_SIM_ID=sim_xxx`。

`backend/scripts/test_*.py` 中的手动运行脚本仍可作为独立程序使用；pytest 层只是将它们注册以供发现。

### CI

`.github/workflows/tests.yml` 工作流会在每次向 `main` 推送和提交 PR 时运行单元测试套件（`pytest -m "not integration"`）。

## 提交 PR

- **从 `main` 拉取分支**，并使用带类型的前缀：`feat/…`、`fix/…`、`docs/…`、`test/…` 或 `chore/…`。
- **以 [Conventional Commit](https://www.conventionalcommits.org/) 格式为 PR 命名** —— 与已合并历史使用的前缀一致，例如 `feat: …`、`fix: …`、`docs: …`。需要时可加上作用域：`feat(api): …`。
- **保持聚焦。** 每个 PR 只做一件事 —— 不要把无关改动捆绑在一起。
- **推送前先运行快速单元测试套件**（`cd backend && pytest -m "not integration"`）；CI 运行的是同一套测试，因此本地通过是 PR 通过的最快途径。
- **保持翻译同步。** 如果你改动了带有 `*.zh-CN.md` / `*.ja.md` 对应版本的文档（README、本文件），请一并更新 —— 或在 PR 中注明它仍需翻译。

## 新增 API 端点

后端的 HTTP 接口记录在 `backend/openapi.yaml` 中，并有一项漂移测试（`backend/tests/test_unit_openapi.py`）**在规范与实际 Flask 路由不一致时会让 CI 失败** —— 由此让规范与代码保持同步。新增端点的步骤：

1. **注册路由**：在 `backend/app/api/` 中对应的 blueprint 上注册（例如 `@simulation_bp.route('/<simulation_id>/your-surface')`）。全新的 blueprint 必须在 `backend/app/__init__.py` 中注册，并在漂移测试的 `_BLUEPRINT_PREFIXES` 映射中加入前缀条目。
2. **记录路径**：在 `backend/openapi.yaml` 的 `paths:` 下记录，并使用一个已在顶层声明的 tag。内部/调试路由应改为加入测试的 `_UNDOCUMENTED_ALLOWLIST`。
3. **添加单元测试**：在 `backend/tests/test_unit_<feature>.py` 中添加。保持离线（无实时 Flask 应用、无 Neo4j），以便在最简 CI 环境中运行 —— 可参照已有的 `test_unit_*.py` 文件。

记录在案的端点会自动出现在 `/api/docs` 的 Swagger UI 和 `/api/openapi.json` 的 JSON 规范中，二者均由同一份 `openapi.yaml` 提供。
