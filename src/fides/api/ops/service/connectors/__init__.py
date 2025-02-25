# pylint: disable=useless-import-alias

# Because these modules are imported into the __init__.py and used elsewhere they need
# to be explicitly exported in order to prevent implicit reexport errors in mypy.
# This is done by importing "as": `from fides.module import MyClass as MyClass`.

from typing import Any, Dict

from fides.api.ops.models.connectionconfig import ConnectionConfig as ConnectionConfig
from fides.api.ops.models.connectionconfig import ConnectionType as ConnectionType
from fides.api.ops.service.connectors.base_connector import (
    BaseConnector as BaseConnector,
)
from fides.api.ops.service.connectors.email.attentive_connector import (
    AttentiveConnector,
)
from fides.api.ops.service.connectors.email.sovrn_connector import SovrnConnector
from fides.api.ops.service.connectors.fides_connector import (
    FidesConnector as FidesConnector,
)
from fides.api.ops.service.connectors.http_connector import (
    HTTPSConnector as HTTPSConnector,
)
from fides.api.ops.service.connectors.manual_connector import (
    ManualConnector as ManualConnector,
)
from fides.api.ops.service.connectors.manual_webhook_connector import (
    ManualWebhookConnector as ManualWebhookConnector,
)
from fides.api.ops.service.connectors.mongodb_connector import (
    MongoDBConnector as MongoDBConnector,
)
from fides.api.ops.service.connectors.saas_connector import (
    SaaSConnector as SaaSConnector,
)
from fides.api.ops.service.connectors.sql_connector import (
    BigQueryConnector as BigQueryConnector,
)
from fides.api.ops.service.connectors.sql_connector import (
    MariaDBConnector as MariaDBConnector,
)
from fides.api.ops.service.connectors.sql_connector import (
    MicrosoftSQLServerConnector as MicrosoftSQLServerConnector,
)
from fides.api.ops.service.connectors.sql_connector import (
    MySQLConnector as MySQLConnector,
)
from fides.api.ops.service.connectors.sql_connector import (
    PostgreSQLConnector as PostgreSQLConnector,
)
from fides.api.ops.service.connectors.sql_connector import (
    RedshiftConnector as RedshiftConnector,
)
from fides.api.ops.service.connectors.sql_connector import (
    SnowflakeConnector as SnowflakeConnector,
)
from fides.api.ops.service.connectors.timescale_connector import (
    TimescaleConnector as TimescaleConnector,
)

supported_connectors: Dict[str, Any] = {
    ConnectionType.attentive.value: AttentiveConnector,
    ConnectionType.bigquery.value: BigQueryConnector,
    ConnectionType.fides.value: FidesConnector,
    ConnectionType.https.value: HTTPSConnector,
    ConnectionType.manual.value: ManualConnector,
    ConnectionType.manual_webhook.value: ManualWebhookConnector,
    ConnectionType.mariadb.value: MariaDBConnector,
    ConnectionType.mongodb.value: MongoDBConnector,
    ConnectionType.mssql.value: MicrosoftSQLServerConnector,
    ConnectionType.mysql.value: MySQLConnector,
    ConnectionType.postgres.value: PostgreSQLConnector,
    ConnectionType.redshift.value: RedshiftConnector,
    ConnectionType.saas.value: SaaSConnector,
    ConnectionType.snowflake.value: SnowflakeConnector,
    ConnectionType.sovrn.value: SovrnConnector,
    ConnectionType.timescale.value: TimescaleConnector,
}


def get_connector(conn_config: ConnectionConfig) -> BaseConnector:
    """Return the Connector class corresponding to the connection_type."""
    try:
        return supported_connectors[conn_config.connection_type.value](conn_config)  # type: ignore
    except KeyError:
        raise NotImplementedError(
            f"Add {conn_config.connection_type} to the 'supported_connectors' mapping."
        )
