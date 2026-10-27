"""Production SPA-serving tests (api/main.py).

Only meaningful once a production frontend build exists (frontend/dist
-- built via `npm run build`), since FastAPI decides whether to mount
the SPA-serving routes once, at import time. CI builds the frontend
before running pytest (see .github/workflows/tests.yml) so these run
for real there; locally, without a build, they skip rather than fail
a routine `pytest` run.
"""

from pathlib import Path
import re
import sys

from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from api.main import FRONTEND_DIST, app

pytestmark = pytest.mark.skipif(
    not FRONTEND_DIST.is_dir(),
    reason="frontend/dist not built -- run `npm run build` first to exercise SPA serving",
)

client = TestClient(app)


def test_api_health_remains_a_json_api_response():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unmatched_api_path_returns_a_real_404_not_the_spa_shell():
    response = client.get("/api/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_static_asset_resolves():
    index_html = (FRONTEND_DIST / "index.html").read_text(encoding="utf-8")
    match = re.search(r'src="(/assets/[^"]+\.js)"', index_html)
    assert match is not None, "expected index.html to reference a built /assets/*.js bundle"

    response = client.get(match.group(1))

    assert response.status_code == 200


def test_deep_react_route_falls_back_to_the_spa_shell_not_a_404():
    response = client.get("/quotes/Q-12345/review")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<div id=\"root\">" in response.text


def test_root_path_serves_the_spa_shell():
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
