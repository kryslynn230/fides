/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { MessagingServiceDetailsMailchimpTransactional } from "./MessagingServiceDetailsMailchimpTransactional";
import type { MessagingServiceDetailsMailgun } from "./MessagingServiceDetailsMailgun";
import type { MessagingServiceDetailsTwilioEmail } from "./MessagingServiceDetailsTwilioEmail";
import type { MessagingServiceType } from "./MessagingServiceType";

/**
 * Messaging Config Response Schema
 */
export type MessagingConfigResponse = {
  service_type: MessagingServiceType;
  details?:
    | MessagingServiceDetailsMailgun
    | MessagingServiceDetailsTwilioEmail
    | MessagingServiceDetailsMailchimpTransactional;
  name: string;
  key: string;
};
