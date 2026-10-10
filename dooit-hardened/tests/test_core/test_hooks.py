from tests.test_core.core_base import *  # noqa


def test_todo_status_update_children(todo1):
    assert todo1.is_pending

    for child_todo in todo1.todos:
        child_todo.toggle_complete()

    assert not todo1.is_pending
