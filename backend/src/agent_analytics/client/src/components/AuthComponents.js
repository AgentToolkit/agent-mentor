import React, { createContext, useContext, useState, useEffect } from "react";

// Create Authentication Context
const AuthContext = createContext(null);

// Storage wrapper with fallback
export const storage = {
  getItem(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      try {
        return sessionStorage.getItem(key);
      } catch (e2) {
        console.warn("Both localStorage and sessionStorage are unavailable:", e2);
        return null;
      }
    }
  },

  setItem(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (e) {
      try {
        sessionStorage.setItem(key, value);
      } catch (e2) {
        console.warn("Both localStorage and sessionStorage are unavailable:", e2);
      }
    }
  },

  removeItem(key) {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      try {
        sessionStorage.removeItem(key);
      } catch (e2) {
        console.warn("Both localStorage and sessionStorage are unavailable:", e2);
      }
    }
  },

  // New method to handle service history
  addServiceToHistory(serviceName) {
    if (!serviceName) return;

    try {
      // Get current service history
      const historyString = this.getItem("serviceNameHistory") || "[]";
      let history = JSON.parse(historyString);

      // Remove the service if it already exists (to avoid duplicates)
      history = history.filter((name) => name !== serviceName);

      // Add the new service to the beginning of the array
      history.unshift(serviceName);

      // Keep only the most recent 10 services
      if (history.length > 10) {
        history = history.slice(0, 10);
      }

      // Save the updated history
      this.setItem("serviceNameHistory", JSON.stringify(history));
    } catch (e) {
      console.warn("Error updating service history:", e);
    }
  },

  // Get service history
  getServiceHistory() {
    try {
      const historyString = this.getItem("serviceNameHistory") || "[]";
      return JSON.parse(historyString);
    } catch (e) {
      console.warn("Error retrieving service history:", e);
      return [];
    }
  },
};

