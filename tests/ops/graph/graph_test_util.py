import random
from typing import Iterable

from fideslang.validation import FidesKey
from sqlalchemy.engine import Engine

from fides.api.ops.graph.config import *
from fides.api.ops.graph.traversal import *
from fides.api.ops.graph.traversal import Traversal, TraversalNode

# to avoid having faker spam the logs
from fides.api.ops.models.connectionconfig import ConnectionConfig
from fides.api.ops.models.policy import ActionType, Policy, Rule, RuleTarget
from fides.api.ops.models.privacy_request import PrivacyRequest
from fides.api.ops.service.connectors import BaseConnector, MongoDBConnector
from fides.api.ops.service.connectors.sql_connector import SQLConnector
from fides.api.ops.task.graph_task import GraphTask
from fides.api.ops.task.task_resources import TaskResources
from fides.api.ops.util.collection_util import Row
from fides.lib.db.base_class import FidesBase
from tests.fixtures.application_fixtures import faker


class MockResources(TaskResources):
    def __init__(self, request: PrivacyRequest):
        super().__init__(request, Policy(), [])

    def get_connector(self, key: FidesKey) -> Any:
        return MockSqlConnector()


class MockSqlConnector(SQLConnector):
    def __init__(self):
        return super().__init__(ConnectionConfig())

    def build_uri(self) -> str:
        """Build a database specific uri connection string"""
        raise AttributeError("Unsupported")

    def client(self) -> Engine:
        """Return SQLAlchemy engine that can be used to interact with a database"""
        raise AttributeError("Unsupported")

    def retrieve_data(
        self,
        node: TraversalNode,
        policy: Policy,
        privacy_request: PrivacyRequest,
        input_data: Dict[str, List[Any]],
    ) -> List[Row]:
        return [generate_collection(node.node.collection) for _ in range(3)]


class MockSqlTask(GraphTask):
    def connector(self) -> BaseConnector:
        return MockSqlConnector(ConnectionConfig())


class MockMongoTask(GraphTask):
    def connector(self) -> BaseConnector:
        return MongoDBConnector(ConnectionConfig())


#  -------------------------------------------
#   test utility functions
#  -------------------------------------------
def erasure_policy(*erasure_categories: str) -> Policy:
    """Generate an erasure policy with the given categories"""
    policy = Policy()
    targets = [RuleTarget(data_category=c) for c in erasure_categories]
    policy.rules = [
        Rule(
            action_type=ActionType.erasure,
            targets=targets,
            masking_strategy={
                "strategy": "null_rewrite",
                "configuration": {},
            },
        )
    ]
    return policy


def records_matching_fields(records: List[FidesBase], **args):
    """records that match parameters passed in from a list of returned records"""
    return [
        record for record in records if all([record[k] == v for k, v in args.items()])
    ]


def assert_rows_match(rows: List[Row], min_size: int, keys: Iterable[str]) -> None:
    def contains_keys(data: Dict[str, Any], *keys: str) -> bool:
        """The provided collection contains all the specified keys"""
        return len(set(keys).difference(set(data.keys()))) == 0

    assert len(rows) >= min_size
    for row in rows:
        assert contains_keys(
            row, *keys
        ), f"assert_rows_match differs by [{','.join(set(keys).difference(set(row.keys())))}]"


# Helper methods
def generate_collection(collection: Collection) -> Dict[str, Any]:
    """A first version fake data generator that assumes that
    - anything named "*_id" or "id" is an int.
    - anything else gets a string
    """

    def value_for_name(name: str) -> Any:
        if name == "id" or name.find("_id") > -1:
            return random.randint(0, 1000000000)
        if name.find("email") > -1:
            return faker.email()
        return faker.name()

    return {f.name: value_for_name(f.name) for f in collection.field_dict.values()}


def generate_field_list(num_fields: int) -> List[ScalarField]:
    return [ScalarField(name=f"f{i}") for i in range(1, num_fields + 1)]


def generate_node(dr_name: str, ds_name: str, *field_names: str) -> Node:
    ds = Collection(name=ds_name, fields=[ScalarField(name=s) for s in field_names])
    dr = GraphDataset(
        name=dr_name,
        collections=[ds],
        connection_key=f"mock_connection_config_key_{dr_name}",
    )
    return Node(dr, ds)


