import React, { useState, useCallback } from "react";
import { useRouter } from "next/router";
import { useLocalStorage } from "~/common/hooks";
import RequestModal from "../RequestModal";

import { ModalViews, VerificationType } from "../types";
import ConsentRequestForm from "./ConsentRequestForm";
import VerificationForm from "../VerificationForm";

export const useConsentRequestModal = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [currentView, setCurrentView] = useState<ModalViews>(
    ModalViews.ConsentRequest
  );
  const router = useRouter();
  const [consentRequestId, setConsentRequestId] = useLocalStorage(
    "consentRequestId",
    ""
  );

  const successHandler = useCallback(() => {
    router.push("consent");
  }, [router]);

  const onOpen = () => {
    setCurrentView(ModalViews.ConsentRequest);
    setIsOpen(true);
  };

  const onClose = () => {
    setIsOpen(false);
    setCurrentView(ModalViews.ConsentRequest);
    setConsentRequestId("");
  };

  return {
    isOpen,
    onClose,
    onOpen,
    currentView,
    setCurrentView,
    consentRequestId,
    setConsentRequestId,
    successHandler,
  };
};

export type ConsentRequestModalProps = {
  isOpen: boolean;
  onClose: () => void;
  currentView: ModalViews;
  setCurrentView: (view: ModalViews) => void;
  consentRequestId: string;
  setConsentRequestId: (id: string) => void;
  isVerificationRequired: boolean;
  successHandler: () => void;
};

export const ConsentRequestModal: React.FC<ConsentRequestModalProps> = ({
  isOpen,
  onClose,
  currentView,
  setCurrentView,
  consentRequestId,
  setConsentRequestId,
  isVerificationRequired,
  successHandler,
}) => {
  let form = null;

  if (currentView === ModalViews.ConsentRequest) {
    form = (
      <ConsentRequestForm
        isOpen={isOpen}
        onClose={onClose}
        setCurrentView={setCurrentView}
        setConsentRequestId={setConsentRequestId}
        isVerificationRequired={isVerificationRequired}
        successHandler={successHandler}
      />
    );
  }

  if (currentView === ModalViews.IdentityVerification) {
    form = (
      <VerificationForm
        isOpen={isOpen}
        onClose={onClose}
        requestId={consentRequestId}
        setCurrentView={setCurrentView}
        resetView={ModalViews.ConsentRequest}
        verificationType={VerificationType.ConsentRequest}
        successHandler={successHandler}
      />
    );
  }

  return (
    <RequestModal isOpen={isOpen} onClose={onClose}>
      {form}
    </RequestModal>
  );
};
