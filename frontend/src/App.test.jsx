import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import api from "./api";

vi.mock("./api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

// Pages are stubbed so these tests assert routing/authorisation only.
vi.mock("./pages/Dashboard", () => ({ default: () => <div>DASHBOARD PAGE</div> }));
vi.mock("./pages/Inbox", () => ({ default: () => <div>INBOX PAGE</div> }));
vi.mock("./pages/AuditLogs", () => ({ default: () => <div>AUDIT PAGE</div> }));
vi.mock("./pages/StaffPortal", () => ({ default: () => <div>STAFF PAGE</div> }));
vi.mock("./pages/ReleaseRequests", () => ({ default: () => <div>REQUESTS PAGE</div> }));
vi.mock("./pages/Login", () => ({ default: () => <div>LOGIN PAGE</div> }));

function signedInAs(role) {
  localStorage.setItem("pg_token", "t");
  localStorage.setItem(
    "pg_user",
    JSON.stringify({ id: 1, email: `${role}@phishguard.local`, role, full_name: "Test User" })
  );
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  localStorage.clear();
});

describe("route protection", () => {
  it("sends an anonymous visitor to the login page", () => {
    renderAt("/dashboard");
    expect(screen.getByText("LOGIN PAGE")).toBeInTheDocument();
  });

  it("sends an anonymous visitor on an unknown path to login", () => {
    renderAt("/nonsense");
    expect(screen.getByText("LOGIN PAGE")).toBeInTheDocument();
  });

  it("lets a signed-in analyst reach the dashboard", () => {
    signedInAs("analyst");
    renderAt("/dashboard");
    expect(screen.getByText("DASHBOARD PAGE")).toBeInTheDocument();
  });

  it("keeps a signed-in user away from the login page", () => {
    signedInAs("analyst");
    renderAt("/login");
    expect(screen.getByText("DASHBOARD PAGE")).toBeInTheDocument();
  });
});

describe("role-based access", () => {
  it("allows an analyst into the inbox", () => {
    signedInAs("analyst");
    renderAt("/inbox");
    expect(screen.getByText("INBOX PAGE")).toBeInTheDocument();
  });

  it("blocks staff from the analyst inbox", () => {
    signedInAs("staff");
    renderAt("/inbox");
    expect(screen.queryByText("INBOX PAGE")).not.toBeInTheDocument();
    expect(screen.getByText("DASHBOARD PAGE")).toBeInTheDocument();
  });

  it("blocks staff from the audit log", () => {
    signedInAs("staff");
    renderAt("/audit");
    expect(screen.queryByText("AUDIT PAGE")).not.toBeInTheDocument();
    expect(screen.getByText("DASHBOARD PAGE")).toBeInTheDocument();
  });

  it("blocks an analyst from the staff-only portal", () => {
    signedInAs("analyst");
    renderAt("/staff");
    expect(screen.queryByText("STAFF PAGE")).not.toBeInTheDocument();
  });

  it("gives admin access to both the analyst and staff areas", () => {
    signedInAs("admin");
    renderAt("/audit");
    expect(screen.getByText("AUDIT PAGE")).toBeInTheDocument();
    cleanupRender();

    signedInAs("admin");
    renderAt("/staff");
    expect(screen.getByText("STAFF PAGE")).toBeInTheDocument();
  });

  it("lets every signed-in role see the release-request queue", () => {
    for (const role of ["staff", "analyst", "admin"]) {
      localStorage.clear();
      signedInAs(role);
      renderAt("/release-requests");
      expect(screen.getByText("REQUESTS PAGE")).toBeInTheDocument();
      cleanupRender();
    }
  });
});

// Test-Library's automatic cleanup runs between test cases, not within one.
function cleanupRender() {
  document.body.innerHTML = "";
}
