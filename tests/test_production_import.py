#!/usr/bin/env python
"""生产边缘冒烟：FastAPI app 导入与路由存在性（无 FastAPI 环境自动跳过）。"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(HAS_FASTAPI, "未安装 fastapi，跳过生产边缘导入测试")
class ProductionEdgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT))
        from production import app as production_app  # noqa: F401

        cls.production_app = production_app

    def test_routes_exist(self):
        paths = {getattr(route, "path", "") for route in self.production_app.app.routes}
        self.assertIn("/healthz", paths)
        self.assertIn("/readyz", paths)

    def test_security_middleware_configured(self):
        # `@app.middleware("http")` 注册为 BaseHTTPMiddleware，真实函数在 options["dispatch"]
        names = []
        for middleware in self.production_app.app.user_middleware:
            dispatch = middleware.kwargs.get("dispatch")
            names.append(getattr(dispatch, "__name__", "") or middleware.cls.__name__)
        self.assertTrue(any("security" in name.lower() for name in names), names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
