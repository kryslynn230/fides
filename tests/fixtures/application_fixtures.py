import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Generator, List, Optional
from unittest import mock
from uuid import uuid4

import pydash
import pytest
import yaml
from faker import Faker
from fideslang.models import Dataset
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError, StaleDataError
from toml import load as load_toml

from fides.api.ctl.sql_models import Dataset as CtlDataset
from fides.api.ctl.sql_models import System
from fides.api.ops.common_exceptions import SystemManagerException
from fides.api.ops.models.application_config import ApplicationConfig
from fides.api.ops.models.connectionconfig import (
    AccessLevel,
    ConnectionConfig,
    ConnectionType,
)
from fides.api.ops.models.datasetconfig import DatasetConfig
from fides.api.ops.models.messaging import MessagingConfig
from fides.api.ops.models.policy import (
    ActionType,
    Policy,
    PolicyPostWebhook,
    PolicyPreWebhook,
    Rule,
    RuleTarget,
)
from fides.api.ops.models.privacy_notice import (
    ConsentMechanism,
    EnforcementLevel,
    PrivacyNotice,
    PrivacyNoticeRegion,
)
from fides.api.ops.models.privacy_request import (
    ConsentRequest,
    PrivacyRequest,
    PrivacyRequestStatus,
    ProvidedIdentity,
)
from fides.api.ops.models.registration import UserRegistration
from fides.api.ops.models.storage import (
    ResponseFormat,
    StorageConfig,
    _create_local_default_storage,
    default_storage_config_name,
)
from fides.api.ops.schemas.messaging.messaging import (
    MessagingServiceDetails,
    MessagingServiceSecrets,
    MessagingServiceType,
)
from fides.api.ops.schemas.redis_cache import Identity
from fides.api.ops.schemas.storage.storage import (
    FileNaming,
    S3AuthMethod,
    StorageDetails,
    StorageSecrets,
    StorageType,
)
from fides.api.ops.service.connectors.fides.fides_client import FidesClient
from fides.api.ops.service.masking.strategy.masking_strategy_hmac import (
    HmacMaskingStrategy,
)
from fides.api.ops.service.masking.strategy.masking_strategy_nullify import (
    NullMaskingStrategy,
)
from fides.api.ops.service.masking.strategy.masking_strategy_string_rewrite import (
    StringRewriteMaskingStrategy,
)
from fides.api.ops.util.data_category import DataCategory
from fides.core.config import CONFIG
from fides.core.config.helpers import load_file
from fides.lib.models.audit_log import AuditLog, AuditLogAction
from fides.lib.models.client import ClientDetail
from fides.lib.models.fides_user import FidesUser
from fides.lib.models.fides_user_permissions import FidesUserPermissions
from fides.lib.oauth.roles import APPROVER, VIEWER

logging.getLogger("faker").setLevel(logging.ERROR)
# disable verbose faker logging
faker = Faker()
integration_config = load_toml("tests/ops/integration_test_config.toml")


# Unified list of connections to integration dbs specified from fides.api-integration.toml

integration_secrets = {
    "postgres_example": {
        "host": pydash.get(integration_config, "postgres_example.server"),
        "port": pydash.get(integration_config, "postgres_example.port"),
        "dbname": pydash.get(integration_config, "postgres_example.db"),
        "username": pydash.get(integration_config, "postgres_example.user"),
        "password": pydash.get(integration_config, "postgres_example.password"),
    },
    "mongo_example": {
        "host": pydash.get(integration_config, "mongodb_example.server"),
        "defaultauthdb": pydash.get(integration_config, "mongodb_example.db"),
        "username": pydash.get(integration_config, "mongodb_example.user"),
        "password": pydash.get(integration_config, "mongodb_example.password"),
    },
    "mysql_example": {
        "host": pydash.get(integration_config, "mysql_example.server"),
        "port": pydash.get(integration_config, "mysql_example.port"),
        "dbname": pydash.get(integration_config, "mysql_example.db"),
        "username": pydash.get(integration_config, "mysql_example.user"),
        "password": pydash.get(integration_config, "mysql_example.password"),
    },
    "mssql_example": {
        "host": pydash.get(integration_config, "mssql_example.server"),
        "port": pydash.get(integration_config, "mssql_example.port"),
        "dbname": pydash.get(integration_config, "mssql_example.db"),
        "username": pydash.get(integration_config, "mssql_example.user"),
        "password": pydash.get(integration_config, "mssql_example.password"),
    },
    "mariadb_example": {
        "host": pydash.get(integration_config, "mariadb_example.server"),
        "port": pydash.get(integration_config, "mariadb_example.port"),
        "dbname": pydash.get(integration_config, "mariadb_example.db"),
        "username": pydash.get(integration_config, "mariadb_example.user"),
        "password": pydash.get(integration_config, "mariadb_example.password"),
    },
    "timescale_example": {
        "host": pydash.get(integration_config, "timescale_example.server"),
        "port": pydash.get(integration_config, "timescale_example.port"),
        "dbname": pydash.get(integration_config, "timescale_example.db"),
        "username": pydash.get(integration_config, "timescale_example.user"),
        "password": pydash.get(integration_config, "timescale_example.password"),
    },
    "fides_example": {
        "uri": pydash.get(integration_config, "fides_example.uri"),
        "username": pydash.get(integration_config, "fides_example.username"),
        "password": pydash.get(integration_config, "fides_example.password"),
        "polling_timeout": pydash.get(
            integration_config, "fides_example.polling_timeout"
        ),
    },
}


