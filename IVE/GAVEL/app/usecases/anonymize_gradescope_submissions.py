from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

def strip_gradescope_comments(assignment_in: str) -> str:
    """
    Method for taking in a C or Java file and stripping it of comments for privacy purposes

    :param assignment_in: string representation of assignment, to be stripped of comments
    :return: that same assignment but without comments
    """

    # instantiate some stuff; an output string, a counter, the length of the original string, a "normal" state,
    # and a blocker for following quotes

    out = []
    i = 0
    n = len(assignment_in)
    state = "normal"
    quote_char = None

    # go through string and set state based on a combination of present state and incoming characters

    while i < n:
        # set pointers
        c = assignment_in[i]
        nxt = assignment_in[i + 1] if i + 1 < n else ""

        # if "normal" state (that is, in a state of parsing code)
        if state == "normal":
            # if "//" detected, change state to line_comment and bypass the "//"
            if c == "/" and nxt == "/":
                state = "line_comment"
                i += 2
                continue
            # if "/*" detected, change state to block_comment and bypass the "/*"
            if c == "/" and nxt == "*":
                state = "block_comment"
                i += 2
                continue
            # if apostrophes detected, change state to "string" and add to output
            if c in ('"', "'"):
                state = "string"
                quote_char = c
                out.append(c)
                i += 1
                continue
            # finally, append output with current character and move on
            out.append(c)
            i += 1

        # escape condition for line_comment
        elif state == "line_comment":
            if c == "\n":
                state = "normal"
                out.append(c)
            i += 1

        # escape condition for block_comment
        elif state == "block_comment":
            # add line spaces if newlines appear in block comment
            if c == "\n":
                out.append("\n")
                i += 1
                continue
            if c == "*" and nxt == "/":
                state = "normal"
                i += 2
            else:
                i += 1

        # escape condition for string
        elif state == "string":
            out.append(c)
            if c == "\\":  # escape next char
                if i + 1 < n:
                    out.append(assignment_in[i + 1])
                    i += 2
                else:
                    i += 1
            elif c == quote_char:
                state = "normal"
                i += 1
            else:
                i += 1

    # return output without comments!
    return "".join(out)


# REFACTORED TO INCLUDE PROCESSED AND SKIPPED COUNTS

# def anonymize_gradescope_submissions(input_folder: str, output_folder: str):
#     """
#     Method for scanning input_folder for Java/C files, stripping out comments, and writing anonymized
#     versions to output_folder with '_anon' suffixes.
#     """
#     input_folder = Path(input_folder)
#     output_folder = Path(output_folder)
#
#     # Create output folder if it doesn't exist
#     output_folder.mkdir(parents=True, exist_ok=True)
#
#     file_extensions = {".java", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp"}
#
#     if not input_folder.exists():
#         raise FileNotFoundError(f"Input folder does not exist: {input_folder}")
#
#     # for each file, if either the file is NOT a file (that is, a folder, shortcut, etc.), OR if the file is
#     # not a Java or C/C++ file, skip it
#     for path in input_folder.rglob("*"):
#         if not path.is_file():
#             continue
#         if path.suffix.lower() not in file_extensions:
#             continue
#
#         # Read text from file
#         try:
#             text = path.read_text(encoding="utf-8")
#         except UnicodeDecodeError:
#             text = path.read_text(encoding="latin-1")
#
#         # Strip comments
#         cleaned = strip_gradescope_comments(text)
#
#         # Add _anon suffix to filename, create output path using provided folder
#         rel = path.relative_to(input_folder)
#         anon_name = rel.with_name(rel.stem + "_anon" + rel.suffix)
#         out_path = output_folder / anon_name
#
#         # Ensure directory exists
#         out_path.parent.mkdir(parents=True, exist_ok=True)
#
#         # Write anonymized file
#         out_path.write_text(cleaned, encoding="utf-8")
#
#         print(f"Gradescope Submissions Processed: {path} -> {out_path}")
#


@dataclass(frozen=True)
class AnonymizeGradescopeSubmissionsRequest:
    """
    Request object for anonymizing Gradescope submissions.
    """
    input_folder: str
    output_folder: str


@dataclass(frozen=True)
class AnonymizeGradescopeSubmissionsResult:
    """
    Result object containing counts of processed/skipped files and output folder location.
    """
    processed_count: int
    skipped_count: int
    output_folder: str


class AnonymizeGradescopeSubmissionsUseCase:
    """
    Use case for anonymizing Gradescope submissions
    """

    def execute(self, request: AnonymizeGradescopeSubmissionsRequest) -> AnonymizeGradescopeSubmissionsResult:
        input_path = Path(request.input_folder)
        output_path = Path(request.output_folder)

        if not input_path.exists():
            raise FileNotFoundError(f"Input folder does not exist: {input_path}")

        file_extensions = {".java", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp"}

        processed_count = 0
        skipped_count = 0

        for path in input_path.rglob("*"):
            if not path.is_file():
                skipped_count += 1
                continue
            if path.suffix.lower() not in file_extensions:
                skipped_count += 1
                continue

            # Read file
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="latin-1")

            cleaned = strip_gradescope_comments(text)

            # Build output path
            rel = path.relative_to(input_path)
            anon_name = rel.with_name(rel.stem + "_anon" + rel.suffix)
            out_path = output_path / anon_name

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(cleaned, encoding="utf-8")

            processed_count += 1

        return AnonymizeGradescopeSubmissionsResult(
            processed_count=processed_count,
            skipped_count=skipped_count,
            output_folder=str(output_path)
        )
