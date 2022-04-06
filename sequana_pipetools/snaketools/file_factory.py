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
import glob
import os
import re
import sys

import colorlog

logger = colorlog.getLogger(__name__)


class FileFactory:
    """Factory to handle a set of files

    ::

        from sequana.snaketools import FileFactory
        ff = FileFactory("H*.gz")
        ff.filenames

    A set of useful methods are available based on this convention::

        >>> fullpath = /home/user/test/A.fastq.gz
        >>> dirname(fullpath)
        '/home/user/test'
        >>> basename(fullpath)
        'A.fastq.gz'
        >>> realpath(fullpath) # is .., expanded to /home/user/test

        >>> all_extensions
        "fastq.gz"
        >>> extensions
        ".gz"

    FIXME: pathname to be checked.

    A **basename** is the name of a directory in a Unix pathname that occurs
    after the last slash.

    dirname, returns everything but the final basename in a pathname. Both


    The **pathname** is a specific label for a file’s directory location
    while within an operating system.

    .. versionchanged:: 0.8.7 attributes were recomputed at each accession. For
        small projects, this is transparent, but on novogene or large set of samples,
        this is taking too much time. This was done in case FileFactorry
        attributes such as input directorty or pattern are changed. In practice this
        does not happen, so we can write the basenames and other attributes in variables
        once for all

    """

    def __init__(self, pattern):
        """.. rubric:: Constructor

        :param pattern: can be a filename, list of filenames, or a global
            pattern (a unix regular expression with wildcards). For instance,
            ``*/*fastq.gz``

        .. warning:: Only in Python 3.X supports the recursive global pattern
            for now.

        """
        self.pattern = pattern
        try:
            if os.path.exists(pattern):
                self._glob = [pattern]
            else:
                self._glob = glob.glob(pattern, recursive=True)
        except TypeError:
            # Error if pattern is a list of file
            for filename in pattern:
                if not os.path.exists(filename):
                    raise FileNotFoundError(f"This file {filename} does not exist")
            self._glob = pattern[:]

        self.realpaths = [os.path.realpath(filename) for filename in self._glob]
        self.basenames = [os.path.split(filename)[1] for filename in self._glob]
        self.filenames = [basename.split(".")[0] for basename in self.basenames]
        self.pathnames = [os.path.split(filename)[0] for filename in self.realpaths]
        self.extensions = [os.path.splitext(filename)[1] for filename in self._glob]
        self.all_extensions = [basename.split(".", 1)[1] if "." in basename else "" for basename in self.basenames]

    def _pathname(self):
        pathname = set(self.pathnames)
        if len(pathname) == 1:
            return list(pathname)[0] + os.sep
        else:
            raise ValueError("found more than one pathname")

    pathname = property(_pathname, doc="the common relative path")

    def __len__(self):
        return len(self.filenames)

    def __str__(self):
        return "Found %s file(s)" % len(self)


