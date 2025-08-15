import json


def main():
    # Read runtime requirements from manifest.json
    with open("custom_components/eta_webservices/manifest.json") as f:
        manifest = json.load(f)
    runtime_requirements = manifest.get("requirements", [])

    # Define development and test requirements
    dev_requirements = [
        "homeassistant",
        "aiohttp",
    ] + runtime_requirements

    test_requirements = [
        "pytest-homeassistant-custom-component",
        "mock",
        "pytest-asyncio",
    ] + runtime_requirements

    with open("requirements_dev.txt", "w") as f:
        for package in sorted(list(set(dev_requirements))):
            f.write(package + "\n")

    with open("requirements_test.txt", "w") as f:
        for package in sorted(list(set(test_requirements))):
            f.write(package + "\n")


if __name__ == "__main__":
    main()
