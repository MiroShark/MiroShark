<sup>[English](CONTRIBUTING.md) · 中文</sup>

# 贡献指南

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

`.github/workflows/tests.yml` 工作流会在每次推送和 PR 时运行单元测试套件。