@pytest.fixture(scope="session", autouse=True)
def mock_upload_logic() -> Generator:
    with mock.patch(
        "fides.api.ops.service.storage.storage_uploader_service.upload_to_s3"
    ) as _fixture:
        yield _fixture


@pytest.fixture(scope="function")
def storage_config(db: Session) -> Generator:
    name = str(uuid4())
    storage_config = StorageConfig.create(
        db=db,
        data={
            "name": name,
            "type": StorageType.s3,
            "details": {
                StorageDetails.AUTH_METHOD.value: S3AuthMethod.SECRET_KEYS.value,
                StorageDetails.NAMING.value: FileNaming.request_id.value,
                StorageDetails.BUCKET.value: "test_bucket",
            },
            "key": "my_test_config",
            "format": ResponseFormat.json,
        },
    )
    storage_config.set_secrets(
        db=db,
        storage_secrets={
            StorageSecrets.AWS_ACCESS_KEY_ID.value: "1234",
            StorageSecrets.AWS_SECRET_ACCESS_KEY.value: "5678",
        },
    )
    yield storage_config
    storage_config.delete(db)


@pytest.fixture(scope="function")
def storage_config_local(db: Session) -> Generator:
    name = str(uuid4())
    storage_config = StorageConfig.create(
        db=db,
        data={
            "name": name,
            "type": StorageType.local,
            "details": {
                StorageDetails.NAMING.value: FileNaming.request_id.value,
            },
            "key": "my_test_config_local",
            "format": ResponseFormat.json,
        },
    )
    yield storage_config
    storage_config.delete(db)


@pytest.fixture(scope="function")
def storage_config_default(db: Session) -> Generator:
    """
    Create and yield a default storage config, as defined by its
    `is_default` flag being set to `True`. This is an s3 storage config.
    """
    sc = StorageConfig.create(
        db=db,
        data={
            "name": default_storage_config_name(StorageType.s3.value),
            "type": StorageType.s3,
            "is_default": True,
            "details": {
                StorageDetails.NAMING.value: FileNaming.request_id.value,
                StorageDetails.AUTH_METHOD.value: S3AuthMethod.AUTOMATIC.value,
                StorageDetails.BUCKET.value: "test_bucket",
            },
            "format": ResponseFormat.json,
        },
    )
    yield sc


@pytest.fixture(scope="function")
def storage_config_default_s3_secret_keys(db: Session) -> Generator:
    """
    Create and yield a default storage config, as defined by its
    `is_default` flag being set to `True`. This is an s3 storage config.
    """
    sc = StorageConfig.create(
        db=db,
        data={
            "name": default_storage_config_name(StorageType.s3.value),
            "type": StorageType.s3,
            "is_default": True,
            "details": {
                StorageDetails.NAMING.value: FileNaming.request_id.value,
                StorageDetails.AUTH_METHOD.value: S3AuthMethod.SECRET_KEYS.value,
                StorageDetails.BUCKET.value: "test_bucket",
            },
            "secrets": {
                StorageSecrets.AWS_ACCESS_KEY_ID.value: "access_key_id",
                StorageSecrets.AWS_SECRET_ACCESS_KEY.value: "secret_access_key",
            },
            "format": ResponseFormat.json,
        },
    )
    yield sc


@pytest.fixture(scope="function")
def storage_config_default_local(db: Session) -> Generator:
    """
    Create and yield the default local storage config.
    """
    sc = _create_local_default_storage(db)
    yield sc


@pytest.fixture(scope="function")
def set_active_storage_s3(db) -> None:
    ApplicationConfig.create_or_update(
        db,
        data={
            "api_set": {
                "storage": {"active_default_storage_type": StorageType.s3.value}
            }
        },
    )


@pytest.fixture(scope="function")
def messaging_config(db: Session) -> Generator:
    name = str(uuid4())
    messaging_config = MessagingConfig.create(
        db=db,
        data={
            "name": name,
            "key": "my_mailgun_messaging_config",
            "service_type": MessagingServiceType.mailgun.value,
            "details": {
                MessagingServiceDetails.API_VERSION.value: "v3",
                MessagingServiceDetails.DOMAIN.value: "some.domain",
                MessagingServiceDetails.IS_EU_DOMAIN.value: False,
            },
        },
    )
    messaging_config.set_secrets(
        db=db,
        messaging_secrets={
            MessagingServiceSecrets.MAILGUN_API_KEY.value: "12984r70298r"
        },
    )
    yield messaging_config
    messaging_config.delete(db)


@pytest.fixture(scope="function")
def messaging_config_twilio_email(db: Session) -> Generator:
    name = str(uuid4())
    messaging_config = MessagingConfig.create(
        db=db,
        data={
            "name": name,
            "key": "my_twilio_email_config",
            "service_type": MessagingServiceType.twilio_email.value,
        },
    )
    messaging_config.set_secrets(
        db=db,
        messaging_secrets={
            MessagingServiceSecrets.TWILIO_API_KEY.value: "123489ctynpiqurwfh"
        },
    )
    yield messaging_config
    messaging_config.delete(db)


