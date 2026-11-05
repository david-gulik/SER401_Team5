"""
Shoggoth - A Gradescope compatible tool for performing automatic assessment of Java homework, using static and
dynamic analysis.
"""
__author__ = "Ruben Acuna"

import json


class GradescopeResult:
    """
    A wrapper for a Gradescope result file that provides common operations.
    """

    def __init__(self, filepath=None):
        if filepath is None:
            self.results = {"execution_time": 1, "stdout_visibility": "visible", "tests": []}
            self.add_note("Shoggoth Internal", "ERROR: used uninitialized results file.")
        else:
            self.load(filepath)

    def load(self, filepath):
        with open(filepath) as infile:
            self.results = json.load(infile)

    def save(self, filepath):
        with open(filepath, 'w') as outfile:
            json.dump(self.results, outfile)

    def add_case(self, name, number, score, max_score, output, force_failed=False):
        new_entry = {'name': name,
                     'number': number,
                     'score': score,
                     'max_score': max_score,
                     'visibility': 'visible',
                     'output': output}

        if force_failed:
            new_entry["status"] = "failed"

        self.results["tests"].append(new_entry)

    def add_note(self, name, output, force_failed=False):
        self.add_case(name, "0", 0.0, 0.0, output, force_failed)

    def zero_all(self):
        for test in self.results["tests"]:
            test["score"] = 0.0
            test["output"] = ""

    def zero_by_keyword(self, keyword, output, append=False):
        for test in self.results["tests"]:
            if keyword in test["name"]:
                test["score"] = 0.0
                if append:
                    test["output"] += "\n" + output
                else:
                    test["output"] = output

    def set_result_buildfail(self):
        self.results = {"execution_time": 1,
                   "stdout_visibility": "visible",
                   "tests": [{"name": "Compilation",
                              "number": "",
                              "score": 0.0,
                              "max_score": 0.0,
                              "visibility": "visible",
                              "output": "Could not compile submission.\n"}]}

    def set_result_filemissing(self):
        self.results = {"execution_time": 1,
                   "stdout_visibility": "visible",
                   "tests": [{"name": "Upload File",
                              "number": "",
                              "score": 0.0,
                              "max_score": 0.0,
                              "visibility": "visible",
                              "output": "Could not find expected file(s).\n"}]}