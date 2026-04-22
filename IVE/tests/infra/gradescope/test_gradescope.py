from unittest.mock import MagicMock, patch

from IVE.GAVEL.app.ports.gradescope_client import GradescopeClient, GradescopeSession

# testing extracting Gradescope courseID from URL


def test_extract_gradescope_course_id():
    client = GradescopeClient("https://canvas.asu.edu/courses/123567")
    client._driver = MagicMock()
    client._driver.current_url = "https://www.gradescope.com/courses/987654/assignments"

    course_id = client._extract_gradescope_course_id()

    assert course_id == "987654"


# testing Selenium grabbing the correct cookies


def test_extract_session():
    client = GradescopeClient("dummy")
    client._driver = MagicMock()
    client._driver.get_cookies.return_value = [
        {"name": "_gradescope_session", "value": "123456"},
        {"name": "token", "value": "987654"},
    ]

    session = client._extract_session()

    assert session.session_cookie == "123456"
    assert session.token == "987654"
    assert session.all_cookies["_gradescope_session"] == "123456"


# Mock Gradescope session, checking cookies and session headers


def test_build_requests_session():
    client = GradescopeClient("dummy")
    gs = GradescopeSession(
        session_cookie="123456",
        token="csrf123",
        all_cookies={"_gradescope_session": "123456", "token": "csrf123"},
    )

    session = client._build_requests_session(gs, course_id=42)

    assert session.cookies.get("_gradescope_session") == "123456"
    assert session.headers["X-CSRF-Token"] == "csrf123"
    assert "Mozilla" in session.headers["User-Agent"]


@patch("IVE.GAVEL.app.ports.gradescope_client.time.sleep", return_value=None)
@patch("IVE.GAVEL.app.ports.gradescope_client.requests.Session")
def test_download_all_assignments(mock_session_cls, _):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    # Fake responses for each GET call
    assignments_html = """
        <div data-assignment-id="123456">Module 3: Programming</div>
    """

    review_grades_html = """
        <a class="js-bulkExportModalDownload" href="/submissions.zip"></a>
    """

    zip_bytes = b"SUBMISSIONS.ZIP"

    # GET assignments page, GET review_grades, GET zip download
    mock_session.get.side_effect = [
        MagicMock(text=assignments_html),  # assignments list
        MagicMock(text=review_grades_html),  # review page
        MagicMock(content=zip_bytes),  # ZIP download
    ]

    # instantiate fake session, capture fake cookies
    client = GradescopeClient("courseID")

    client.capture_session = MagicMock(
        return_value=(GradescopeSession("cookie", None, {"_gradescope_session": "cookie"}), "999")
    )

    # run downloader on fake patched session
    with patch("builtins.open", MagicMock()):
        client.download_all_assignments("user", "password")

    # assert we made three GET calls in the previous series
    assert mock_session.get.call_count == 3