@pytest.fixture(scope="function")
def messaging_config_twilio_sms(db: Session) -> Generator:
    name = str(uuid4())
    messaging_config = MessagingConfig.create(
        db=db,
        data={
            "name": name,
            "key": "my_twilio_sms_config",
            "service_type": MessagingServiceType.twilio_text.value,
        },
    )
    messaging_config.set_secrets(
        db=db,
        messaging_secrets={
            MessagingServiceSecrets.TWILIO_ACCOUNT_SID.value: "23rwrfwxwef",
            MessagingServiceSecrets.TWILIO_AUTH_TOKEN.value: "23984y29384y598432",
            MessagingServiceSecrets.TWILIO_MESSAGING_SERVICE_SID.value: "2ieurnoqw",
        },
    )
    yield messaging_config
    messaging_config.delete(db)


@pytest.fixture(scope="function")
def messaging_config_mailchimp_transactional(db: Session) -> Generator:
    messaging_config = MessagingConfig.create(
        db=db,
        data={
            "name": str(uuid4()),
            "key": "my_mailchimp_transactional_messaging_config",
            "service_type": MessagingServiceType.mailchimp_transactional,
            "details": {
                MessagingServiceDetails.DOMAIN.value: "some.domain",
                MessagingServiceDetails.EMAIL_FROM.value: "test@example.com",
            },
        },
    )
    messaging_config.set_secrets(
        db=db,
        messaging_secrets={
            MessagingServiceSecrets.MAILCHIMP_TRANSACTIONAL_API_KEY.value: "12984r70298r"
        },
    )
    yield messaging_config
    messaging_config.delete(db)


@pytest.fixture(scope="function")
def https_connection_config(db: Session) -> Generator:
    name = str(uuid4())
    connection_config = ConnectionConfig.create(
        db=db,
        data={
            "name": name,
            "key": "my_webhook_config",
            "connection_type": ConnectionType.https,
            "access": AccessLevel.read,
            "secrets": {
                "url": "http://example.com",
                "authorization": "test_authorization",
            },
        },
    )
    yield connection_config
    connection_config.delete(db)


