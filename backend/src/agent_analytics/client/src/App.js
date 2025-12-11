// App.js
import React, { useState, useEffect } from "react";
import { AuthProvider, useAuth, storage } from "./components/AuthComponents";
import { MainContent } from "./components/MainComponents";
import { LoginForm } from "./components/AuthComponents";

const App = ({ tenantId, setTenantId, serverUrl, setServerUrl }) => {
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);
  const { user, authMode } = useAuth();
  const [isEmbedded, setIsEmbedded] = useState(false);

  // Add auto-login for embedded mode
  useEffect(() => {
    const autoLogin = async () => {
      if (isEmbedded && !user && authMode !== "bypass") {
        try {
          const serverUrl =
            storage.getItem("serverUrl") ||
            (window.location.port === "3000" ? window.location.protocol + "//" + window.location.hostname : "");

          // Call the auto-login endpoint with the correct server URL
          const response = await fetch(`${serverUrl}/auth/auto-login?embed=true`, {
            method: "POST",
            credentials: "include",
            headers: {
              "x-tenant-id": tenantId,
            },
          });
          if (response.ok) {
            // Instead of immediate redirect, wait a short time for cookie to be set
            await new Promise((resolve) => setTimeout(resolve, 100));
            window.location.href = "/?embed=true";
          } else {
            const errorData = await response.json();
            console.error("Auto-login failed:", errorData);
            setError(errorData.detail || "Auto-login failed");
          }
        } catch (error) {
          console.error("Auto-login error:", error);
          setError("Auto-login failed");
        }
      }
    };
    autoLogin();
  }, [isEmbedded, user, authMode, tenantId]);

  useEffect(() => {
    // Get URL parameters when component mounts
    const queryParams = new URLSearchParams(window.location.search);
    const embedParam = queryParams.get("embed");

    // Convert the parameter to boolean
    setIsEmbedded(embedParam === "true");

    // Check for SAML error message
    const samlError = queryParams.get("error");
    if (samlError) {
      setError(decodeURIComponent(samlError));
      // Clean up the URL
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  // Show login form only if:
  // 1. No user is logged in AND
  // 2. Not in embedded mode AND
  // 3. Not in bypass mode
  if (!user && !isEmbedded && authMode !== "bypass") {
    return <LoginForm propError={error} tenantId={tenantId} />;
  }

  return (
    <MainContent
      data={data}
      setData={setData}
      error={error}
      setError={setError}
      isEmbedded={isEmbedded}
      tenantId={tenantId}
      setTenantId={setTenantId}
      serverUrl={serverUrl}
      setServerUrl={setServerUrl}
    />
  );
};

// Wrap the export with AuthProvider
const AppWithAuth = () => {
  const [isEmbedded, setIsEmbedded] = useState(false);
  const [tenantId, setTenantId] = useState(storage.getItem("tenantId"));
  const [serverUrl, setServerUrl] = useState(
    storage.getItem("serverUrl") ||
      (window.location.port >= "3000" && window.location.port <= "3010"
        ? window.location.protocol + "//" + window.location.hostname + ":8765"
        : "")
  );

  const saveServerUrl = (newServerUrl) => {
    storage.setItem("serverUrl", newServerUrl);
    setServerUrl(newServerUrl);
  };

  useEffect(() => {
    // Get URL parameters when component mounts
    const queryParams = new URLSearchParams(window.location.search);
    const embedParam = queryParams.get("embed");

    // Convert the parameter to boolean
    setIsEmbedded(embedParam === "true");
  }, []);

  return (
    <AuthProvider isEmbedded={isEmbedded} tenantId={tenantId} serverUrl={serverUrl}>
      <App tenantId={tenantId} setTenantId={setTenantId} serverUrl={serverUrl} setServerUrl={saveServerUrl} />
    </AuthProvider>
  );
};

export default AppWithAuth;
