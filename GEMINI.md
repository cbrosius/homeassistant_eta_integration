# Gemini Project Memory

This file helps Gemini remember important details about this project. Please keep it up-to-date.

## Project Overview

This project is a Home Assistant integration for ETA heating systems. The integration is named `eta_webservices` and provides sensors, switches, numbers, and other entities to monitor and control the heating system.

## Coding Style & Conventions

- **Code Formatting**: The project uses the `black` code formatter to ensure a consistent code style. All Python code should be formatted with `black` before committing.
- **Linting**: The project uses `flake8` for linting to identify potential errors and style issues. The CI pipeline runs `flake8` checks.

## Dependencies

- **Runtime Dependencies**: The runtime dependencies for the integration are defined in the `requirements` key of the `custom_components/eta_webservices/manifest.json` file.
- **Development and Test Dependencies**: The dependencies for development and testing are defined in `requirements_dev.txt` and `requirements_test.txt` respectively.
- **Dependency Generation**: The `.github/generate_requirements.py` script is used to generate the `requirements_dev.txt` and `requirements_test.txt` files based on the runtime dependencies in `manifest.json` and a hardcoded list of development and test packages.

## CI/CD

The project has a CI/CD pipeline defined in `.github/workflows/ci.yml`. The pipeline performs the following checks:

- **Code Formatting**: Checks if the code is formatted with `black`.
- **Linting**: Runs `flake8` to check for linting errors.
- **Security**: Uses `bandit` to perform a security analysis of the code.
- **Home Assistant Validation**: Uses `hassfest` to validate the integration against Home Assistant's requirements.

## Testing

The CI pipeline is set up to run tests, but the test execution step is currently commented out in `.github/workflows/ci.yml`. To run tests locally, you would typically use `pytest`.

## User Preferences

- **Black Formatting**: Please format all Python code changes using the `black` code formatter before presenting them.