@pytest.fixture(scope="function")
def policy_pre_execution_webhooks(
    db: Session, https_connection_config, policy
) -> Generator:
    pre_webhook = PolicyPreWebhook.create(
        db=db,
        data={
            "connection_config_id": https_connection_config.id,
            "policy_id": policy.id,
            "direction": "one_way",
            "name": str(uuid4()),
            "key": "pre_execution_one_way_webhook",
            "order": 0,
        },
    )
    pre_webhook_two = PolicyPreWebhook.create(
        db=db,
        data={
            "connection_config_id": https_connection_config.id,
            "policy_id": policy.id,
            "direction": "two_way",
            "name": str(uuid4()),
            "key": "pre_execution_two_way_webhook",
            "order": 1,
        },
    )
    db.commit()
    yield [pre_webhook, pre_webhook_two]
    try:
        pre_webhook.delete(db)
    except ObjectDeletedError:
        pass
    try:
        pre_webhook_two.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def policy_post_execution_webhooks(
    db: Session, https_connection_config, policy
) -> Generator:
    post_webhook = PolicyPostWebhook.create(
        db=db,
        data={
            "connection_config_id": https_connection_config.id,
            "policy_id": policy.id,
            "direction": "one_way",
            "name": str(uuid4()),
            "key": "cache_busting_webhook",
            "order": 0,
        },
    )
    post_webhook_two = PolicyPostWebhook.create(
        db=db,
        data={
            "connection_config_id": https_connection_config.id,
            "policy_id": policy.id,
            "direction": "one_way",
            "name": str(uuid4()),
            "key": "cleanup_webhook",
            "order": 1,
        },
    )
    db.commit()
    yield [post_webhook, post_webhook_two]
    try:
        post_webhook.delete(db)
    except ObjectDeletedError:
        pass
    try:
        post_webhook_two.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def access_and_erasure_policy(
    db: Session,
    oauth_client: ClientDetail,
    storage_config: StorageConfig,
) -> Generator:
    access_and_erasure_policy = Policy.create(
        db=db,
        data={
            "name": "example access and erasure policy",
            "key": "example_access_erasure_policy",
            "client_id": oauth_client.id,
        },
    )
    access_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.access.value,
            "client_id": oauth_client.id,
            "name": "Access Request Rule",
            "policy_id": access_and_erasure_policy.id,
            "storage_destination_id": storage_config.id,
        },
    )
    access_rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user").value,
            "rule_id": access_rule.id,
        },
    )
    erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "Erasure Rule",
            "policy_id": access_and_erasure_policy.id,
            "masking_strategy": {
                "strategy": "null_rewrite",
                "configuration": {},
            },
        },
    )

    erasure_rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.name").value,
            "rule_id": erasure_rule.id,
        },
    )
    yield access_and_erasure_policy
    try:
        access_rule_target.delete(db)
        erasure_rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_rule.delete(db)
        erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_and_erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def erasure_policy(
    db: Session,
    oauth_client: ClientDetail,
) -> Generator:
    erasure_policy = Policy.create(
        db=db,
        data={
            "name": "example erasure policy",
            "key": "example_erasure_policy",
            "client_id": oauth_client.id,
        },
    )

    erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "Erasure Rule",
            "policy_id": erasure_policy.id,
            "masking_strategy": {
                "strategy": "null_rewrite",
                "configuration": {},
            },
        },
    )

    rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.name").value,
            "rule_id": erasure_rule.id,
        },
    )
    yield erasure_policy
    try:
        rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def erasure_policy_aes(
    db: Session,
    oauth_client: ClientDetail,
) -> Generator:
    erasure_policy = Policy.create(
        db=db,
        data={
            "name": "example erasure policy aes",
            "key": "example_erasure_policy_aes",
            "client_id": oauth_client.id,
        },
    )

    erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "Erasure Rule",
            "policy_id": erasure_policy.id,
            "masking_strategy": {
                "strategy": "aes_encrypt",
                "configuration": {},
            },
        },
    )

    rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.name").value,
            "rule_id": erasure_rule.id,
        },
    )
    yield erasure_policy
    try:
        rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def erasure_policy_string_rewrite_long(
    db: Session,
    oauth_client: ClientDetail,
) -> Generator:
    erasure_policy = Policy.create(
        db=db,
        data={
            "name": "example erasure policy string rewrite",
            "key": "example_erasure_policy_string_rewrite",
            "client_id": oauth_client.id,
        },
    )

    erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "Erasure Rule",
            "policy_id": erasure_policy.id,
            "masking_strategy": {
                "strategy": StringRewriteMaskingStrategy.name,
                "configuration": {
                    "rewrite_value": "some rewrite value that is very long and goes on and on"
                },
            },
        },
    )

    rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.name").value,
            "rule_id": erasure_rule.id,
        },
    )
    yield erasure_policy
    try:
        rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def erasure_policy_two_rules(
    db: Session, oauth_client: ClientDetail, erasure_policy: Policy
) -> Generator:
    second_erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "Second Erasure Rule",
            "policy_id": erasure_policy.id,
            "masking_strategy": {
                "strategy": NullMaskingStrategy.name,
                "configuration": {},
            },
        },
    )

    # TODO set masking strategy in Rule.create() call above, once more masking strategies beyond NULL_REWRITE are supported.
    second_erasure_rule.masking_strategy = {
        "strategy": StringRewriteMaskingStrategy.name,
        "configuration": {"rewrite_value": "*****"},
    }

    second_rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.contact.email").value,
            "rule_id": second_erasure_rule.id,
        },
    )
    yield erasure_policy
    try:
        second_rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        second_erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def policy(
    db: Session,
    oauth_client: ClientDetail,
    storage_config: StorageConfig,
) -> Generator:
    access_request_policy = Policy.create(
        db=db,
        data={
            "name": "example access request policy",
            "key": "example_access_request_policy",
            "client_id": oauth_client.id,
            "execution_timeframe": 7,
        },
    )

    access_request_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.access.value,
            "client_id": oauth_client.id,
            "name": "Access Request Rule",
            "policy_id": access_request_policy.id,
            "storage_destination_id": storage_config.id,
        },
    )

    rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user").value,
            "rule_id": access_request_rule.id,
        },
    )
    yield access_request_policy
    try:
        rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_request_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_request_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def consent_policy(
    db: Session,
    oauth_client: ClientDetail,
    storage_config: StorageConfig,
) -> Generator:
    """Consent policies only need a ConsentRule attached - no RuleTargets necessary"""
    consent_request_policy = Policy.create(
        db=db,
        data={
            "name": "example consent request policy",
            "key": "example_consent_request_policy",
            "client_id": oauth_client.id,
        },
    )

    consent_request_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.consent.value,
            "client_id": oauth_client.id,
            "name": "Consent Request Rule",
            "policy_id": consent_request_policy.id,
        },
    )

    yield consent_request_policy
    try:
        consent_request_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        consent_request_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def policy_local_storage(
    db: Session,
    oauth_client: ClientDetail,
    storage_config_local: StorageConfig,
) -> Generator:
    """
    A basic example policy fixture that uses a local storage config
    in cases where end-to-end request execution must actually succeed
    """
    access_request_policy = Policy.create(
        db=db,
        data={
            "name": "example access request policy",
            "key": "example_access_request_policy",
            "client_id": oauth_client.id,
            "execution_timeframe": 7,
        },
    )

    access_request_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.access.value,
            "client_id": oauth_client.id,
            "name": "Access Request Rule",
            "policy_id": access_request_policy.id,
            "storage_destination_id": storage_config_local.id,
        },
    )

    rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user").value,
            "rule_id": access_request_rule.id,
        },
    )
    yield access_request_policy
    try:
        rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_request_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_request_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def policy_drp_action(
    db: Session,
    oauth_client: ClientDetail,
    storage_config: StorageConfig,
) -> Generator:
    access_request_policy = Policy.create(
        db=db,
        data={
            "name": "example access request policy drp",
            "key": "example_access_request_policy_drp",
            "drp_action": "access",
            "client_id": oauth_client.id,
        },
    )

    access_request_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.access.value,
            "client_id": oauth_client.id,
            "name": "Access Request Rule DRP",
            "policy_id": access_request_policy.id,
            "storage_destination_id": storage_config.id,
        },
    )

    rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user").value,
            "rule_id": access_request_rule.id,
        },
    )
    yield access_request_policy
    try:
        rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_request_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        access_request_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def policy_drp_action_erasure(db: Session, oauth_client: ClientDetail) -> Generator:
    erasure_request_policy = Policy.create(
        db=db,
        data={
            "name": "example erasure request policy drp",
            "key": "example_erasure_request_policy_drp",
            "drp_action": "deletion",
            "client_id": oauth_client.id,
        },
    )

    erasure_request_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "Erasure Request Rule DRP",
            "policy_id": erasure_request_policy.id,
            "masking_strategy": {
                "strategy": StringRewriteMaskingStrategy.name,
                "configuration": {"rewrite_value": "MASKED"},
            },
        },
    )

    rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user").value,
            "rule_id": erasure_request_rule.id,
        },
    )
    yield erasure_request_policy
    try:
        rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_request_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_request_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def erasure_policy_string_rewrite(
    db: Session,
    oauth_client: ClientDetail,
    storage_config: StorageConfig,
) -> Generator:
    erasure_policy = Policy.create(
        db=db,
        data={
            "name": "string rewrite policy",
            "key": "string_rewrite_policy",
            "client_id": oauth_client.id,
        },
    )

    erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "string rewrite erasure rule",
            "policy_id": erasure_policy.id,
            "masking_strategy": {
                "strategy": StringRewriteMaskingStrategy.name,
                "configuration": {"rewrite_value": "MASKED"},
            },
        },
    )

    erasure_rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.name").value,
            "rule_id": erasure_rule.id,
        },
    )

    yield erasure_policy
    try:
        erasure_rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def erasure_policy_string_rewrite_name_and_email(
    db: Session,
    oauth_client: ClientDetail,
    storage_config: StorageConfig,
) -> Generator:
    erasure_policy = Policy.create(
        db=db,
        data={
            "name": "string rewrite policy",
            "key": "string_rewrite_policy",
            "client_id": oauth_client.id,
        },
    )

    erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "string rewrite erasure rule",
            "policy_id": erasure_policy.id,
            "masking_strategy": {
                "strategy": StringRewriteMaskingStrategy.name,
                "configuration": {"rewrite_value": "MASKED"},
            },
        },
    )

    erasure_rule_target_name = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.name").value,
            "rule_id": erasure_rule.id,
        },
    )

    erasure_rule_target_email = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.contact.email").value,
            "rule_id": erasure_rule.id,
        },
    )

    yield erasure_policy
    try:
        erasure_rule_target_name.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_rule_target_email.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def erasure_policy_hmac(
    db: Session,
    oauth_client: ClientDetail,
    storage_config: StorageConfig,
) -> Generator:
    erasure_policy = Policy.create(
        db=db,
        data={
            "name": "hmac policy",
            "key": "hmac_policy",
            "client_id": oauth_client.id,
        },
    )

    erasure_rule = Rule.create(
        db=db,
        data={
            "action_type": ActionType.erasure.value,
            "client_id": oauth_client.id,
            "name": "hmac erasure rule",
            "policy_id": erasure_policy.id,
            "masking_strategy": {
                "strategy": HmacMaskingStrategy.name,
                "configuration": {},
            },
        },
    )

    erasure_rule_target = RuleTarget.create(
        db=db,
        data={
            "client_id": oauth_client.id,
            "data_category": DataCategory("user.name").value,
            "rule_id": erasure_rule.id,
        },
    )

    yield erasure_policy
    try:
        erasure_rule_target.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_rule.delete(db)
    except ObjectDeletedError:
        pass
    try:
        erasure_policy.delete(db)
    except ObjectDeletedError:
        pass


