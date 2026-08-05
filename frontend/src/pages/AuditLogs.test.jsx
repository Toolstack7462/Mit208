import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AuditLogs from "./AuditLogs";
import { AuthProvider } from "../context/AuthContext";
import api from "../api";

vi.mock("../api", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("../components/Layout", () => ({
  default: ({ children }) => <div>{children}</div>,
}));

const LOGS = [
  {
    id: 1, actor_email: "analyst@phishguard.local", action: "login",
    entity_type: "user", entity_id: 2, details: "User logged in",
    ip_address: "127.0.0.1", created_at: "2026-08-05T10:00:00Z",
  },
  {
    id: 2, actor_email: "analyst@phishguard.local", action: "quarantine",
    entity_type: "email", entity_id: 5, details: "quarantine on email 'Urgent'",
    ip_address: "127.0.0.1", created_at: "2026-08-05T10:05:00Z",
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <AuditLogs />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  api.get.mockReset();
  localStorage.setItem("pg_user", JSON.stringify({ role: "analyst", email: "a@b.c" }));
});

describe("AuditLogs", () => {
  it("renders the audit rows returned by the API", async () => {
    api.get.mockResolvedValue({ data: LOGS });
    renderPage();
    expect(await screen.findByText("User logged in")).toBeInTheDocument();
    expect(screen.getByText(/quarantine on email/)).toBeInTheDocument();
  });

  it("shows a loading state before the data arrives", () => {
    api.get.mockReturnValue(new Promise(() => {}));  // never settles
    renderPage();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("shows an error instead of a misleading empty table when the API fails", async () => {
    // Regression guard: this request previously had no rejection handler, so a
    // failure rendered "No audit entries" as if the log were genuinely empty.
    api.get.mockRejectedValue({ message: "Network Error" });
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/cannot reach the phishguard api/i);
    expect(screen.queryByText(/no audit entries/i)).not.toBeInTheDocument();
  });

  it("surfaces the request id so an error can be traced in the server log", async () => {
    api.get.mockRejectedValue({
      response: {
        status: 503,
        data: { error: { message: "Database unavailable", request_id: "req-42" } },
      },
    });
    renderPage();
    expect(await screen.findByText(/req-42/)).toBeInTheDocument();
  });

  it("retries the request when the user clicks Try again", async () => {
    api.get.mockRejectedValueOnce({ message: "Network Error" });
    renderPage();
    await screen.findByRole("alert");

    api.get.mockResolvedValueOnce({ data: LOGS });
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(screen.getByText("User logged in")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows the genuine empty state when the API returns no rows", async () => {
    api.get.mockResolvedValue({ data: [] });
    renderPage();
    expect(await screen.findByText(/no audit entries/i)).toBeInTheDocument();
  });
});
