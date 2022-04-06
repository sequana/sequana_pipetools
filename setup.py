from setuptools import setup, find_packages


_MAJOR = 0
_MINOR = 8
_MICRO = 0
version = f"{_MAJOR}.{_MINOR}.{_MICRO}"
release = f"{_MAJOR}.{_MINOR}"

metainfo = {
    "authors": {"main": ("thomas cokelaer", "thomas.cokelaer@pasteur.fr")},
    "version": version,
    "license": "new BSD",
    "url": "https://github.com/sequana/sequana_pipetools",
    "description": "A set of tools to help building or using Sequana pipelines",
    "platforms": ["Linux", "Unix", "MacOsX", "Windows"],
    "keywords": ["snakemake, sequana, pipelines"],
    "classifiers": [
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Education",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Mathematics",
        "Topic :: Scientific/Engineering :: Physics",
    ],
}


setup(
    name="sequana_pipetools",
    version=version,
    maintainer=metainfo["authors"]["main"][0],
    maintainer_email=metainfo["authors"]["main"][1],
    author=metainfo["authors"]["main"][0],
    author_email=metainfo["authors"]["main"][1],
    long_description=open("README.rst").read(),
    keywords=metainfo["keywords"],
    description=metainfo["description"],
    license=metainfo["license"],
    platforms=metainfo["platforms"],
    url=metainfo["url"],
    classifiers=metainfo["classifiers"],
    # package installation
    packages=find_packages(exclude=["tests*"]),
    install_requires=open("requirements.txt").read(),
    tests_require=["pytest", "coverage", "pytest-cov"],
    # This is recursive include of data files
    exclude_package_data={"": ["__pycache__"]},
    package_data={
        "": ["*.yaml", "*.rules", "*.json", "requirements.txt", "*png", "fastq_screen.conf"],
    },
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "sequana_completion=sequana_pipetools.completion:main",
            "sequana_slurm_status=sequana_pipetools.slurm:main",
        ]
    },
)
