// WorkflowsPage.js
import { useState } from "react";
import { AuthProvider, useAuth, storage } from "../components/AuthComponents";
import { WorkflowsContent } from "./WorkflowsComponents";
import { LoginForm } from "../components/AuthComponents";

const WorkflowsPage = ({ setTenantId, tenantId, serverUrl }) => {
  const { user, authMode } = useAuth();
  const [isEmbedded] = useState(true); // This page is designed to be embedded as an iframe

  // Show login form only if no user is logged in and not in bypass mode
  if (!user && !isEmbedded && authMode !== "bypass") {
    return <LoginForm propError={null} tenantId={tenantId} />;
  }

  return (
    <WorkflowsContent
      serverUrl={serverUrl} setTenantId={setTenantId} tenant_id={tenantId}
    />
  );
};

// Wrap the export with AuthProvider
const WorkflowsPageWithAuth = () => {
  const [isEmbedded] = useState(true);
  const [tenantId, setTenantId] = useState("");
  const [serverUrl] = useState(
    storage.getItem("serverUrl") ||
      (window.location.port >= "3000" && window.location.port <= "3010"
        ? window.location.protocol + "//" + window.location.hostname + ":8765"
        : "")
  );

  return (
    <AuthProvider isEmbedded={isEmbedded} tenantId={tenantId} serverUrl={serverUrl}>
      <WorkflowsPage
        setTenantId={setTenantId}
        tenantId={tenantId}
        serverUrl={serverUrl}
      />
    </AuthProvider>
  );
};

export default WorkflowsPageWithAuth;
