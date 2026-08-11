import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import EmailDetailPanel from "./EmailDetailPanel";

// Regression cover for BUG-17 as it appeared in the interface: the analyst panel
// rendered all three status-changing buttons for every email whatever its
// status, so "Release" was live on email that had never been quarantined and the
// only feedback was an error toast after the click.

const EMAIL = {
  id: 1,
  message_id: "<a@b>",
  sender: "security@paypa1-support.com",
  sender_name: "PayPal Security",
  recipient: "staff@phishguard.local",
  subject: "Urgent: account suspended",
  body: "Confirm your password immediately.",
  status: "quarantined",
  risk_score: 88,
  risk_level: "critical",
  reasons: ["Raw IP address in link."],
  auth_spf: "fail",
  auth_dkim: "fail",
  auth_dmarc: "fail",
  templated_language: true,
  received_at: "2026-08-05T09:00:00Z",
};

const btn = (name) => screen.getByRole("button", { name });

function renderPanel(overrides = {}, props = {}) {
  return render(
    <EmailDetailPanel email={{ ...EMAIL, ...overrides }} mode="analyst" onAction={vi.fn()} {...props} />
  );
}

describe("analyst action availability", () => {
  it.each([
    // status,             quarantine, release, confirm phishing
    ["inbox", true, false, true],
    ["quarantined", false, true, true],
    ["released", true, false, true],
    ["confirmed_phishing", false, true, false],
    ["safe", true, false, true],
  ])("offers the right actions for %s email", (status, canQuarantine, canRelease, canConfirm) => {
    renderPanel({ status });

    expect(btn(/quarantine/i).disabled).toBe(!canQuarantine);
    expect(btn(/^release$/i).disabled).toBe(!canRelease);
    expect(btn(/confirm phishing/i).disabled).toBe(!canConfirm);
  });

  it("keeps Submit Feedback available from every status, because it changes nothing", () => {
    for (const status of ["inbox", "quarantined", "released", "confirmed_phishing", "safe"]) {
      const { unmount } = renderPanel({ status });
      expect(btn(/submit feedback/i)).toBeEnabled();
      unmount();
    }
  });

  it("explains in a tooltip why a disabled action is unavailable", () => {
    renderPanel({ status: "inbox" });
    expect(btn(/^release$/i)).toHaveAttribute("title", expect.stringMatching(/not available/i));
  });

  it("does not fire an action the server would refuse", async () => {
    const onAction = vi.fn();
    renderPanel({ status: "inbox" }, { onAction });

    await userEvent.click(btn(/^release$/i));

    expect(onAction).not.toHaveBeenCalled();
  });

  it("still fires a permitted action", async () => {
    const onAction = vi.fn();
    renderPanel({ status: "quarantined" }, { onAction });

    await userEvent.click(btn(/^release$/i));

    expect(onAction).toHaveBeenCalledWith("release");
  });

  it("disables every action while a request is in flight", () => {
    renderPanel({ status: "quarantined" }, { busy: true });
    expect(btn(/^release$/i)).toBeDisabled();
    expect(btn(/confirm phishing/i)).toBeDisabled();
  });
});

describe("staff release-request availability", () => {
  it.each([
    ["quarantined", true, /request email release/i],
    ["confirmed_phishing", true, /request email release/i],
    ["released", false, /already released/i],
    ["inbox", false, /already delivered/i],
    ["safe", false, /already delivered/i],
  ])("shows the right button for %s email", (status, enabled, label) => {
    render(<EmailDetailPanel email={{ ...EMAIL, status }} mode="staff" onAction={vi.fn()} />);

    const button = btn(label);
    expect(button.disabled).toBe(!enabled);
  });

  it("does not open the request dialog for an email that is not held", async () => {
    const onAction = vi.fn();
    render(<EmailDetailPanel email={{ ...EMAIL, status: "inbox" }} mode="staff" onAction={onAction} />);

    await userEvent.click(btn(/already delivered/i));

    expect(onAction).not.toHaveBeenCalled();
  });
});
