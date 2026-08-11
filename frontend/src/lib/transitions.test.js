import { describe, expect, it } from "vitest";

import {
  ACTION_TARGET_STATUS,
  ALLOWED_SOURCE_STATUSES,
  HOLDABLE_STATUSES,
  isAllowed,
  unavailableReason,
} from "./transitions";

// The five statuses declared in backend/app/models.py (EMAIL_STATUSES).
const STATUSES = ["inbox", "quarantined", "released", "confirmed_phishing", "safe"];

describe("email transition rules", () => {
  it("allows release only from a status that is withholding the email", () => {
    expect(isAllowed("release", "quarantined")).toBe(true);
    expect(isAllowed("release", "confirmed_phishing")).toBe(true);
    expect(isAllowed("release", "inbox")).toBe(false);
    expect(isAllowed("release", "safe")).toBe(false);
    expect(isAllowed("release", "released")).toBe(false);
  });

  it("does not let quarantine downgrade a confirmed phishing verdict", () => {
    expect(isAllowed("quarantine", "confirmed_phishing")).toBe(false);
    expect(isAllowed("quarantine", "inbox")).toBe(true);
    expect(isAllowed("quarantine", "released")).toBe(true);
  });

  it("keeps a phishing verdict reachable from every other status", () => {
    for (const status of STATUSES.filter((s) => s !== "confirmed_phishing")) {
      expect(isAllowed("confirm_phishing", status)).toBe(true);
    }
    expect(isAllowed("confirm_phishing", "confirmed_phishing")).toBe(false);
  });

  it("allows feedback from every status because it changes nothing", () => {
    for (const status of STATUSES) expect(isAllowed("feedback", status)).toBe(true);
    expect(ACTION_TARGET_STATUS.feedback).toBeNull();
  });

  it("never offers an action that would leave the status unchanged", () => {
    for (const status of STATUSES) {
      for (const [action, target] of Object.entries(ACTION_TARGET_STATUS)) {
        if (target === status) expect(isAllowed(action, status)).toBe(false);
      }
    }
  });

  it("treats the holdable statuses as exactly the release sources", () => {
    expect(HOLDABLE_STATUSES).toEqual(ALLOWED_SOURCE_STATUSES.release);
  });

  it("explains why an unavailable action is unavailable", () => {
    expect(unavailableReason("release", "quarantined")).toBe("");
    expect(unavailableReason("release", "released")).toMatch(/already released/i);
    expect(unavailableReason("release", "inbox")).toMatch(/not available/i);
  });
});
