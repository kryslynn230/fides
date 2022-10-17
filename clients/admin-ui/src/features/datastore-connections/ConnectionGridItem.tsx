import { Box, Button, Flex, Spacer, Text } from "@fidesui/react";
import { formatDate } from "common/utils";
import React from "react";

import ConnectionMenu from "./ConnectionMenu";
import ConnectionStatusBadge from "./ConnectionStatusBadge";
import ConnectionTypeLogo from "./ConnectionTypeLogo";
import { useLazyGetDatastoreConnectionStatusQuery } from "./datastore-connection.slice";
import { DatastoreConnection } from "./types";

type TestDataProps = {
  succeeded: boolean | null;
  timestamp: string;
};

const TestData: React.FC<TestDataProps> = ({ succeeded, timestamp }) => {
  let testCircleColor = succeeded ? "green.500" : "red.500";
  if (succeeded === null) {
    testCircleColor = "gray.300";
  }

  const date = formatDate(timestamp);
  const testText = timestamp
    ? `Last tested on ${date}`
    : "This datastore has not been tested yet";

  return (
    <>
      <Box
        width="12px"
        height="12px"
        borderRadius="6px"
        backgroundColor={testCircleColor}
      />
      <Text
        color="gray.500"
        fontSize="xs"
        fontWeight="semibold"
        lineHeight="16px"
        ml="10px"
      >
        {testText}
      </Text>
    </>
  );
};

type ConnectionGridItemProps = {
  connectionData: DatastoreConnection;
};

const ConnectionGridItem: React.FC<ConnectionGridItemProps> = ({
  connectionData,
}) => {
  const [trigger, result] = useLazyGetDatastoreConnectionStatusQuery();

  return (
    <Box width="100%" height={136} p="18px 16px 16px 16px">
      <Flex justifyContent="center" alignItems="center">
        <ConnectionTypeLogo data={connectionData} />
        <Text
          color="gray.900"
          fontSize="md"
          fontWeight="medium"
          m="8px"
          textOverflow="ellipsis"
          overflow="hidden"
          whiteSpace="nowrap"
        >
          {connectionData.name}
        </Text>
        <Spacer />
        <ConnectionStatusBadge disabled={connectionData.disabled} />
        <ConnectionMenu
          connection_key={connectionData.key}
          disabled={connectionData.disabled}
          name={connectionData.name}
          connection_type={connectionData.connection_type}
          access_type={connectionData.access}
        />
      </Flex>
      <Text color="gray.600" fontSize="sm" fontWeight="sm" lineHeight="20px">
        {/* If description is empty display empty placeholder */}
        {connectionData.description ? connectionData.description : <br />}
      </Text>
      <Text color="gray.600" fontSize="sm" fontWeight="sm" lineHeight="20px">
        Edited on {formatDate(connectionData.updated_at!)}
      </Text>

      <Flex mt="0px" justifyContent="center" alignItems="center">
        <TestData
          succeeded={connectionData.last_test_succeeded}
          timestamp={connectionData.last_test_timestamp}
        />
        <Spacer />
        <Button
          size="xs"
          variant="outline"
          onClick={() => {
            trigger(connectionData.key);
          }}
          loadingText="Test"
          isLoading={result.isLoading || result.isFetching}
          spinnerPlacement="end"
        >
          Test
        </Button>
      </Flex>
    </Box>
  );
};

export default ConnectionGridItem;
