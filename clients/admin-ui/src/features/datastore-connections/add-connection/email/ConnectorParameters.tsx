import { Box } from "@fidesui/react";
import { ConnectionTypeSecretSchemaReponse } from "connection-type/types";
import React from "react";

import { useDatabaseConnector } from "~/features/datastore-connections/add-connection/database/ConnectorParameters";
import ConnectorParametersForm from "~/features/datastore-connections/add-connection/forms/ConnectorParametersForm";
import { EmailConnectorParametersFormFields } from "~/features/datastore-connections/add-connection/types";

type ConnectorParametersProps = {
  data: ConnectionTypeSecretSchemaReponse;
  /**
   * Parent callback invoked when a connection is initially created
   */
  onConnectionCreated?: () => void;
  /**
   * Parent callback when Test Email is clicked
   */
  onTestEmail: (value: any) => void;
};

const DEFAULT_VALUES: EmailConnectorParametersFormFields = {
  description: "",
  instance_key: "",
  name: "",
};

/**
 * We do not support advanced settings in the UI yet, but the backend requires at least
 * a payload that looks like it. We stuff one into handleSubmit for now
 * See fides#2458
 */
const STUBBED_ADVANCED_SETTINGS = {
  advanced_settings: {
    identity_types: {
      email: false,
      phone_number: false,
      cookie_ids: [],
    },
  },
};

export const ConnectorParameters: React.FC<ConnectorParametersProps> = ({
  data,
  onConnectionCreated,
  onTestEmail,
}) => {
  const {
    connectionOption,
    isSubmitting,
    handleSubmit: onSubmit,
  } = useDatabaseConnector({ onConnectionCreated, data });

  const handleSubmit = (values: EmailConnectorParametersFormFields) => {
    onSubmit({ ...values, ...STUBBED_ADVANCED_SETTINGS });
  };

  return (
    <>
      <Box color="gray.700" fontSize="14px" h="80px">
        Configure your {connectionOption!.human_readable} connector by providing
        the connector name, description and a test email address. Once you have
        saved the details, you can click test email to check the format of the
        email.
      </Box>
      <ConnectorParametersForm
        data={data}
        defaultValues={DEFAULT_VALUES}
        isSubmitting={isSubmitting}
        onSaveClick={handleSubmit}
        onTestConnectionClick={onTestEmail}
        testButtonLabel="Test email"
      />
    </>
  );
};
