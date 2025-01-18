from setuptools import setup, find_packages

setup(
    name="smart_thermostat",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "homeassistant",
    ],
) 