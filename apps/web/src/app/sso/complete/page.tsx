"use client";

import { useEffect, useState } from "react";
import { api, isApiError } from "@/lib/api";

const MESSAGES: Record<string, string> = {
  provider_not_configured: "Enterprise sign-in is not configured.",
  sso_rejected: "Enterprise authentication was rejected.",
  replay_detected: "That sign-in request was already used.",
  invalid_state: "The sign-in session expired. Try again.",
  invalid_exchange_code: "The sign-in session expired. Try again.",
  user_inactive: "This account is deactivated.",
  identity_unlinked: "Linking is not permitted for this identity.",
};

export default function SsoCompletePage() {
  const [message, setMessage] = useState("Completing enterprise sign-in…");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const error = params.get("error");
    const exchangeCode = params.get("exchange_code");
    if (error) {
      setMessage(MESSAGES[error] ?? "Enterprise authentication failed.");
      return;
    }
    if (!exchangeCode) {
      setMessage("Missing sign-in exchange code.");
      return;
    }
    void api
      .exchangeSsoCode!(exchangeCode)
      .then(() => {
        window.location.replace("/dashboard");
      })
      .catch((err: unknown) => {
        if (isApiError(err)) {
          setMessage(MESSAGES[err.code ?? ""] ?? err.userMessage());
        } else {
          setMessage("Enterprise authentication failed.");
        }
      });
  }, []);

  return (
    <div
      data-testid="sso-complete-page"
      className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100"
    >
      <p data-testid="sso-complete-message">{message}</p>
    </div>
  );
}
