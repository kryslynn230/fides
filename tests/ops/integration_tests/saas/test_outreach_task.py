import random

import pytest

from fides.api.ops.graph.graph import DatasetGraph
from fides.api.ops.models.privacy_request import PrivacyRequest
from fides.api.ops.schemas.redis_cache import Identity
from fides.api.ops.service.connectors import get_connector
from fides.api.ops.task import graph_task
from fides.api.ops.task.filter_results import filter_data_categories
from fides.api.ops.task.graph_task import get_cached_data_for_erasures
from fides.core.config import CONFIG
from tests.ops.graph.graph_test_util import assert_rows_match


@pytest.mark.skip(reason="Currently unable to test OAuth2 connectors")
@pytest.mark.integration_saas
@pytest.mark.integration_outreach
def test_outreach_connection_test(outreach_connection_config) -> None:
    get_connector(outreach_connection_config).test_connection()


@pytest.mark.skip(reason="Currently unable to test OAuth2 connectors")
@pytest.mark.integration_saas
@pytest.mark.integration_outreach
@pytest.mark.asyncio
async def test_outreach_access_request_task(
    db,
    policy,
    outreach_connection_config,
    outreach_dataset_config,
    outreach_identity_email,
) -> None:
    """Full access request based on the Outreach SaaS config"""

    privacy_request = PrivacyRequest(
        id=f"test_outreach_access_request_task_{random.randint(0, 1000)}"
    )
    identity = Identity(**{"email": outreach_identity_email})
    privacy_request.cache_identity(identity)

    dataset_name = outreach_connection_config.get_saas_config().fides_key
    merged_graph = outreach_dataset_config.get_graph()
    graph = DatasetGraph(merged_graph)

    v = await graph_task.run_access_request(
        privacy_request,
        policy,
        graph,
        [outreach_connection_config],
        {"email": outreach_identity_email},
        db,
    )

    assert_rows_match(
        v[f"{dataset_name}:prospects"],
        min_size=1,
        keys=["type", "id", "attributes", "relationships", "links"],
    )
    assert_rows_match(
        v[f"{dataset_name}:recipients"],
        min_size=1,
        keys=["type", "id", "attributes", "links"],
    )

    # verify we only returned data for our identity email
    assert (
        outreach_identity_email
        in v[f"{dataset_name}:prospects"][0]["attributes"]["emails"]
    )

    assert (
        v[f"{dataset_name}:recipients"][0]["attributes"]["value"]
        == outreach_identity_email
    )

    # verify we keep the expected fields after filtering by the user data category
    target_categories = {"user"}
    filtered_results = filter_data_categories(
        v, target_categories, graph.data_category_field_mapping
    )

    assert set(filtered_results.keys()) == {
        f"{dataset_name}:prospects",
        f"{dataset_name}:recipients",
    }

    assert set(filtered_results[f"{dataset_name}:prospects"][0].keys()) == {
        "attributes",
    }

    assert set(filtered_results[f"{dataset_name}:recipients"][0].keys()) == {
        "attributes",
    }


@pytest.mark.skip(reason="Currently unable to test OAuth2 connectors")
@pytest.mark.integration_saas
@pytest.mark.integration_outreach
@pytest.mark.asyncio
async def test_outreach_erasure_request_task(
    db,
    policy,
    erasure_policy_string_rewrite,
    outreach_connection_config,
    outreach_dataset_config,
    outreach_erasure_identity_email,
    outreach_create_erasure_data,
) -> None:
    """Full erasure request based on the Outreach SaaS config"""

    masking_strict = CONFIG.execution.masking_strict
    CONFIG.execution.masking_strict = False  # Allow Delete

    privacy_request = PrivacyRequest(
        id=f"test_outreach_erasure_request_task_{random.randint(0, 1000)}"
    )
    identity = Identity(**{"email": outreach_erasure_identity_email})
    privacy_request.cache_identity(identity)

    dataset_name = outreach_connection_config.get_saas_config().fides_key
    merged_graph = outreach_dataset_config.get_graph()
    graph = DatasetGraph(merged_graph)

    v = await graph_task.run_access_request(
        privacy_request,
        policy,
        graph,
        [outreach_connection_config],
        {"email": outreach_erasure_identity_email},
        db,
    )

    # verify staged data is available for erasure
    assert_rows_match(
        v[f"{dataset_name}:prospects"],
        min_size=1,
        keys=["type", "id", "attributes", "relationships", "links"],
    )
    assert_rows_match(
        v[f"{dataset_name}:recipients"],
        min_size=1,
        keys=["type", "id", "attributes", "links"],
    )

    x = await graph_task.run_erasure(
        privacy_request,
        erasure_policy_string_rewrite,
        graph,
        [outreach_connection_config],
        {"email": outreach_erasure_identity_email},
        get_cached_data_for_erasures(privacy_request.id),
        db,
    )

    # Assert erasure request made to prospects and recipients
    # cannot verify success immediately as this can take days, weeks to process
    assert x == {f"{dataset_name}:prospects": 1, f"{dataset_name}:recipients": 1}

    CONFIG.execution.masking_strict = masking_strict
