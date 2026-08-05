import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Dashboard from "./Dashboard";
import { AuthProvider } from "../context/AuthContext";
import api from "../api";

vi.mock("../api", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("../components/Layout", () => ({
  default: ({ title, children }) => <div><h1>{title}</h1>{children}</div>,
}));

const STATS = {
  total_emails: 8, quarantined: 3, confirmed_phishing: 1, released: 0,
  safe: 4, pending_requests: 1,
  by_level: { low: 3, medium: 1, high: 3, critical: 1 },
  avg_risk_score: 41.5, recent_high_risk: [],
};

function mockOk() {
  api.get.mockImplementation((url) =>
    url === "/api/dashboard/stats"
      ? Promise.resolve({ data: STATS })
      : Promise.resolve({ data: [] })
  );
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Dashboard />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  api.get.mockReset();
  localStorage.setItem(
    "pg_user",
    JSON.stringify({ id: 2, role: "analyst", email: "analyst@phishguard.local", full_name: "Sam" })
  );
});

describe("Dashboard", () => {
  it("renders the statistics returned by the API", async () => {
    mockOk();
    renderPage();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    expect(screen.getByText("41.5")).toBeInTheDocument();
  });

  it("shows a loading state while the request is in flight", () => {
    api.get.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("escapes the loading state and shows an error when stats fail", async () => {
    // Regression guard: the stats request previously had no rejection handler, so
    // `stats` stayed null and the page was stuck on "Loading…" forever.
    api.get.mockRejectedValue({ message: "Network Error" });
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/cannot reach the phishguard api/i);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("recovers when the retry succeeds", async () => {
    api.get.mockRejectedValue({ message: "Network Error" });
    renderPage();
    await screen.findByRole("alert");

    mockOk();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(screen.getByText("41.5")).toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not crash when by_level is missing from the response", async () => {
    api.get.mockImplementation((url) =>
      url === "/api/dashboard/stats"
        ? Promise.resolve({ data: { ...STATS, by_level: undefined } })
        : Promise.resolve({ data: [] })
    );
    renderPage();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
