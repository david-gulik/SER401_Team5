"""Fixture autograder that blows up before writing any results."""

import sys

print("compiling...", flush=True)
sys.stderr.write("boom: the compiler exploded\n")
sys.exit(3)
