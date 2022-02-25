from datetime import timedelta

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import clear_mappers, sessionmaker

from deploy.adapters import orm
from deploy.auth import create_access_token, get_password_hash
from deploy.bootstrap import bootstrap, get_bus
from deploy.config import settings
from deploy.domain import model
from deploy.entrypoints.fastapi_app import app as fastapi_app
from deploy.service_layer import unit_of_work


@pytest.fixture
def base_url():
    return "http://test"


@pytest.fixture
def anyio_backend():
    """Choose asyncio backend for tests"""
    return "trio"


@pytest.fixture(scope="session")
def postgres_db():
    engine = create_engine(settings.database_url)
    orm.metadata_obj.create_all(engine)
    orm.start_mappers()
    yield engine
    orm.metadata_obj.drop_all(engine)
    clear_mappers()


@pytest.fixture
def rollback_postgres_session(postgres_db):
    """Wraps the session in a transaction and rolls back after each test."""
    connection = postgres_db.connect()
    transaction = connection.begin()
    session = sessionmaker()(bind=connection)
    yield session
    print("cleanup/rollback session..")
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def rollback_postgres_uow(request, rollback_postgres_session):
    """
    Returns a unit of work that rolls back all changes after each test.
    """
    print("request: ", request)
    marks = [m.name for m in request.node.iter_markers()]
    print("marks: ", marks)

    def session_factory():
        """
        Just a helper to be able to pass the rollback_postgres_session
        to the unit of work.
        """
        return rollback_postgres_session

    return unit_of_work.TestableSqlAlchemyUnitOfWork(session_factory)


@pytest.fixture
def bus(rollback_postgres_uow):
    """The central message bus."""
    return bootstrap(start_orm=False, uow=rollback_postgres_uow)


@pytest.fixture
def app(bus):
    """
    Returns a fastapi app with custom message bus dependency.
    """
    fastapi_app.dependency_overrides[get_bus] = lambda: bus
    return fastapi_app


@pytest.fixture
def password():
    return "password"


@pytest.fixture
def user(password):
    return model.User(name="user", password=get_password_hash(password))


@pytest.fixture
def user_in_db(bus, user):
    with bus.uow as uow:
        uow.users.add(user)
        [from_db] = uow.users.get(user.name)
    return from_db


@pytest.fixture
def valid_access_token(user):
    return create_access_token({"type": "user", "user": user.name}, timedelta(minutes=5))


@pytest.fixture
def valid_access_token_in_db(user_in_db):
    print("user in db: ", user_in_db)
    return create_access_token({"type": "user", "user": user_in_db.name}, timedelta(minutes=5))


@pytest.fixture
def service():
    return model.Service(name="fastdeploytest", data={"foo": "bar"})


@pytest.fixture
def service_in_db(bus, service):
    with bus.uow as uow:
        uow.services.add(service)
        uow.commit()
        [from_db] = uow.services.get(service.name)
        print("from_db: ", from_db)
    return from_db