class FastQFactory(FileFactory):
    """FastQ Factory tool

    In NGS experiments, reads are stored in a so-called FastQ file. The file is
    named::

        PREFIX_R1_SUFFIX.fastq.gz

    where _R1_ tag is always to be found. This is a single-ended case. In
    paired case, a second file is to be found::

        PREFIX_R2_SUFFIX.fastq.gz

    The PREFIX indicates the sample name. The SUFFIX does not convey any
    information per se. The default read tag ("_R[12]_") handle this case.


    The following commands expect to find data with a readtag _R1_ or _R2_::

        FastQFactory("*fastq.gz")

    This behaviour can be changed if data have another read tags. (e.g. "[12].fastq.gz")

        FastQFactory("*fastq.gz", read_tag="_[12].")

    Sometimes, e.g. in long reads experiments (for instance), naming convention is
    different and may nor be single/paired end convention. If so, set the
    readtag to None.

        FastQFactory("*ccs.fastq.gz", read_tag=None)

    In a directory (recursively or not), there could be lots of samples. This
    class can be used to get all the sample prefix in the :attr:`tags`
    attribute.

    Given a tag, one can get the corresponding file(s)::

        ff = FastQFactory("*fastq.gz")
        ff.tags
        ff.get_file1(ff.tags[0])
        len(ff)

    """

    def __init__(self, pattern, extension=["fq.gz", "fastq.gz"], read_tag="_R[12]_", verbose=False, paired=True):
        r""".. rubric:: Constructor

        :param str pattern: a global pattern (e.g., ``H*fastq.gz``)
        :param list extension: not used
        :param str read_tag: regex tag used to join paired end files. Some
            characters need to be escaped with a \ character to be interpreted as
            character. (e.g. '_R[12]_\.fastq\.gz')
        :param bool verbose:
        """
        super(FastQFactory, self).__init__(pattern)

        self.read_tag = read_tag
        # Filter out reads that do not have the read_tag
        # https://github.com/sequana/sequana/issues/480
        if self.read_tag is None or self.read_tag.strip() == "":
            self.read_tag = ""

        if self.read_tag:
            logger.info(f"readtag: {self.read_tag}")
        else:
            logger.info("No readtag provided.")

        if self.read_tag:
            remaining = [filename for filename in self._glob if re.search(self.read_tag, os.path.basename(filename))]
            if len(remaining) < len(self._glob):
                diff = len(self._glob) - len(remaining)
                logger.warning(
                    "Filtered out {} files that match the pattern but do not contain the read_tag ({})".format(
                        diff, self.read_tag
                    )
                )
            self._glob = remaining

        # check if tag is informative
        if self.read_tag != "":
            if "[12]" not in self.read_tag:
                msg = "the read_tag parameter must contain '[12]' to differentiate read 1 and 2."
                logger.error(msg)
                raise ValueError(msg)
            elif self.read_tag == "[12]":
                msg = "The read_tag parameter must be more informative than just have [12]"
                logger.error(msg)
                raise ValueError(msg)

            if len(self.filenames) == 0:
                msg = "No files found with the requested pattern ({}) and readtag ({})"
                msg = msg.format(pattern, self.read_tag)
                logger.error(msg)
                raise ValueError(msg)

        # save pattern and read tag
        self.pattern = pattern

        # If a user uses a . it should be taken into account hence the regex
        # that follows
        if self.read_tag:
            re_read_tag = re.compile(self.read_tag.replace(r".", r"\."))
            self.tags = list({re_read_tag.split(f)[0] for f in self.basenames})
        else:
            self.tags = list({f.split(".")[0] for f in self.basenames})

        self.short_tags = [x.split("_")[0] for x in self.tags]
        if len(self.tags) == 0:
            msg = "No sample found. Tag '{0}' is not relevant".format(self.read_tag)
            logger.error(msg)
            raise ValueError(msg)

        logger.info("Found %s projects/samples " % len(self.tags))

    def _get_file(self, tag, r):
        if tag is None:
            if len(self.tags) == 1:
                tag = self.tags[0]
            elif len(self.tags) > 1:
                raise ValueError("Ambiguous tag. You must provide one " "(sequana.FastQFactory)")
        else:
            assert tag in self.tags, "invalid tag"

        # retrieve file of tag
        if self.read_tag:
            read_tag = self.read_tag.replace("[12]", r)

            # changed in v0.8.7 tricky hanbling of sample names
            # https://github.com/sequana/sequana/issues/576
            candidates = [
                realpath
                for basename, realpath in zip(self.basenames, self.realpaths)
                if read_tag in basename and tag == basename.split(read_tag)[0]
            ]
        else:
            read_tag = ""
            candidates = [
                realpath for basename, realpath in zip(self.basenames, self.realpaths) if basename.startswith(tag)
            ]

        if len(candidates) == 0 and r == "2":
            # assuming there is no R2
            return None
        elif len(candidates) == 1:
            return candidates[0]
        elif len(candidates) == 0:
            msg = "Found no valid matches for {}. "
            msg += "Files must have the tag ({}) and an underscore somewhere"
            msg = msg.format(tag, read_tag)
            logger.critical(msg)
            raise Exception
        else:
            logger.critical("Found too many candidates: %s " % candidates)
            msg = "Found too many candidates or identical names: %s " % candidates
            msg += "Files must have the tag %s" % read_tag
            raise ValueError(msg)

    def get_file1(self, tag=None):
        return self._get_file(tag, "1")

    def get_file2(self, tag=None):
        return self._get_file(tag, "2")

    def _get_paired(self):

        # If there is no read_tag, this means data is unpaired
        if self.read_tag == "":
            return False

        # change [12] regex
        rt1 = self.read_tag.replace("[12]", "1")
        rt2 = self.read_tag.replace("[12]", "2")

        # count number of occurences
        # Note1: the filenames do not have the extension and therefore the final "."
        # Note2: the tag _1 and _2 may be used at the end of the filename.
        #        and are not robust enough. Indeed, sample names may contain the
        #        _1 or _2 strings. Yet, usually, if used, the _1 and _2 are at
        #        the end of the filename. Thereofre the read "1." and "_2." can
        #        be used robustly.
        # Given Note1 and Note2, we decided to count the R1 and R2 tag by
        # appending the "." in the variable 'this' so that if used in the
        # read_tag it can be match
        R1 = [1 for this in self.filenames if rt1 in this + "."]
        R2 = [1 for this in self.filenames if rt2 in this + "."]

        if len(R2) == 0:
            return False
        elif R1 == R2:
            return True
        else:
            logger.error("Mix of paired and single-end data sets {}".format(self.pattern))
            sys.exit(1)

    paired = property(_get_paired, doc="guess whether data is paired or not")

    def __len__(self):
        return len(self.tags)