@pytest.fixture(scope="function")
def privacy_requests(db: Session, policy: Policy) -> Generator:
    privacy_requests = []
    for count in range(3):
        privacy_requests.append(
            PrivacyRequest.create(
                db=db,
                data={
                    "external_id": f"ext-{str(uuid4())}",
                    "started_processing_at": datetime.utcnow(),
                    "requested_at": datetime.utcnow() - timedelta(days=1),
                    "status": PrivacyRequestStatus.in_processing,
                    "origin": f"https://example.com/{count}/",
                    "policy_id": policy.id,
                    "client_id": policy.client_id,
                },
            )
        )
    yield privacy_requests
    for pr in privacy_requests:
        pr.delete(db)


def _create_privacy_request_for_policy(
    db: Session,
    policy: Policy,
    status: PrivacyRequestStatus = PrivacyRequestStatus.in_processing,
    email_identity: Optional[str] = "test@example.com",
) -> PrivacyRequest:
    data = {
        "external_id": f"ext-{str(uuid4())}",
        "requested_at": datetime(
            2018,
            12,
            31,
            hour=2,
            minute=30,
            second=23,
            microsecond=916482,
            tzinfo=timezone.utc,
        ),
        "status": status,
        "origin": f"https://example.com/",
        "policy_id": policy.id,
        "client_id": policy.client_id,
    }
    if status != PrivacyRequestStatus.pending:
        data["started_processing_at"] = datetime(
            2019,
            1,
            1,
            hour=1,
            minute=45,
            second=55,
            microsecond=393185,
            tzinfo=timezone.utc,
        )
    pr = PrivacyRequest.create(
        db=db,
        data=data,
    )
    identity_kwargs = {"email": email_identity}
    pr.cache_identity(identity_kwargs)
    pr.persist_identity(
        db=db,
        identity=Identity(
            email=email_identity,
            phone_number="+12345678910",
        ),
    )
    return pr


