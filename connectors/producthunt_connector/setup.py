"""
Product Hunt Connector for Fivetran
Fetches trending products and discussions from Product Hunt for idea generation
"""

from setuptools import setup, find_packages

setup(
    name="fivetran-producthunt-connector",
    version="1.0.0",
    description="Fivetran connector for Product Hunt data extraction",
    author="IdeaGen Team",
    author_email="team@ideagen.ai",
    packages=find_packages(),
    install_requires=[
        "fivetran-client>=1.0.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "asyncio>=3.4.3",
        "aiohttp>=3.8.5",
        "backoff>=2.2.1",
        "tenacity>=8.2.3",
        "python-dateutil>=2.8.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.1",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ]
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    entry_points={
        "console_scripts": [
            "producthunt-connector=producthunt_connector.main:main",
        ],
    },
)