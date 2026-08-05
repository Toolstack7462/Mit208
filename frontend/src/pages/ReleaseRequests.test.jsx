import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReleaseRequests from "./ReleaseRequests";
import { AuthProvider } from "../context/AuthContext";
import api from "../api";

vi.mock("../api", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("../components/Layout", () => ({ default: ({ children }) => <div>{children}</div> }));

const PENDING = {
  id: 1, email_id: 5, requested_by: 3, requester_name: "Riley Staff",
  email_subject: "Urgent: account suspended",
  reason: "I was expecting this invoice from our vendor.",
  status: "pending", reviewed_by: null, review_note: null,
  created_at: "2026-08-05T09:30:00Z", reviewed_at: null,
};

function signIn(role) {
  localStorage.setItem(
    "pg_user",
    JSON.stringify({ id: 2, role, email: `${role}@phishguard.local`, full_name: "Test" })
  );
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <ReleaseRequests />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
});

describe("ReleaseRequests", () => {
  it("lists pending requests with the stated reason", async () => {
    signIn("analyst");
    api.get.mockResolvedValue({ data: [PENDING] });
    renderPage();
    expect(await screen.findByText(/urgent: account suspended/i)).toBeInTheDocument();
    expect(screen.getByText(/expecting this invoice/i)).toBeInTheDocument();
  });

  it("shows an error with a retry when the queue cannot be loaded", async () => {
    signIn("analyst");
    api.get.mockRejectedValue({ message: "Network Error" });
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/cannot reach the phishguard api/i);
    expect(screen.queryByText(/no release requests yet/i)).not.toBeInTheDocument();
  });

  it("distinguishes a genuinely empty queue from a failure", async () => {
    signIn("analyst");
    api.get.mockResolvedValue({ data: [] });
    renderPage();
    expect(await screen.findByText(/no release requests yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("sends the analyst's approval and reloads the queue", async () => {
    signIn("analyst");
    api.get.mockResolvedValue({ data: [PENDING] });
    api.post.mockResolvedValue({ data: { ...PENDING, status: "approved" } });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /approve/i }));

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/api/release-requests/1/decision", {
        status: "approved",
      })
    );
  });

  it("reports the server's conflict message when the request was already decided", async () => {
    signIn("analyst");
    api.get.mockResolvedValue({ data: [PENDING] });
    api.post.mockRejectedValue({
      response: { status: 409, data: { error: { message: "Request already decided" } } },
    });
    renderPage();

    await userEvent.click(await screen.findByRole("button", { name: /deny/i }));
    expect(await screen.findByText(/request already decided/i)).toBeInTheDocument();
  });

  it("hides the decision controls from staff", async () => {
    signIn("staff");
    api.get.mockResolvedValue({ data: [PENDING] });
    renderPage();

    await screen.findByText(/urgent: account suspended/i);
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /deny/i })).not.toBeInTheDocument();
  });
});