@pytest.fixture(scope="function")
def privacy_request(db: Session, policy: Policy) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        policy,
    )
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def privacy_request_with_erasure_policy(
    db: Session, erasure_policy: Policy
) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        erasure_policy,
    )
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def privacy_request_with_consent_policy(
    db: Session, consent_policy: Policy
) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        consent_policy,
    )
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def privacy_request_requires_input(db: Session, policy: Policy) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        policy,
    )
    privacy_request.status = PrivacyRequestStatus.requires_input
    privacy_request.save(db)
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def privacy_request_awaiting_consent_email_send(
    db: Session, consent_policy: Policy
) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        consent_policy,
    )
    privacy_request.status = PrivacyRequestStatus.awaiting_email_send
    privacy_request.save(db)
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def privacy_request_awaiting_erasure_email_send(
    db: Session, erasure_policy: Policy
) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        erasure_policy,
    )
    privacy_request.status = PrivacyRequestStatus.awaiting_email_send
    privacy_request.save(db)
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def audit_log(db: Session, privacy_request) -> PrivacyRequest:
    audit_log = AuditLog.create(
        db=db,
        data={
            "user_id": "system",
            "privacy_request_id": privacy_request.id,
            "action": AuditLogAction.approved,
            "message": "",
        },
    )
    yield audit_log
    audit_log.delete(db)


@pytest.fixture(scope="function")
def privacy_request_status_pending(db: Session, policy: Policy) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        policy,
        PrivacyRequestStatus.pending,
    )
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def privacy_request_status_canceled(db: Session, policy: Policy) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        policy,
        PrivacyRequestStatus.canceled,
    )
    privacy_request.started_processing_at = None
    privacy_request.save(db)
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def privacy_request_with_drp_action(
    db: Session, policy_drp_action: Policy
) -> PrivacyRequest:
    privacy_request = _create_privacy_request_for_policy(
        db,
        policy_drp_action,
    )
    yield privacy_request
    privacy_request.delete(db)


@pytest.fixture(scope="function")
def succeeded_privacy_request(cache, db: Session, policy: Policy) -> PrivacyRequest:
    pr = PrivacyRequest.create(
        db=db,
        data={
            "external_id": f"ext-{str(uuid4())}",
            "started_processing_at": datetime(2021, 10, 1),
            "finished_processing_at": datetime(2021, 10, 3),
            "requested_at": datetime(2021, 10, 1),
            "status": PrivacyRequestStatus.complete,
            "origin": f"https://example.com/",
            "policy_id": policy.id,
            "client_id": policy.client_id,
        },
    )
    identity_kwargs = {"email": "email@example.com"}
    pr.cache_identity(identity_kwargs)
    pr.persist_identity(
        db=db,
        identity=Identity(**identity_kwargs),
    )
    yield pr
    pr.delete(db)


@pytest.fixture(scope="function")
def failed_privacy_request(db: Session, policy: Policy) -> PrivacyRequest:
    pr = PrivacyRequest.create(
        db=db,
        data={
            "external_id": f"ext-{str(uuid4())}",
            "started_processing_at": datetime(2021, 1, 1),
            "finished_processing_at": datetime(2021, 1, 2),
            "requested_at": datetime(2020, 12, 31),
            "status": PrivacyRequestStatus.error,
            "origin": f"https://example.com/",
            "policy_id": policy.id,
            "client_id": policy.client_id,
        },
    )
    yield pr
    pr.delete(db)


@pytest.fixture(scope="function")
def privacy_notice(db: Session) -> Generator:
    privacy_notice = PrivacyNotice.create(
        db=db,
        data={
            "name": "example privacy notice",
            "description": "a sample privacy notice configuration",
            "origin": "privacy_notice_template_1",
            "regions": [
                PrivacyNoticeRegion.us_ca,
                PrivacyNoticeRegion.us_co,
            ],
            "consent_mechanism": ConsentMechanism.opt_in,
            "data_uses": ["advertising", "third_party_sharing"],
            "enforcement_level": EnforcementLevel.system_wide,
        },
    )

    yield privacy_notice


@pytest.fixture(scope="function")
def privacy_notice_us_ca_provide(db: Session) -> Generator:
    privacy_notice = PrivacyNotice.create(
        db=db,
        data={
            "name": "example privacy notice us_ca provide",
            # no description or origin on this privacy notice to help
            # cover edge cases due to column nullability
            "regions": [PrivacyNoticeRegion.us_ca],
            "consent_mechanism": ConsentMechanism.opt_in,
            "data_uses": ["provide"],
            "enforcement_level": EnforcementLevel.system_wide,
        },
    )

    yield privacy_notice


