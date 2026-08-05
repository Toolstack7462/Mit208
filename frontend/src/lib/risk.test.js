import { describe, expect, it } from "vitest";
import { CATEGORY_META, FILTER_TABS, STATUS_META, formatDate, riskCategory } from "./risk";

describe("riskCategory", () => {
  it("collapses the backend's four levels into the UI's three categories", () => {
    expect(riskCategory("critical")).toBe("high");
    expect(riskCategory("high")).toBe("high");
    expect(riskCategory("medium")).toBe("uncertain");
    expect(riskCategory("low")).toBe("safe");
  });

  it("treats an unknown or missing level as safe rather than crashing", () => {
    expect(riskCategory(undefined)).toBe("safe");
    expect(riskCategory("")).toBe("safe");
    expect(riskCategory("something-new")).toBe("safe");
  });
});

describe("category and status metadata", () => {
  it("has styling for every category riskCategory can return", () => {
    for (const level of ["critical", "high", "medium", "low", undefined]) {
      expect(CATEGORY_META[riskCategory(level)]).toBeDefined();
    }
  });

  it("has a label for every status the backend can set", () => {
    for (const status of ["inbox", "quarantined", "released", "confirmed_phishing", "safe"]) {
      expect(STATUS_META[status]).toBeDefined();
      expect(STATUS_META[status].label).toBeTruthy();
    }
  });

  it("exposes a filter tab for each category plus 'all'", () => {
    expect(FILTER_TABS.map((t) => t.key)).toEqual(["all", "high", "uncertain", "safe"]);
  });
});

describe("formatDate", () => {
  it("returns an empty string for missing input instead of 'Invalid Date'", () => {
    expect(formatDate(null)).toBe("");
    expect(formatDate(undefined)).toBe("");
    expect(formatDate("")).toBe("");
  });

  it("formats a valid ISO timestamp", () => {
    const out = formatDate("2026-08-05T10:30:00Z");
    expect(out).not.toBe("");
    expect(out).toMatch(/\d/);
  });
});
