from setuptools import setup, find_packages

setup(
    name="agent_analytics",
    version="0.6.1",
    author="Muhammad Kanaan",
    author_email="Muhammad.kanaan@ibm.com",
    description="Agent Analytics observability SDK package",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url="https://github.ibm.com/agent-analytics/sdk",
    package_dir={"": "src"},
    packages=find_packages(where="src", include=["agent_analytics*"]),
    install_requires=[
        "agent-analytics-common @ file://../common",
        "traceloop-sdk>=0.47.5,<0.49.0",
        "opentelemetry-instrumentation-fastapi>=0.50b0",
        "pydantic>=2.8.2",
        "python-dotenv",
        "botocore",
        "packaging",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    python_requires='>=3.10,<3.14',
)
