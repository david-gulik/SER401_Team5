import preparation


def test_simple_line_comment():
    expected = "int x = 1; \nint y = 2;\n"
    src = "int x = 1; // set x\nint y = 2;\n"
    result = preparation.strip_gradescope_comments(src)
    assert result == expected


def test_no_comment():
    src = "int x = 1; \nint y = 2;\n"
    result = preparation.strip_gradescope_comments(src)
    assert result == src


def test_single_line_block_comment():
    src = "int x = 1; /* block comment */ int y = 2;\n"
    expected = "int x = 1;  int y = 2;\n"
    result = preparation.strip_gradescope_comments(src)
    assert result == expected


def test_multi_line_block_comment():
    src = "int x = 1; /* block comment \n \n with several lines */ int y = 2;\n"
    expected = "int x = 1; \n\n int y = 2;\n"
    result = preparation.strip_gradescope_comments(src)
    assert result == expected


def test_string_comment():
    src = 'String x = "//not a comment"'
    result = preparation.strip_gradescope_comments(src)
    assert result == src


def test_comment_markers_inside_char_literal():
    src = "char c = '/'; char d = '*'; // this is a real comment\n"
    expected = "char c = '/'; char d = '*'; \n"
    result = preparation.strip_gradescope_comments(src)
    assert result == expected


def test_sloppy_comment_markers():
    src = "int x = 1;/////////// comment\nint y = 2;/*/*/\nint z = 3;//comment\n"
    expected = "int x = 1;\nint y = 2;\nint z = 3;\n"
    result = preparation.strip_gradescope_comments(src)
    assert result == expected


def test_acuna_exception():
    src = "/* blah blah */int x = 1;"
    expected = "int x = 1;"
    result = preparation.strip_gradescope_comments(src)
    print(result)
    assert result == expected


# def test_bulk_comment_strip():
#     with zipfile.ZipFile('data_original/submissions/Module 2 Programming.zip', 'r') as gradescope_zip:
#         gradescope_zip.extractall('data_original/submissions/')
#     with zipfile.ZipFile('data_original/submissions/Module 3 Programming.zip', 'r') as gradescope_zip:
#         gradescope_zip.extractall('data_original/submissions/')
#     preparation.anonymize_gradescope_submissions('data_original/submissions/', 'data_processed/submissions/')
