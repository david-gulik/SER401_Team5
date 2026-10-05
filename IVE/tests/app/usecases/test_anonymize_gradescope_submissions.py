from pathlib import Path

from GAVEL.app.usecases.anonymize_gradescope_submissions import (
    AnonymizeGradescopeSubmissionsRequest,
    AnonymizeGradescopeSubmissionsUseCase,
    strip_gradescope_comments,
)


def test_strip_gradescope_comments_basic():
    src = """
    int x = 0; // this is a comment
    /* block comment */
    int y = 1;
    """
    cleaned = strip_gradescope_comments(src)

    assert "//" not in cleaned
    assert "block comment" not in cleaned
    assert "int x = 0;" in cleaned
    assert "int y = 1;" in cleaned


def test_strip_gradescope_comments_preserves_strings():
    src = r"""
    char *s = "/* not a comment */";
    char *t = "// also not a comment";
    """
    cleaned = strip_gradescope_comments(src)

    assert "/* not a comment */" in cleaned
    assert "// also not a comment" in cleaned


def test_usecase_processes_valid_files(tmp_path):
    # Arrange
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    valid_file = input_dir / "test.java"
    valid_file.write_text("int x = 0; // remove me\n")

    request = AnonymizeGradescopeSubmissionsRequest(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
    )

    usecase = AnonymizeGradescopeSubmissionsUseCase()

    # Act
    result = usecase.execute(request)

    # Assert
    assert result.processed_count == 1
    assert result.skipped_count == 0

    out_file = output_dir / "test_anon.java"
    assert out_file.exists()
    assert "//" not in out_file.read_text()


def test_usecase_skips_non_code_files(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    (input_dir / "notes.txt").write_text("hello world")
    (input_dir / "image.png").write_text("binarydata")

    request = AnonymizeGradescopeSubmissionsRequest(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
    )

    usecase = AnonymizeGradescopeSubmissionsUseCase()
    result = usecase.execute(request)

    assert result.processed_count == 0
    assert result.skipped_count == 2
    assert Path(result.output_folder).exists()


def test_usecase_recurses_directories(tmp_path):
    input_dir = tmp_path / "input"
    nested = input_dir / "nested"
    output_dir = tmp_path / "output"

    nested.mkdir(parents=True)

    file1 = nested / "a.cpp"
    file1.write_text("int x; // comment")

    request = AnonymizeGradescopeSubmissionsRequest(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
    )

    usecase = AnonymizeGradescopeSubmissionsUseCase()
    result = usecase.execute(request)

    assert result.processed_count == 1

    out_file = output_dir / "nested" / "a_anon.cpp"
    assert out_file.exists()
    assert "//" not in out_file.read_text()


def test_usecase_handles_encoding_fallback(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    # Write Latin-1 encoded file
    file = input_dir / "latin.c"
    file.write_bytes("int x = 0; // áéíóú".encode("latin-1"))

    request = AnonymizeGradescopeSubmissionsRequest(
        input_folder=str(input_dir),
        output_folder=str(output_dir),
    )

    usecase = AnonymizeGradescopeSubmissionsUseCase()
    result = usecase.execute(request)

    assert result.processed_count == 1

    out_file = output_dir / "latin_anon.c"
    assert out_file.exists()
    assert "//" not in out_file.read_text()
