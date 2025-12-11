from setuptools import setup, find_packages

setup(
    name='agent-analytics-common',
    version='0.1.6',
    packages=find_packages(where="src", include=["agent_analytics_common*"]),
    package_dir={'': 'src'},
    install_requires=[        
        "pydantic>=2.0.0,<3.0.0",
    ],
)