// Auth Provider Component
export const AuthProvider = ({ isEmbedded, children, tenantId, serverUrl }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authMode, setAuthMode] = useState(null); // 'bypass', 'local', 'saml'
  const [embedStr, setEmbedStr] = useState("");

  const logout = async () => {
    try {
      await fetch(`${serverUrl}/auth/logout`, {
        credentials: "include",
        headers: {
          "Cache-Control": "no-cache, no-store, must-revalidate",
          Pragma: "no-cache",
          "x-tenant-id": tenantId,
        },
      });

      // Clear any client-side state
      setUser(null);

      // Force clear any cached auth state
      window.location.href = "/";

      // Wait a moment to ensure cookie clearing takes effect
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Force reload to ensure fresh state
      window.location.reload(true);
    } catch (error) {
      console.error("Logout error:", error);
      // Even if there's an error, try to clear state
      setUser(null);
      window.location.href = "/";
    }
  };

  // Check auth mode from server
  useEffect(() => {
    const checkAuthMode = async () => {
      try {
        const response = await fetch(`${serverUrl}/auth/mode`, {
          credentials: "include",
          headers: {
            "x-tenant-id": tenantId,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setAuthMode(data.mode);
          console.log("Auth mode:", data.mode);
        }
      } catch (error) {
        console.error("Error checking auth mode:", error);
        // Default to SAML mode if we can't determine
        setAuthMode("saml");
      }
    };

    checkAuthMode();
  }, [serverUrl, tenantId]);

  // Effect to validate session and fetch user data
  useEffect(() => {
    const validateSession = async () => {
      try {
        setEmbedStr(isEmbedded ? "?embed=true" : "");

        // If auth is bypassed, create a mock user and skip validation
        if (authMode === "bypass") {
          console.log("Auth bypass mode detected - creating bypass user");
          setUser({
            username: "bypass_user",
            email: "bypass@system.local",
            full_name: "Bypass User",
          });
          setLoading(false);
          return;
        }

        // For other modes, validate session normally
        const userResponse = await fetch(`${serverUrl}/users/me${embedStr}`, {
          credentials: "include", // Important: includes cookies in the request
          headers: {
            "x-tenant-id": tenantId,
          },
        });

        if (userResponse.ok) {
          const userData = await userResponse.json();
          setUser(userData);
        }
      } catch (error) {
        console.error("Session validation error:", error);
      }
      setLoading(false);
    };

    // Only validate session if we know the auth mode
    if (authMode !== null) {
      validateSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverUrl, isEmbedded, authMode]); // Added authMode as dependency

  const initiateLogin = () => {
    // Redirect to SAML login endpoint
    window.location.href = `${serverUrl}/saml/login${embedStr}`;
  };

  // Helper function for making authenticated API calls
  const authFetch = async (url, options = {}) => {
    try {
      if (!options["headers"]) {
        options["headers"] = {};
      }
      options["headers"]["x-tenant-id"] = tenantId;
      const response = await fetch(`${url}${embedStr}`, {
        ...options,
        credentials: "include", // Always include cookies
      });

      // In bypass mode, don't redirect on 401 as auth isn't required
      if (response.status === 401 && authMode !== "bypass") {
        // Session expired
        setUser(null);
        window.location.href = "/"; // Redirect to login
        throw new Error("Session expired");
      }

      return response;
    } catch (error) {
      throw error;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-16 h-16 border-4 border-t-blue-500 border-blue-200 rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, initiateLogin, logout, authFetch, authMode }}>{children}</AuthContext.Provider>
  );
};

// Custom Hook for using Authentication
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

// Login Form Component (Simplified for SSO and supports localhost)
export const LoginForm = ({ propError, tenantId }) => {
  const [serverUrl] = useState(
    storage.getItem("serverUrl") ||
      (window.location.port >= "3000" && window.location.port <= "3010"
        ? window.location.protocol + "//" + window.location.hostname
        : "")
  );
  const [isLocal, setIsLocal] = useState(process.env.NODE_ENV === "development" || window.ENV?.TEST === "true");
  const [error, setError] = useState(propError);

  // Check URL parameters for error messages on component mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const errorMessage = urlParams.get("error");
    if (errorMessage) {
      setError(decodeURIComponent(errorMessage));
    }
  }, []);

  useEffect(() => {
    setIsLocal(process.env.NODE_ENV === "development" || window.ENV?.TEST === "true");
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      if (isLocal && e.target.username) {
        const formData = new FormData();
        formData.append("username", e.target.username.value);

        const response = await fetch(`${serverUrl}/auth/login`, {
          method: "POST",
          body: formData,
          credentials: "include",
          headers: {
            "x-tenant-id": tenantId,
          },
        });

        if (response.ok) {
          window.location.href = "/";
        } else {
          const data = await response.json();
          setError(data.detail || "Login failed");
        }
      } else {
        // For SSO login, use direct navigation instead of fetch
        window.location.href = `${serverUrl}/auth/login`;
      }
    } catch (err) {
      setError("Login service unavailable. Please try again later.");
    }
  };

  return (
    <div className="w-full max-w-md mx-auto mt-8 p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6 text-center">
        Agent Analytics Dashboard<br></br>Sign-in
      </h2>

      {error && <div className="p-3 mb-4 bg-red-100 text-red-700 rounded-md">{error}</div>}

      {isLocal ? (
        // Local development login form
        <form onSubmit={handleSubmit} className="space-y-4" data-testid="login-form">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-700">
              (Local Server): Enter any name below and click "Login"
              <br></br>
              <br></br>
              Name:
            </label>
            <input
              data-testid="username-input"
              type="text"
              id="username"
              name="username"
              className="mt-1 block w-full rounded-md border-blue-300 bg-gray-100 shadow focus:border-blue-500 focus:ring-blue-500"
              required
            />
          </div>

          <button
            data-testid="login-button"
            type="submit"
            className="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            Login (Local)
          </button>
        </form>
      ) : (
        // Production SAML login
        <div className="space-y-4">
          <div className="space-y-3">
            <div className="flex items-start">
              <div className="flex items-center h-5"></div>
              <label className="ml-3 text text-gray-700">
                <span className="font-bold">New Users?</span>
                <br></br>
                In order to access the application, please complete the{" "}
                <a
                  href="https://forms.office.com/r/BVWnRakNF3"
                  target="new"
                  class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
                >
                  Research Survey
                </a>
                .<br></br>
                <br></br>
                <br></br>
                <span className="font-bold">Research Use Disclaimer</span>
                <br></br>
                This system is a Research Asset and is intended for internal evaluation purposes only.
                <br></br>
                <br></br>
                Please do not upload any of the following:
                <br></br>
                Client confidential information, Personally Identifiable Information (PII), and any other sensitive or
                regulated data.
                <br></br>
                Note: Agent traces include end-user requests and LLM-generated responses. These must not contain any of
                the above data types.
                <br></br>
                <br></br>
                <span className="font-bold">
                  By signing in, you acknowledge that you comply with these usage guidelines.
                </span>
                <br></br>
              </label>
            </div>

            <button
              onClick={handleSubmit}
              className="w-full py-3 px-4 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors bg-blue-600 text-white hover:bg-blue-700"
            >
              Sign in with SSO
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
