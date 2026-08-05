import { describe, expect, it } from "vitest";
import { errorMessage, errorRequestId, isNetworkError } from "./errors";

describe("errorMessage", () => {
  it("reads the API's error envelope", () => {
    const err = {
      response: { status: 409, data: { error: { code: 409, message: "Request already decided" } } },
    };
    expect(errorMessage(err)).toBe("Request already decided");
  });

  it("still understands FastAPI's plain detail string", () => {
    const err = { response: { status: 404, data: { detail: "Email not found" } } };
    expect(errorMessage(err)).toBe("Email not found");
  });

  it("flattens FastAPI's field-level validation list", () => {
    const err = {
      response: {
        status: 422,
        data: { detail: [{ loc: ["body", "reason"], msg: "String too short" }] },
      },
    };
    expect(errorMessage(err)).toBe("reason: String too short");
  });

  it("explains an unreachable backend instead of showing a raw axios message", () => {
    expect(errorMessage({ message: "Network Error" })).toMatch(/Cannot reach the PhishGuard API/);
  });

  it("explains a timeout distinctly", () => {
    expect(errorMessage({ code: "ECONNABORTED" })).toMatch(/took too long/);
  });

  it("gives a readable message for a bare 500 with no body", () => {
    expect(errorMessage({ response: { status: 500, data: null } })).toMatch(/server encountered a problem/);
  });

  it("gives a readable message for 403 and 429", () => {
    expect(errorMessage({ response: { status: 403, data: {} } })).toMatch(/permission/);
    expect(errorMessage({ response: { status: 429, data: {} } })).toMatch(/Too many attempts/);
  });

  it("falls back to the supplied default", () => {
    expect(errorMessage({ response: { status: 418, data: {} } }, "Custom fallback"))
      .toBe("Custom fallback");
  });

  it("never returns an empty string", () => {
    for (const err of [undefined, null, {}, { response: {} }, { response: { data: {} } }]) {
      expect(errorMessage(err).length).toBeGreaterThan(0);
    }
  });
});

describe("errorRequestId", () => {
  it("reads the id from the envelope", () => {
    const err = { response: { data: { error: { request_id: "abc-123" } } } };
    expect(errorRequestId(err)).toBe("abc-123");
  });

  it("falls back to the response header", () => {
    const err = { response: { data: {}, headers: { "x-request-id": "hdr-9" } } };
    expect(errorRequestId(err)).toBe("hdr-9");
  });

  it("returns null when there is none", () => {
    expect(errorRequestId({ response: { data: {} } })).toBeNull();
  });
});

describe("isNetworkError", () => {
  it("distinguishes a transport failure from an API reply", () => {
    expect(isNetworkError({ message: "Network Error" })).toBe(true);
    expect(isNetworkError({ response: { status: 500 } })).toBe(false);
  });
});