def field(dataresources: List[GraphDataset], *address: str) -> ScalarField:
    """Test util to access a particular field - can access a nested field one level deep"""
    dr: GraphDataset = next(dr for dr in dataresources if dr.name == address[0])
    ds: Collection = next(ds for ds in dr.collections if ds.name == address[1])

    try:
        # Assuming object field with at most one level - get ScalarField out of object field
        df: ScalarField = next(
            df for df in ds.field_dict.values() if df.name == address[3]
        )
    except:
        df: ScalarField = next(
            df for df in ds.field_dict.values() if df.name == address[2]
        )
    return df


def collection(
    dataresources: List[GraphDataset], address: CollectionAddress
) -> Collection:
    dr: GraphDataset = next(dr for dr in dataresources if dr.name == address.dataset)
    return next(ds for ds in dr.collections if ds.name == address.collection)


def dataresource(
    dataresources: List[GraphDataset], address: DatasetAddress
) -> GraphDataset:
    return next(dr for dr in dataresources if dr.name == address)


def incoming_edges(traversal: Traversal, node_address: CollectionAddress) -> Set[Edge]:
    tnode = traversal.traversal_node_dict[node_address]
    return tnode.incoming_edges()


def outgoing_edges(traversal: Traversal, node_address: CollectionAddress) -> Set[Edge]:
    tnode = traversal.traversal_node_dict[node_address]
    return tnode.outgoing_edges()


def generate_traversal(
    seed: Dict[str, Any], *dataresources: GraphDataset
) -> Tuple[Dict[str, Any], List[CollectionAddress]]:
    graph = DatasetGraph(*dataresources)
    traversal = Traversal(graph, seed)
    return traversal.traversal_map()


def generate_traversal_order(
    traversal: Traversal,
) -> Dict[CollectionAddress, List[int]]:
    def traversal_order_fn(
        tn: TraversalNode, data: Dict[CollectionAddress, List[int]]
    ) -> None:
        if tn.address in data:
            data[tn.address].append(traversal_order_fn.counter)
        else:
            data[tn.address] = [traversal_order_fn.counter]
        traversal_order_fn.counter += 1

    traversal_order_fn.counter = 0

    env: Dict[CollectionAddress, List[int]] = {}
    traversal.traverse(env, traversal_order_fn)
    return env


# --------------- generated graphs -------------
def generate_graph_resources(num_nodes: int) -> List[GraphDataset]:
    return [
        GraphDataset(
            name=f"dr_{i}",
            collections=[Collection(name=f"ds_{i}", fields=generate_field_list(3))],
            connection_key=f"mock_connection_config_key_{i}",
        )
        for i in range(1, num_nodes + 1)
    ]


def generate_binary_tree_resources(
    num_levels: int, branching_factor: int = 2
) -> List[GraphDataset]:
    """Generate a multi-level binary tree for testing"""
    root = GraphDataset(
        name=f"root",
        collections=[Collection(name=f"ds", fields=generate_field_list(3))],
        connection_key=f"mock_connection_config_key_root",
    )

    queue = [root]
    resources = [root]
    field(resources, "root", "ds", "f1").identity = "email"
    level = 1
    while queue:
        next_node = queue.pop()
        next_dr_name, next_ds_name = next_node.name, next_node.collections[0].name
        for j in range(branching_factor):
            next_child_key = (f"{next_dr_name}.{j}", f"{next_ds_name}.{j}", "f1")
            next_child = GraphDataset(
                name=next_child_key[0],
                collections=[
                    Collection(name=next_child_key[1], fields=generate_field_list(3))
                ],
                connection_key="mock_connection_config_key",
            )
            resources.append(next_child)
            if level < num_levels:
                queue.insert(0, next_child)
            field(resources, next_dr_name, next_ds_name, "f1").references.append(
                (FieldAddress(*next_child_key), None)
            )
        level += 1
    return resources


def generate_fully_connected_resources(size: int) -> List[GraphDataset]:
    """Generate a fully connected graph of resources"""

    def connect(r1: GraphDataset, r2: GraphDataset) -> None:
        field(
            [r1], r1.name, r1.collections[0].name, random.choice(["f1", "f2", "f3"])
        ).references.append(
            (
                FieldAddress(
                    r2.name, r2.collections[0].name, random.choice(["f1", "f2", "f3"])
                ),
                None,
            )
        )

    resources_dict = {r.name: r for r in generate_graph_resources(size)}
    resource_names = set(resources_dict.keys())
    for name, r in resources_dict.items():
        for other_name in resource_names.difference({name}):
            connect(r, resources_dict[other_name])
    return list(resources_dict.values())
