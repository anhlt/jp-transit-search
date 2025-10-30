"""Test configuration and fixtures."""


import pytest


@pytest.fixture
def sample_station_data():
    """Sample station data for testing."""
    return [
        {"name": "横浜", "prefecture": "神奈川県", "lines": ["JR東海道本線"]},
        {"name": "豊洲", "prefecture": "東京都", "lines": ["東京メトロ有楽町線"]},
        {"name": "新宿", "prefecture": "東京都", "lines": ["JR山手線", "JR中央線"]},
    ]


@pytest.fixture
def sample_yahoo_response():
    """Sample Yahoo Transit HTML response."""
    return """
    <div class="routeSummary">
        <li class="time">49分(乗車33分)</li>
        <li class="transfer">乗換：2回</li>
        <li class="fare">IC優先：628円</li>
    </div>
    <div class="routeDetail">
        <div class="station">横浜</div>
        <li class="transport"><div>京急本線快特</div></li>
        <li class="estimatedTime">16分</li>
        <p class="fare">303円</p>
        <div class="station">品川</div>
        <li class="transport"><div>JR山手線内回り</div></li>
        <li class="estimatedTime">10分</li>
        <p class="fare">157円</p>
        <div class="station">有楽町</div>
        <li class="transport"><div>東京メトロ有楽町線(和光市−新木場)</div></li>
        <li class="estimatedTime">7分</li>
        <p class="fare">168円</p>
        <div class="station">豊洲</div>
    </div>
    """


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary configuration directory."""
    config_dir = tmp_path / ".jp-transit-search"
    config_dir.mkdir()
    return config_dir
