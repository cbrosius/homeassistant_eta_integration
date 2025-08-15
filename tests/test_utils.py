from custom_components.eta_webservices.utils import create_device_info


def test_create_device_info():
    """Test the create_device_info function."""
    # Given
    host = "127.0.0.1"
    port = "8080"
    device_name = "My ETA Device"

    # When
    device_info = create_device_info(host, port, device_name)

    # Then
    assert isinstance(device_info, dict)
    assert device_info["identifiers"] == {
        ("eta_webservices", "eta_127_0_0_1_8080_My ETA Device")
    }
    assert device_info["name"] == "ETA My ETA Device"
    assert device_info["manufacturer"] == "ETA"
    assert device_info["configuration_url"] == "https://www.meineta.at"


def test_create_device_info_default_name():
    """Test the create_device_info function with the default device name."""
    # Given
    host = "192.168.1.1"
    port = "8888"

    # When
    device_info = create_device_info(host, port)

    # Then
    assert isinstance(device_info, dict)
    assert device_info["identifiers"] == {
        ("eta_webservices", "eta_192_168_1_1_8888_ETA")
    }
    assert device_info["name"] == "ETA"
    assert device_info["manufacturer"] == "ETA"
    assert device_info["configuration_url"] == "https://www.meineta.at"
