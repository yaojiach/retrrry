from setuptools import setup


VERSION = "2.0.0"
CLASSIFIERS = [
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
]

with open("README.md") as f:
    readme = f.read()

setup(
    name="retrrry",
    version=VERSION,
    description="Retry for Python3. No dependency.",
    long_description_content_type="text/markdown",
    long_description=readme,
    author="Jiachen Yao",
    license="Apache 2.0",
    url="https://github.com/yaojiach/retrrry",
    classifiers=CLASSIFIERS,
    py_modules=["retrrry"],
)