@pytest.fixture(scope="function")
def privacy_notice_us_co_third_party_sharing(db: Session) -> Generator:
    privacy_notice = PrivacyNotice.create(
        db=db,
        data={
            "name": "example privacy notice us_co third_party_sharing",
            "description": "a sample privacy notice configuration",
            "origin": "privacy_notice_template_2",
            "regions": [PrivacyNoticeRegion.us_co],
            "consent_mechanism": ConsentMechanism.opt_in,
            "data_uses": ["third_party_sharing"],
            "enforcement_level": EnforcementLevel.system_wide,
        },
    )

    yield privacy_notice


@pytest.fixture(scope="function")
def ctl_dataset(db: Session, example_datasets):
    ds = Dataset(
        fides_key="postgres_example_subscriptions_dataset",
        organization_fides_key="default_organization",
        name="Postgres Example Subscribers Dataset",
        description="Example Postgres dataset created in test fixtures",
        data_qualifier="aggregated.anonymized.unlinked_pseudonymized.pseudonymized.identified",
        retention="No retention or erasure policy",
        collections=[
            {
                "name": "subscriptions",
                "fields": [
                    {
                        "name": "id",
                        "data_categories": ["system.operations"],
                    },
                    {
                        "name": "email",
                        "data_categories": ["user.contact.email"],
                        "fidesops_meta": {
                            "identity": "email",
                        },
                    },
                ],
            },
        ],
    )
    dataset = CtlDataset(**ds.dict())
    db.add(dataset)
    db.commit()
    yield dataset
    dataset.delete(db)


@pytest.fixture(scope="function")
def dataset_config(
    connection_config: ConnectionConfig,
    ctl_dataset,
    db: Session,
) -> Generator:
    dataset_config = DatasetConfig.create(
        db=db,
        data={
            "connection_config_id": connection_config.id,
            "fides_key": "postgres_example_subscriptions_dataset",
            "ctl_dataset_id": ctl_dataset.id,
        },
    )
    yield dataset_config
    dataset_config.delete(db)


@pytest.fixture(scope="function")
def dataset_config_preview(
    connection_config: ConnectionConfig, db: Session, ctl_dataset
) -> Generator:
    ctl_dataset.fides_key = "postgres"
    db.add(ctl_dataset)
    db.commit()
    dataset_config = DatasetConfig.create(
        db=db,
        data={
            "connection_config_id": connection_config.id,
            "fides_key": "postgres",
            "ctl_dataset_id": ctl_dataset.id,
        },
    )
    yield dataset_config
    dataset_config.delete(db)


def load_dataset(filename: str) -> Dict:
    yaml_file = load_file([filename])
    with open(yaml_file, "r") as file:
        return yaml.safe_load(file).get("dataset", [])


def load_dataset_as_string(filename: str) -> str:
    yaml_file = load_file([filename])
    with open(yaml_file, "r") as file:
        return file.read()


@pytest.fixture
def example_datasets() -> List[Dict]:
    example_datasets = []
    example_filenames = [
        "data/dataset/postgres_example_test_dataset.yml",
        "data/dataset/mongo_example_test_dataset.yml",
        "data/dataset/snowflake_example_test_dataset.yml",
        "data/dataset/redshift_example_test_dataset.yml",
        "data/dataset/mssql_example_test_dataset.yml",
        "data/dataset/mysql_example_test_dataset.yml",
        "data/dataset/mariadb_example_test_dataset.yml",
        "data/dataset/bigquery_example_test_dataset.yml",
        "data/dataset/manual_dataset.yml",
        "data/dataset/email_dataset.yml",
        "data/dataset/remote_fides_example_test_dataset.yml",
    ]
    for filename in example_filenames:
        example_datasets += load_dataset(filename)
    return example_datasets


@pytest.fixture
def example_yaml_datasets() -> str:
    example_filename = "data/dataset/example_test_datasets.yml"
    return load_dataset_as_string(example_filename)


@pytest.fixture
def example_yaml_dataset() -> str:
    example_filename = "data/dataset/postgres_example_test_dataset.yml"
    return load_dataset_as_string(example_filename)


@pytest.fixture
def example_invalid_yaml_dataset() -> str:
    example_filename = "data/dataset/example_test_dataset.invalid"
    return load_dataset_as_string(example_filename)


@pytest.fixture(scope="function")
def sample_data():
    return {
        "_id": 12345,
        "thread": [
            {
                "comment": "com_0001",
                "message": "hello, testing in-flight chat feature",
                "chat_name": "John",
                "messages": {},
            },
            {
                "comment": "com_0002",
                "message": "yep, got your message, looks like it works",
                "chat_name": "Jane",
            },
            {"comment": "com_0002", "message": "hello!", "chat_name": "Jeanne"},
        ],
        "snacks": ["pizza", "chips"],
        "seats": {"first_choice": "A2", "second_choice": "B3"},
        "upgrades": {
            "magazines": ["Time", "People"],
            "books": ["Once upon a Time", "SICP"],
            "earplugs": True,
        },
        "other_flights": [
            {"DFW": ["11 AM", "12 PM"], "CHO": ["12 PM", "1 PM"]},
            {"DFW": ["2 AM", "12 PM"], "CHO": ["2 PM", "1 PM"]},
            {"DFW": ["3 AM", "2 AM"], "CHO": ["2 PM", "1:30 PM"]},
        ],
        "months": {
            "july": [
                {
                    "activities": ["swimming", "hiking"],
                    "crops": ["watermelon", "cheese", "grapes"],
                },
                {"activities": ["tubing"], "crops": ["corn"]},
            ],
            "march": [
                {
                    "activities": ["skiing", "bobsledding"],
                    "crops": ["swiss chard", "swiss chard"],
                },
                {"activities": ["hiking"], "crops": ["spinach"]},
            ],
        },
        "hello": [1, 2, 3, 4, 2],
        "weights": [[1, 2], [3, 4]],
        "toppings": [[["pepperoni", "salami"], ["pepperoni", "cheese", "cheese"]]],
        "A": {"C": [{"M": ["p", "n", "n"]}]},
        "C": [["A", "B", "C", "B"], ["G", "H", "B", "B"]],  # Double lists
        "D": [
            [["A", "B", "C", "B"], ["G", "H", "B", "B"]],
            [["A", "B", "C", "B"], ["G", "H", "B", "B"]],
        ],  # Triple lists
        "E": [[["B"], [["A", "B", "C", "B"], ["G", "H", "B", "B"]]]],  # Irregular lists
        "F": [
            "a",
            ["1", "a", [["z", "a", "a"]]],
        ],  # Lists elems are different types, not officially supported
    }


