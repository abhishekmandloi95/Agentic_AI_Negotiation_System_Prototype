import pytest

@pytest.fixture
def sample_agent_config():
    def _make(agent_id):
        return {
            "agent_id": agent_id,
            "style": "neutral",
            "inventory": {"analytics": 100},
            "needs": {"devops": 50},
        }
    return _make