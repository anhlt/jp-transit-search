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
        <div class="station">
            <ul class="time"><li>10:00</li></ul>
            <p class="icon"><span class="icnStaDep">発</span></p>
            <dl><dt>横浜</dt></dl>
        </div>
        <div class="fareSection">
            <div class="access">
                <ul class="info">
                    <li class="transport">
                        <span class="line" style="border-color:#00b5ad"></span>
                        <div><span class="icon icnTrain"></span>京急本線快特<span class="destination">羽田空港第3ターミナル行</span></div>
                    </li>
                    <li class="platform">[発] <span class="num">1</span>番線 → [着] <span class="num">3</span>番線</li>
                </ul>
            </div>
            <p class="fare"><span>303円</span></p>
        </div>
        <div class="station">
            <ul class="time"><li>10:16</li></ul>
            <p class="icon"><span class="icnStaTrain"></span></p>
            <dl><dt>品川</dt></dl>
        </div>
        <div class="fareSection">
            <div class="access">
                <ul class="info">
                    <li class="transport">
                        <span class="line" style="border-color:#80c241"></span>
                        <div><span class="icon icnTrain"></span>JR山手線内回り<span class="destination">大崎行</span></div>
                    </li>
                    <li class="platform">[発] <span class="num">2</span>番線 → [着] <span class="num">1</span>番線</li>
                </ul>
            </div>
            <p class="fare"><span>157円</span></p>
        </div>
        <div class="station">
            <ul class="time"><li>10:26</li></ul>
            <p class="icon"><span class="icnStaTrain"></span></p>
            <dl><dt>有楽町</dt></dl>
        </div>
        <div class="fareSection">
            <div class="access">
                <ul class="info">
                    <li class="transport">
                        <span class="line" style="border-color:#c1a470"></span>
                        <div><span class="icon icnTrain"></span>東京メトロ有楽町線(和光市−新木場)<span class="destination">新木場行</span></div>
                    </li>
                    <li class="platform">[発] <span class="num">1</span>番線 → [着] <span class="num">2</span>番線</li>
                </ul>
            </div>
            <p class="fare"><span>168円</span></p>
        </div>
        <div class="station">
            <ul class="time"><li>10:33</li></ul>
            <p class="icon"><span class="icnStaArr">着</span></p>
            <dl><dt>豊洲</dt></dl>
        </div>
    </div>
    """


@pytest.fixture
def temp_config_dir(tmp_path):
    """Temporary configuration directory."""
    config_dir = tmp_path / ".jp-transit-search"
    config_dir.mkdir()
    return config_dir
