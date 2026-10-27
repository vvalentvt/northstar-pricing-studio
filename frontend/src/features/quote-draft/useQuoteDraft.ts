import { useContext } from "react";
import { QuoteDraftContext, type QuoteDraftContextValue } from "./QuoteDraftProvider";

export function useQuoteDraft(): QuoteDraftContextValue {
  const context = useContext(QuoteDraftContext);
  if (!context) {
    throw new Error("useQuoteDraft must be used within a QuoteDraftProvider");
  }
  return context;
}
