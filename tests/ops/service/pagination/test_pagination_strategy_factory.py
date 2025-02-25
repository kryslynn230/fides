import pytest

from fides.api.ops.common_exceptions import NoSuchStrategyException, ValidationError
from fides.api.ops.service.pagination.pagination_strategy import PaginationStrategy
from fides.api.ops.service.pagination.pagination_strategy_cursor import (
    CursorPaginationStrategy,
)
from fides.api.ops.service.pagination.pagination_strategy_link import (
    LinkPaginationStrategy,
)
from fides.api.ops.service.pagination.pagination_strategy_offset import (
    OffsetPaginationStrategy,
)


def test_get_strategy_offset():
    config = {
        "incremental_param": "page",
        "increment_by": 1,
        "limit": 100,
    }
    strategy = PaginationStrategy.get_strategy(
        strategy_name="offset", configuration=config
    )
    assert isinstance(strategy, OffsetPaginationStrategy)


def test_get_strategy_link():
    config = {"source": "body", "path": "body.next_link"}
    strategy = PaginationStrategy.get_strategy(
        strategy_name="link", configuration=config
    )
    assert isinstance(strategy, LinkPaginationStrategy)


def test_get_strategy_cursor():
    config = {"cursor_param": "after", "field": "id"}
    strategy = PaginationStrategy.get_strategy(
        strategy_name="cursor", configuration=config
    )
    assert isinstance(strategy, CursorPaginationStrategy)


def test_get_strategy_invalid_config():
    with pytest.raises(ValidationError):
        PaginationStrategy.get_strategy(
            strategy_name="offset", configuration={"invalid": "thing"}
        )


def test_get_strategy_invalid_strategy():
    with pytest.raises(NoSuchStrategyException):
        PaginationStrategy.get_strategy("invalid", {})
