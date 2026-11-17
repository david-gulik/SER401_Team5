"""Fixture autograder that never finishes, standing in for a student's infinite loop."""

import time

print("working...", flush=True)
time.sleep(300)
