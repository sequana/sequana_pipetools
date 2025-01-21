#
#  This file is part of Sequana software
#
#  Copyright (c) 2016-2021 - Sequana Dev Team (https://sequana.readthedocs.io)
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  Website:       https://github.com/sequana/sequana
#  Documentation: http://sequana.readthedocs.io
#  Contributors:  https://github.com/sequana/sequana/graphs/contributors
##############################################################################
import hashlib
import os
import sys
import tarfile

import colorlog
import requests
from tqdm import tqdm

from sequana_pipetools import get_package_version

logger = colorlog.getLogger(__name__)


__all__ = ["Colors", "print_version", "error", "url2hash", "levenshtein_distance", "download_and_extract_tar_gz"]


def download_and_extract_tar_gz(url, extract_to):
    """
    Downloads a .tar.gz file from a given URL and extracts it to the specified directory.

    :param url: URL of the .tar.gz file
    :param extract_to: Directory where the contents will be extracted
    """
    # Get the file name from the URL
    filename = url.split("/")[-1]
    file_path = os.path.join(extract_to, filename)

    # create the directory
    os.makedirs(extract_to, exist_ok=True)

    # Download the file
    logger.info(f"Downloaded {filename} to {file_path}")
    response = requests.get(url, stream=True)
    response.raise_for_status()  # Raise an exception for HTTP errors
    total_size = int(response.headers.get("content-length", 0))

    # Write the downloaded content to a file
    # Download with a progress bar
    with open(file_path, "wb") as file, tqdm(
        desc=f"Downloading {filename}",
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)
            bar.update(len(chunk))

    # Extract the tar.gz file
    if tarfile.is_tarfile(file_path):
        with tarfile.open(file_path, "r:gz") as tar:
            tar.extractall(path=extract_to)
    else:
        logger.warning(f"{file_path} is not a valid tar.gz file.")

    # Optionally, you can delete the .tar.gz file after extraction
    os.remove(file_path)


def levenshtein_distance(token1: str, token2: str) -> int:
    """Computes the Levenshtein distance between two strings using dynamic programming.

    The Levenshtein distance is a measure of the minimum number of single-character edits
    (insertions, deletions, or substitutions) required to change one word into the other.

    :param str token1: The first input string.
    :param str token2: The second input string.
    :return: Levenshtein distance between the two input strings.

    Example::

        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("flaw", "lawn")
        2

    Notes:
    - The function uses a 2D list to store the distances, which requires O(m * n) space,
      where m and n are the lengths of the input strings.
    - The time complexity is O(m * n) since each cell of the matrix is filled once.

    """
    len1, len2 = len(token1), len(token2)

    # Initialize the matrix with zeros
    distances = [[0 for _ in range(len2 + 1)] for _ in range(len1 + 1)]

    # Fill the first row and column
    for t1 in range(len1 + 1):
        distances[t1][0] = t1

    for t2 in range(len2 + 1):
        distances[0][t2] = t2

    # Compute the Levenshtein distance
    for t1 in range(1, len1 + 1):
        for t2 in range(1, len2 + 1):
            if token1[t1 - 1] == token2[t2 - 1]:
                distances[t1][t2] = distances[t1 - 1][t2 - 1]
            else:
                distances[t1][t2] = (
                    min(
                        distances[t1][t2 - 1],  # Insertion
                        distances[t1 - 1][t2],  # Deletion
                        distances[t1 - 1][t2 - 1],  # Substitution
                    )
                    + 1
                )

    return distances[len1][len2]


def get_url_file_size(url):
    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code == 200 and "Content-Length" in response.headers:
            return int(response.headers["Content-Length"])
        else:
            logger.warning(f"Unable to retrieve file size from {url}. Status code:", response.status_code)
            return 0
    except requests.RequestException as e:
        logger.warning(f"Unable to retrieve file size from {url}:", e)
        return 0


def url2hash(url):
    md5hash = hashlib.md5()
    md5hash.update(url.encode())
    return md5hash.hexdigest()


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Colors:
    """

    ::

        color = Colors()
        print(color.failed("msg"))

    """

    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    def failed(self, msg):
        return self.FAIL + msg + self.ENDC

    def bold(self, msg):
        return self.BOLD + msg + self.ENDC

    def purple(self, msg):
        return self.PURPLE + msg + self.ENDC

    def underlined(self, msg):
        return self.UNDERLINE + msg + self.ENDC

    def fail(self, msg):
        return self.FAIL + msg + self.ENDC

    def error(self, msg):
        return self.FAIL + msg + self.ENDC

    def warning(self, msg):
        return self.WARNING + msg + self.ENDC

    def green(self, msg):
        return self.GREEN + msg + self.ENDC

    def blue(self, msg):
        return self.BLUE + msg + self.ENDC


def error(msg, pipeline):
    color = Colors()
    print(color.error("ERROR [sequana.{}]::".format(pipeline) + msg), flush=True)
    sys.exit(1)


def print_version(name):
    try:
        ver = get_package_version(f"sequana_{name}")
        print(f"sequana_{name} version: {ver}")
    except Exception as err:  # pragma: no cover
        print(err)
        print(f"sequana_{name} version: ?")

    try:
        version = get_package_version("sequana")
        print(f"Sequana version: {version}")
    except Exception:  # pragma: no cover
        print(f"Sequana version: not found")

    try:
        version = get_package_version("sequana_pipetools")
        print(f"Sequana_pipetools version: {version}")
    except Exception as err:  # pragma: no cover
        print(err)
        print("Sequana_pipetools version: not found")

    print(Colors().purple("\nHow to help ?\n- Please, consider citing us (see sequana.readthedocs.io)"))
    print(Colors().purple("- Contribute to the code or documentation"))
    print(Colors().purple("- Fill issues on https://github.com/sequana/sequana/issues/new/choose"))
    print(Colors().purple("- Star us https://github.com/sequana/sequana/stargazers"))


class PipetoolsException(Exception):
    pass
