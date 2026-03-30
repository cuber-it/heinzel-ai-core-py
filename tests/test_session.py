"""Tests for session module -- matches Go core/session_test.go."""

from core.context import Message
from core.session import Session, SessionManager


def test_session_start():
    mgr = SessionManager()
    session = mgr.start("Test Session")

    assert session.id != ""
    assert session.title == "Test Session"
    assert session.end_time is None
    assert mgr.active() is not None


def test_session_end():
    mgr = SessionManager()
    mgr.start("Test")
    mgr.end()

    assert mgr.active() is None
    hist = mgr.history()
    assert len(hist) == 1
    assert hist[0].end_time is not None


def test_session_start_ends_current_first():
    mgr = SessionManager()
    first = mgr.start("First")
    first_id = first.id
    mgr.start("Second")

    hist = mgr.history()
    assert len(hist) == 1
    assert hist[0].id == first_id
    assert mgr.active().title == "Second"


def test_session_resume():
    messages = [
        Message(role="user", content="hello"),
        Message(role="assistant", content="hi"),
    ]
    mgr = SessionManager(on_load=lambda session_id: messages)

    first = mgr.start("First")
    first_id = first.id
    mgr.start("Second")

    # First is now in history
    session, msgs = mgr.resume(first_id)
    assert session is not None
    assert session.id == first_id
    assert msgs is not None
    assert len(msgs) == 2
    assert mgr.active().id == first_id


def test_session_resume_unknown():
    mgr = SessionManager()
    session, msgs = mgr.resume("nonexistent")
    assert session is None
    assert msgs is None


def test_session_auto_title():
    mgr = SessionManager()
    mgr.start("")
    mgr.auto_title("Was ist der Sinn des Lebens?")

    assert mgr.active().title == "Was ist der Sinn des Lebens?"


def test_session_auto_title_truncate():
    mgr = SessionManager()
    mgr.start("")
    long_text = (
        "Dies ist ein sehr langer Satz der mehr als sechzig Zeichen hat "
        "und deshalb abgeschnitten werden sollte"
    )
    mgr.auto_title(long_text)

    assert len(mgr.active().title) <= 65


def test_session_auto_title_no_overwrite():
    mgr = SessionManager()
    mgr.start("Manueller Titel")
    mgr.auto_title("Sollte nicht ueberschreiben")

    assert mgr.active().title == "Manueller Titel"


def test_session_update_message_count():
    mgr = SessionManager()
    mgr.start("Test")
    mgr.update_message_count(42)

    assert mgr.active().messages == 42


def test_session_list():
    mgr = SessionManager()
    mgr.start("First")
    mgr.start("Second")
    mgr.start("Third")

    result = mgr.list()
    assert len(result) == 3  # 2 history + 1 active


def test_session_on_save_callback():
    saved: list[Session] = []
    mgr = SessionManager(on_save=lambda session: saved.append(session))

    mgr.start("Test")
    mgr.end()

    assert len(saved) == 1
    assert saved[0].title == "Test"


def test_session_load_history():
    mgr = SessionManager()
    mgr.load_history([
        Session(id="old1", title="Old Session 1"),
        Session(id="old2", title="Old Session 2"),
    ])

    hist = mgr.history()
    assert len(hist) == 2


def test_session_unique_ids():
    mgr = SessionManager()
    ids: set[str] = set()
    for _ in range(100):
        session = mgr.start("")
        assert session.id not in ids, f"duplicate session ID: {session.id}"
        ids.add(session.id)
