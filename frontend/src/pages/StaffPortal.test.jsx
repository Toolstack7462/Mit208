import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StaffPortal from "./StaffPortal";
import { AuthProvider } from "../context/AuthContext";
import api from "../api";

vi.mock("../api", () => ({ default: { get: vi.fn(), post: vi.fn() } }));
vi.mock("../components/Layout", () => ({ default: ({ children }) => <div>{children}</div> }));

const HELD_EMAIL = {
  id: 1, message_id: "<a@b>", sender: "security@paypa1-support.com",
  sender_name: "PayPal Security", recipient: "staff@phishguard.local",
  subject: "Urgent: account suspended", status: "quarantined",
  risk_score: 88, risk_level: "critical", ai_generated: true,
  received_at: "2026-08-05T09:00:00Z",
};
const DELIVERED_EMAIL = {
  ...HELD_EMAIL, id: 2, subject: "Monday tech digest", status: "inbox",
  risk_score: 4, risk_level: "low", ai_generated: false,
};

/** Wire api.get for the two list calls plus the detail call. */
function mockLoad({ emails = [HELD_EMAIL, DELIVERED_EMAIL], requests = [], detail = HELD_EMAIL } = {}) {
  api.get.mockImplementation((url) => {
    if (url === "/api/emails") return Promise.resolve({ data: emails });
    if (url === "/api/release-requests") return Promise.resolve({ data: requests });
    if (url.startsWith("/api/emails/")) {
      const id = Number(url.split("/").pop());
      const found = [emails, [detail]].flat().find((e) => e.id === id) || detail;
      return Promise.resolve({ data: { ...found, body: "…", reasons: ["Raw IP link."] } });
    }
    return Promise.resolve({ data: [] });
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <StaffPortal />
      </AuthProvider>
    </MemoryRouter>
  );
}

async function openRequestDialog() {
  const btn = await screen.findByRole("button", { name: /request email release/i });
  await userEvent.click(btn);
  return screen.findByLabelText(/reason for release/i);
}

beforeEach(() => {
  api.get.mockReset();
  api.post.mockReset();
  localStorage.setItem(
    "pg_user",
    JSON.stringify({ id: 3, role: "staff", email: "staff@phishguard.local", full_name: "Riley" })
  );
});

describe("StaffPortal mailbox", () => {
  it("lists the staff member's own email", async () => {
    mockLoad();
    renderPage();
    expect(await screen.findByText(/urgent: account suspended/i)).toBeInTheDocument();
  });

  it("shows an error with a retry when the mailbox cannot be loaded", async () => {
    api.get.mockRejectedValue({ message: "Network Error" });
    renderPage();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/cannot reach the phishguard api/i);
    expect(screen.queryByText(/your mailbox is empty/i)).not.toBeInTheDocument();
  });
});

describe("release request validation", () => {
  it("keeps Submit disabled until the reason is long enough", async () => {
    mockLoad();
    renderPage();
    const textarea = await openRequestDialog();
    const submit = screen.getByRole("button", { name: /submit request/i });

    expect(submit).toBeDisabled();

    await userEvent.type(textarea, "short");
    expect(submit).toBeDisabled();

    await userEvent.clear(textarea);
    await userEvent.type(textarea, "I was expecting this vendor invoice.");
    expect(submit).toBeEnabled();
  });

  it("does not treat whitespace as a valid justification", async () => {
    mockLoad();
    renderPage();
    const textarea = await openRequestDialog();
    await userEvent.type(textarea, "               ");
    expect(screen.getByRole("button", { name: /submit request/i })).toBeDisabled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("submits a valid request and sends the trimmed reason", async () => {
    mockLoad();
    api.post.mockResolvedValue({ data: { id: 9, status: "pending" } });
    renderPage();
    const textarea = await openRequestDialog();

    await userEvent.type(textarea, "  I was expecting this vendor invoice.  ");
    await userEvent.click(screen.getByRole("button", { name: /submit request/i }));

    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/api/release-requests", {
      email_id: 1,
      reason: "I was expecting this vendor invoice.",
    }));
  });

  it("shows the server's rejection inside the dialog rather than closing it", async () => {
    mockLoad();
    api.post.mockRejectedValue({
      response: {
        status: 409,
        data: { error: { message: "You already have a pending release request for this email." } },
      },
    });
    renderPage();
    const textarea = await openRequestDialog();
    await userEvent.type(textarea, "I was expecting this vendor invoice.");
    await userEvent.click(screen.getByRole("button", { name: /submit request/i }));

    expect(await screen.findByText(/already have a pending release request/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/reason for release/i)).toBeInTheDocument();
  });

  it("blocks a second request for an email that already has one open", async () => {
    mockLoad({ requests: [{ id: 7, email_id: 1, status: "pending", reason: "x", requested_by: 3 }] });
    renderPage();
    await userEvent.click(await screen.findByRole("button", { name: /request email release/i }));

    expect(await screen.findByText(/already have a pending release request/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/reason for release/i)).not.toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });
});