@pytest.fixture(scope="function")
def application_user(
    db,
    oauth_client,
) -> FidesUser:
    unique_username = f"user-{uuid4()}"
    user = FidesUser.create(
        db=db,
        data={
            "username": unique_username,
            "password": "test_password",
            "first_name": "Test",
            "last_name": "User",
        },
    )
    oauth_client.user_id = user.id
    oauth_client.save(db=db)
    yield user
    user.delete(db=db)


@pytest.fixture(scope="function")
def short_redis_cache_expiration():
    original_value: int = CONFIG.redis.default_ttl_seconds
    CONFIG.redis.default_ttl_seconds = (
        1  # Set redis cache to expire very quickly for testing purposes
    )
    yield CONFIG
    CONFIG.redis.default_ttl_seconds = original_value


@pytest.fixture(scope="function")
def user_registration_opt_out(db: Session) -> UserRegistration:
    """Adds a UserRegistration record with `opt_in` as False."""
    return create_user_registration(db, opt_in=False)


@pytest.fixture(scope="function")
def user_registration_opt_in(db: Session) -> UserRegistration:
    """Adds a UserRegistration record with `opt_in` as True."""
    return create_user_registration(db, opt_in=True)


def create_user_registration(db: Session, opt_in: bool = False) -> UserRegistration:
    """Adds a UserRegistration record."""
    return UserRegistration.create(
        db=db,
        data={
            "user_email": "user@example.com",
            "user_organization": "Example Org.",
            "analytics_id": "example-analytics-id",
            "opt_in": opt_in,
        },
    )


@pytest.fixture(scope="function")
def test_fides_client(
    fides_connector_example_secrets: Dict[str, str], api_client
) -> FidesClient:
    return FidesClient(
        fides_connector_example_secrets["uri"],
        fides_connector_example_secrets["username"],
        fides_connector_example_secrets["password"],
        fides_connector_example_secrets["polling_timeout"],
    )


@pytest.fixture(scope="function")
def authenticated_fides_client(
    test_fides_client: FidesClient,
) -> FidesClient:
    test_fides_client.login()
    return test_fides_client


@pytest.fixture(scope="function")
def system_manager(db: Session, system) -> System:
    user = FidesUser.create(
        db=db,
        data={
            "username": "test_system_manager_user",
            "password": "TESTdcnG@wzJeu0&%3Qe2fGo7",
        },
    )
    client = ClientDetail(
        hashed_secret="thisisatest",
        salt="thisisstillatest",
        scopes=[],
        roles=[VIEWER],
        user_id=user.id,
        systems=[system.id],
    )

    FidesUserPermissions.create(db=db, data={"user_id": user.id, "roles": [VIEWER]})

    db.add(client)
    db.commit()
    db.refresh(client)

    user.set_as_system_manager(db, system)
    yield user
    try:
        user.remove_as_system_manager(db, system)
    except (SystemManagerException, StaleDataError):
        pass
    user.delete(db)


@pytest.fixture(scope="function")
def provided_identity_and_consent_request(db):
    provided_identity_data = {
        "privacy_request_id": None,
        "field_name": "email",
        "hashed_value": ProvidedIdentity.hash_value("test@email.com"),
        "encrypted_value": {"value": "test@email.com"},
    }
    provided_identity = ProvidedIdentity.create(db, data=provided_identity_data)

    consent_request_data = {
        "provided_identity_id": provided_identity.id,
    }
    consent_request = ConsentRequest.create(db, data=consent_request_data)

    yield provided_identity, consent_request
    provided_identity.delete(db=db)
    consent_request.delete(db=db)


@pytest.fixture(scope="function")
def executable_consent_request(
    db,
    provided_identity_and_consent_request,
    consent_policy,
):
    provided_identity = provided_identity_and_consent_request[0]
    consent_request = provided_identity_and_consent_request[1]
    privacy_request = _create_privacy_request_for_policy(
        db,
        consent_policy,
    )
    consent_request.privacy_request_id = privacy_request.id
    consent_request.save(db)
    provided_identity.privacy_request_id = privacy_request.id
    provided_identity.save(db)
    yield privacy_request
    privacy_request.delete(db)
