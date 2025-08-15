import asyncio
from unittest.mock import MagicMock
from custom_components.eta_webservices.api import EtaAPI


import pytest
from unittest.mock import AsyncMock


def test_build_uri():
    """Test the build_uri method of the EtaAPI."""
    # Given
    session = MagicMock()
    host = "192.168.1.100"
    port = "8080"
    api = EtaAPI(session, host, port)
    suffix = "/user/menu"

    # When
    uri = api.build_uri(suffix)

    # Then
    assert uri == "http://192.168.1.100:8080/user/menu"


from packaging import version
from custom_components.eta_webservices.const import (
    CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
)


@pytest.mark.parametrize(
    "input_data, force_number_handling, expected_value, expected_unit",
    [
        # Test case 1: Standard float sensor
        (
            {"@unit": "°C", "@scaleFactor": "10", "@decPlaces": "1", "#text": "255"},
            False,
            25.5,
            "°C",
        ),
        # Test case 2: Percentage
        (
            {"@unit": "%", "@scaleFactor": "1", "@decPlaces": "0", "#text": "50"},
            False,
            50.0,
            "%",
        ),
        # Test case 3: Text value
        (
            {"@unit": "", "@strValue": "Some Text", "#text": "123"},
            False,
            "Some Text",
            "",
        ),
        # Test case 4: Force number handling on a text-like value
        (
            {"@unit": "", "@scaleFactor": "100", "@decPlaces": "2", "#text": "12345"},
            True,
            123.45,
            "",
        ),
        # Test case 5: Zero value
        (
            {"@unit": "kW", "@scaleFactor": "10", "@decPlaces": "1", "#text": "0"},
            False,
            0.0,
            "kW",
        ),
    ],
)
def test_parse_data(input_data, force_number_handling, expected_value, expected_unit):
    """Test the _parse_data method with various inputs."""
    # Given
    session = MagicMock()
    api = EtaAPI(session, "testhost", "8080")

    # When
    value, unit = api._parse_data(input_data, force_number_handling)

    # Then
    assert value == expected_value
    assert unit == expected_unit


@pytest.mark.asyncio
async def test_get_data():
    """Test get_data method."""
    # Given
    uri = "123/456/789"
    xml_string = '<eta><value uri="/user/var/123/456/789" strValue="25.5 °C" unit="°C" decPlaces="1" scaleFactor="10" advTextOffset="0">255</value></eta>'
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = AsyncMock(return_value=xml_string)
    mock_session.get = AsyncMock(return_value=mock_response)

    api = EtaAPI(mock_session, "testhost", "8080")

    # When
    value, unit = await api.get_data(uri)

    # Then
    assert value == 25.5
    assert unit == "°C"
    mock_session.get.assert_called_once_with(f"http://testhost:8080/user/var/{uri}")


@pytest.mark.asyncio
async def test_does_endpoint_exists_success():
    """Test does_endpoint_exists method for a successful connection."""
    # Given
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_session.get = AsyncMock(return_value=mock_response)

    api = EtaAPI(mock_session, "testhost", "8080")

    # When
    result = await api.does_endpoint_exists()

    # Then
    assert result is True
    mock_session.get.assert_called_once_with("http://testhost:8080/user/menu")


@pytest.mark.asyncio
async def test_does_endpoint_exists_fail():
    """Test does_endpoint_exists method for a failed connection."""
    # Given
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 404
    mock_session.get = AsyncMock(return_value=mock_response)

    api = EtaAPI(mock_session, "testhost", "8080")

    # When
    result = await api.does_endpoint_exists()

    # Then
    assert result is False
    mock_session.get.assert_called_once_with("http://testhost:8080/user/menu")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "xml_string, expected_version",
    [
        ('<eta><api version="1.2" /></eta>', "1.2"),
        ('<eta><api version="1.1" /></eta>', "1.1"),
        ('<eta><api version="2.0" /></eta>', "2.0"),
    ],
)
async def test_get_api_version(xml_string, expected_version):
    """Test get_api_version method with different version strings."""
    # Given
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = AsyncMock(return_value=xml_string)
    mock_session.get = AsyncMock(return_value=mock_response)

    api = EtaAPI(mock_session, "testhost", "8080")

    # When
    result = await api.get_api_version()

    # Then
    assert result == version.parse(expected_version)
    mock_session.get.assert_called_once_with("http://testhost:8080/user/api")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "api_version, expected_result",
    [
        ("1.2", True),
        ("1.3", True),
        ("2.0", True),
        ("1.1", False),
        ("1.0", False),
    ],
)
async def test_is_correct_api_version(api_version, expected_result, monkeypatch):
    """Test is_correct_api_version method."""
    # Given
    mock_session = MagicMock()
    api = EtaAPI(mock_session, "testhost", "8080")

    # Mock get_api_version to return a specific version
    async def mock_get_version():
        return version.parse(api_version)

    monkeypatch.setattr(api, "get_api_version", mock_get_version)

    # When
    result = await api.is_correct_api_version()

    # Then
    assert result is expected_result


