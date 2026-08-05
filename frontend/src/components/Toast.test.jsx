import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Toast, useToast } from "./Toast";

/** Minimal host so the hook can be driven from a test. */
function ToastHost() {
  const { toast, show } = useToast(3000);
  return (
    <div>
      <button onClick={() => show("Saved successfully", "success")}>fire success</button>
      <button onClick={() => show("Request refused", "error")}>fire error</button>
      <Toast message={toast.message} tone={toast.tone} />
    </div>
  );
}

describe("Toast", () => {
  it("renders nothing when there is no message", () => {
    const { container } = render(<Toast message="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("announces a success as a polite status", () => {
    render(<Toast message="Release request submitted" tone="success" />);
    const el = screen.getByRole("status");
    expect(el).toHaveTextContent("Release request submitted");
    expect(el).toHaveAttribute("aria-live", "polite");
  });

  it("announces a failure as an assertive alert, not a status", () => {
    // Regression guard: the previous per-page toast always rendered a green
    // success tick, so a refusal was shown with a success icon.
    render(<Toast message="You already have a pending release request" tone="error" />);
    const el = screen.getByRole("alert");
    expect(el).toHaveTextContent("You already have a pending release request");
    expect(el).toHaveAttribute("aria-live", "assertive");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("styles an error differently from a success", () => {
    const { container: ok } = render(<Toast message="Saved" tone="success" />);
    const { container: bad } = render(<Toast message="Refused" tone="error" />);
    expect(ok.firstChild.className).not.toEqual(bad.firstChild.className);
    expect(bad.firstChild.className).toMatch(/bg-red/);
  });

  it("defaults to success when no tone is given", () => {
    render(<Toast message="Done" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});

describe("useToast dismissal", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("dismisses a success toast after its timeout", () => {
    render(<ToastHost />);
    act(() => screen.getByText("fire success").click());
    expect(screen.getByRole("status")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(3001));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("keeps an error visible when it replaces a success mid-countdown", () => {
    // Regression guard: the earlier success timer used to survive and wipe the
    // newer error message off the screen before it could be read.
    render(<ToastHost />);
    act(() => screen.getByText("fire success").click());

    act(() => vi.advanceTimersByTime(2000));   // success timer still pending
    act(() => screen.getByText("fire error").click());

    act(() => vi.advanceTimersByTime(1500));   // past when the success would have fired
    expect(screen.getByRole("alert")).toHaveTextContent("Request refused");
  });

  it("eventually dismisses the error on its own longer timeout", () => {
    render(<ToastHost />);
    act(() => screen.getByText("fire error").click());

    act(() => vi.advanceTimersByTime(3001));   // success duration alone is not enough
    expect(screen.getByRole("alert")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(2600));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
