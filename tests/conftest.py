import pytest
import pytest_asyncio
from backend.database import engine


def pytest_collection_modifyitems(items):
    for item in items:
        if isinstance(item, pytest.Function) and item.get_closest_marker("asyncio"):
            item.add_marker(pytest.mark.asyncio(loop_scope="session"), append=False)


@pytest_asyncio.fixture(autouse=True, scope="session")
async def dispose_engine():
    yield
    await engine.dispose()
