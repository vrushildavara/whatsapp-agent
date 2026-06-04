from unittest.mock import AsyncMock, patch

import pytest
from asgi_lifespan import LifespanManager

from app.main import app


@pytest.mark.asyncio
@patch("app.main.start_background_jobs", new_callable=AsyncMock)
async def test_lifespan_triggered(mock_bg_jobs: AsyncMock) -> None:
    async with LifespanManager(app):
        pass

    mock_bg_jobs.assert_awaited_once()
