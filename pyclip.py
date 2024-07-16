import os
import sys
import subprocess
import re
import logging

from argparse import ArgumentParser


logger = logging.getLogger(__name__)


# Used to validate timestamps for ffmpeg
TIMESTAMP_PATTERN = re.compile(r"""(?x)
                               ^-? # Optional minus sign
                               (?:(?:[0-9]+:)?[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?) # [HH:]MM:SS[.m...]
                               | (?:^-?[0-9]+(?:(?:\.[0-9]+)|(?:[mu]?s))?) # S+[.m...][s|ms|us]
                               $
                               """)

# Usee to extract filenames and file extensions
FILENAME_PATTERN = re.compile(r"""(?x)
                              (?P<name>^.*) # name
                              \. # dot
                              (?P<extension>.*$) # extension
                              """)


class Formatter(logging.Formatter):
    """Basic formatter subclass that adds color"""

    GREY = "\x1b[38;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    RED_BOLD = "\x1b[31;1m"
    BLUE = "\x1b[34;20m"
    RESET = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: BLUE,
        logging.INFO: GREY,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED_BOLD
    }

    def format(self, record):
        return self.FORMATS[record.levelno] + super().format(record) + self.RESET


def _init_logger(level : int):
    """
    Initialize the module logger for CLI

    Args:
        level (int): Level of verbosity between 0 and 2 (inclusive)
                     Maps in order to WARNING, INFO, DEBUG
                     Integers > 2 behave identically to 2

    Raises:
        ValueError: If a negative number was provided
    """
    if level == 0:
        logger.setLevel(logging.WARNING)
    elif level == 1:
        logger.setLevel(logging.INFO)
    elif level >= 2:
        logger.setLevel(logging.DEBUG)
    else:
        raise ValueError(f"{level} is not a valid verbosity level")
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)
    handler.setFormatter(Formatter("%(message)s"))
    logger.addHandler(handler)


def clip(infile : os.PathLike | str,
         outfile : os.PathLike | str,
         start_timestamp : str,
         end_timestamp : str,
         no_audio : bool = False,
         no_video : bool = False,
         overwrite : bool = False,
         copy : bool = False):
    """
    Invokes FFMPEG to extract a video clip between the specified timestamps.

    Args:
        infile (os.PathLike): The source video stream
        outfile (os.PathLike): The output video file
        start_timestamp (str): Clip start time in FFMPEG timestamp format
        end_timestamp (str): Clip end time in FFMPEG timestamp format
        no_audio (bool, optional): Do not copy the audio streams to the output. Defaults to False.
        no_video (bool, optional): Do not copy the video streams to the output. Defaults to False.
        overwrite (bool, optional): Overwrite already existing files. Defaults to False.
        copy (bool, optional): Perform a simple copy and do not transcode. Defaults to False.
    """
    command = ["ffmpeg", "-loglevel", "fatal", "-i", infile, "-ss", start_timestamp, "-to", end_timestamp]
    if copy:
        command.append( "-c")
        command.append("copy")
    if no_audio:
        command.append("-an")
    if no_video:
        command.append("-vn")
    if overwrite:
        command.append("-y")
    else:
        command.append("-n")
    command.append(outfile)
    subprocess.run(command, check = True)


def main():
    """Main function"""
    clparser = ArgumentParser("pyclip")
    clparser.add_argument("-v", "--verbose",
                          action = "count",
                          default = 0,
                          help = "Increase the verbosity (up to two times)")
    clparser.add_argument("-i", "--infile",
                          required = True,
                          help = "Path to the input file to extract clips from")
    clparser.add_argument("-o", "--outfile",
                          help = "Path to store the extracted clips, can be a file or a directory")
    clparser.add_argument("--noaudio",
                          action = "store_true",
                          help = "Do not copy audio in the extracted clips")
    clparser.add_argument("--novideo",
                          action = "store_true",
                          help = "Do not copy video in the extracted clips")
    clparser.add_argument("--overwrite",
                          action = "store_true",
                          help = "Overwrite existing output files, defaults to no")
    clparser.add_argument("--copy",
                          action = "store_true",
                          help = "Perform a simple copy and do not transcode")
    clparser.add_argument("timestamps",
                          nargs = "*",
                          help = "Start and end timestamps of the clips to extract, \
                                  must go in pairs : start1 end1 [start2 end2 ...]")
    args = clparser.parse_args()

    _init_logger(args.verbose)

    if len(args.timestamps) < 2 or len(args.timestamps) % 2 != 0:
        clparser.error(f"Mismatched number of timestamps : {len(args.timestamps)}")

    arg_timestamps = iter(args.timestamps)
    timestamps = zip(arg_timestamps, arg_timestamps)

    clip_nb = 1
    clip_total = len(args.timestamps) // 2

    infile = args.infile

    logger.debug("Input file : %s", infile)

    if args.outfile is None or os.path.isdir(args.outfile):
        infile_match = FILENAME_PATTERN.match(os.path.basename(infile))
        if infile_match is None:
            clparser.error("Output file name could not be generated from input file")
        outfile_name = infile_match.group("name") + "_clip"
        if args.outfile is not None:
            outfile_name = os.path.join(args.outfile, outfile_name)
        outfile_ext = infile_match.group("extension")
    else:
        outfile_match = FILENAME_PATTERN.match(os.path.basename(args.outfile))
        if outfile_match is None:
            clparser.error("Output file name could not be parsed")
        outfile_name = os.path.join(os.path.dirname(args.outfile), outfile_match.group("name"))
        outfile_ext = outfile_match.group("extension")

    if args.noaudio and args.novideo:
        logger.warning("The output stream will be empty")

    for start, end in timestamps:
        logger.info("Extracting clip %s of %s", clip_nb, clip_total)
        logger.debug("Clip timestamps : %s - %s", start, end)
        if clip_total > 1:
            outfile = outfile_name + f"_{clip_nb:02}." + outfile_ext
        else:
            outfile = outfile_name + "." + outfile_ext
        logger.debug("Extracting to : %s", outfile)
        clip_nb += 1
        clip(infile, outfile, start, end, args.noaudio, args.novideo, args.overwrite, args.copy)


if __name__ == "__main__":
    raise SystemExit(main())