@pytest.mark.parametrize(
    "endpoint_info, expected",
    [
        (
            {"valid_values": {"scaled_min_value": 0, "scaled_max_value": 100}},
            True,
        ),
        ({"valid_values": {"on_value": 1, "off_value": 0}}, False),
        ({"valid_values": None}, False),
        ({"valid_values": {}}, False),
    ],
)
def test_is_writable(endpoint_info, expected):
    api = EtaAPI(MagicMock(), "host", "8080")
    assert api._is_writable(endpoint_info) == expected


@pytest.mark.parametrize(
    "endpoint_info, expected",
    [
        ({"unit": "", "endpoint_type": "TEXT"}, True),
        ({"unit": "°C", "endpoint_type": "TEXT"}, False),
        ({"unit": "", "endpoint_type": "FLOAT"}, False),
    ],
)
def test_is_text_sensor(endpoint_info, expected):
    api = EtaAPI(MagicMock(), "host", "8080")
    assert api._is_text_sensor(endpoint_info) == expected


@pytest.mark.parametrize(
    "endpoint_info, expected",
    [
        ({"unit": "°C"}, True),
        ({"unit": "%"}, True),
        ({"unit": CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT}, True),
        ({"unit": "unknown"}, False),
        ({"unit": ""}, False),
    ],
)
def test_is_float_sensor(endpoint_info, expected):
    api = EtaAPI(MagicMock(), "host", "8080")
    assert api._is_float_sensor(endpoint_info) == expected


@pytest.mark.parametrize(
    "endpoint_info, expected",
    [
        (
            {
                "valid_values": {
                    "Ein": 1,
                    "Aus": 0,
                }
            },
            True,
        ),
        (
            {
                "valid_values": {
                    "On": 1,
                    "Off": 0,
                }
            },
            True,
        ),
        ({"valid_values": {"Yes": 1, "No": 0}}, True),
        ({"valid_values": None}, False),
        ({"valid_values": {"a": 1, "b": 0}}, False),
        ({"valid_values": {"On": 1, "Off": 0, "Extra": 2}}, False),
    ],
)
def test_is_switch(endpoint_info, expected):
    api = EtaAPI(MagicMock(), "host", "8080")
    assert api._is_switch(endpoint_info) == expected


@pytest.mark.parametrize(
    "endpoint_info, expected_type",
    [
        # Writable number
        (
            {
                "unit": "°C",
                "valid_values": {"scaled_min_value": 0, "scaled_max_value": 100},
                "endpoint_type": "FLOAT",
                "value": 0,
            },
            "number",
        ),
        # Writable time
        (
            {
                "unit": CUSTOM_UNIT_MINUTES_SINCE_MIDNIGHT,
                "valid_values": {"scaled_min_value": 0, "scaled_max_value": 1439},
                "endpoint_type": "FLOAT",
                "value": 0,
            },
            "time",
        ),
        # Switch
        (
            {
                "valid_values": {"On": 1, "Off": 0},
                "value": "1",
                "unit": "",
                "endpoint_type": "TEXT",
            },
            "switch",
        ),
        # Float sensor
        (
            {
                "unit": "kW",
                "value": 12.3,
                "valid_values": None,
                "endpoint_type": "FLOAT",
            },
            "sensor",
        ),
        # Text sensor
        (
            {
                "unit": "",
                "endpoint_type": "TEXT",
                "value": "Some state",
                "valid_values": None,
            },
            "sensor",
        ),
        # Unclassifiable
        (
            {
                "unit": "unknown",
                "value": "abc",
                "valid_values": None,
                "endpoint_type": "TEXT",
            },
            None,
        ),
    ],
)
def test_classify_entity(endpoint_info, expected_type):
    """Test the classify_entity method."""
    api = EtaAPI(MagicMock(), "host", "8080")
    assert api.classify_entity(endpoint_info) == expected_type
