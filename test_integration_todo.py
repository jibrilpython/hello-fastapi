import pytest
from fastapi.testclient import TestClient

from app import app
from database import Base, engine, SessionLocal
from models import Todo


# ---------- Авто-фикстура: очищаем БД перед каждым тестом ----------

@pytest.fixture(autouse=True)
def prepare_database():
    """
    Перед каждым тестом пересоздаем таблицы,
    чтобы тесты были изолированными и воспроизводимыми.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    # После теста можно ничего не делать — БД маленькая.


client = TestClient(app)

@pytest.mark.xfail(reason="Known bug — app does not handle nonexistent IDs")
def test_update_nonexistent_todo_returns_error():
    response = client.get("/update/999", follow_redirects=False)
    assert response.status_code >= 500
    
def get_all_todos():
    """Вспомогательная функция: достать все Todo напрямую из БД."""
    db = SessionLocal()
    try:
        return db.query(Todo).all()
    finally:
        db.close()


# ---------- Интеграционные тесты ----------

def test_home_page_works():
    """
    Проверяем, что главная страница отдается успешно.
    Интеграция: FastAPI -> шаблоны -> БД (пустая).
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "Flask ToDo App" in response.text


def test_add_todo_creates_record_and_shows_on_home():
    """
    Сценарий: пользователь добавляет задачу через форму.
    Интеграция: HTTP POST /add -> БД -> редирект -> шаблон со списком.
    """
    response = client.post(
        "/add",
        data={"title": "Test integration task"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Задача должна появиться в HTML
    assert "Test integration task" in response.text

    # И реально сохраниться в БД
    todos = get_all_todos()
    assert len(todos) == 1
    assert todos[0].title == "Test integration task"
    assert todos[0].complete is False


def test_update_todo_toggles_complete_flag():
    """
    Сценарий: пользователь добавляет задачу, затем отмечает ее как выполненную.
    Интеграция: /add -> /update/{id} -> изменение поля complete в БД.
    """
    # Сначала добавим задачу
    client.post("/add", data={"title": "To be completed"}, follow_redirects=True)

    # В тестовой БД первая запись будет с id = 1
    response_update = client.get("/update/1", follow_redirects=True)
    assert response_update.status_code == 200

    # Проверяем в БД, что флаг complete переключился
    todos = get_all_todos()
    assert len(todos) == 1
    assert todos[0].title == "To be completed"
    assert todos[0].complete is True


def test_delete_todo_removes_record():
    """
    Сценарий: пользователь добавляет задачу, затем удаляет ее.
    Интеграция: /add -> /delete/{id} -> удаление из БД -> обновление списка.
    """
    client.post("/add", data={"title": "To be deleted"}, follow_redirects=True)

    # Удаляем задачу с id=1
    response_delete = client.get("/delete/1", follow_redirects=True)
    assert response_delete.status_code == 200

    todos = get_all_todos()
    assert len(todos) == 0
    # И в HTML задачи больше нет
    assert "To be deleted" not in response_delete.text


def test_update_nonexistent_todo_returns_error():
    """
    Граничный/ошибочный сценарий:
    попытка обновить несуществующую задачу.
    В текущей реализации это приводит к 500 (AttributeError),
    что показывает потенциальную проблему в обработке ошибок.
    """
    response = client.get("/update/999", follow_redirects=False)

    # Ожидаем, что сервер вернет ошибку (500),
    # так как код не проверяет наличие todo в БД.
    assert response.status_code >= 500
