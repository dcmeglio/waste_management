import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="waste_management",
    version="1.1",
    author="Dominick Meglio",
    license="MIT",
    author_email="dmeglio@gmail.com",
    description="Provides ability to query the Waste Management REST API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dcmeglio/waste_management",
    packages=setuptools.find_packages(),
    install_requires=["requests", "pyjwt"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
