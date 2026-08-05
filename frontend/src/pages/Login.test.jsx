import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Login from "./Login";
import { AuthProvider } from "../context/AuthContext";
import api from "../api";

vi.mock("../api", () => ({
  default: { post: vi.fn(), get: vi.fn() },
}));

const navigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => navigate };
});

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  api.post.mockReset();
  api.get.mockReset();
  navigate.mockReset();
});

describe("Login", () => {
  it("renders the sign-in form", () => {
    renderLogin();
    expect(screen.getByRole("heading", { name: /sign in/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it("stores the token and navigates to the dashboard on success", async () => {
    api.post.mockResolvedValue({
      data: {
        access_token: "test-token",
        user: { id: 2, email: "analyst@phishguard.local", role: "analyst", full_name: "Sam" },
      },
    });
    renderLogin();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/dashboard"));
    expect(localStorage.getItem("pg_token")).toBe("test-token");
  });

  it("shows the API's message when the credentials are wrong", async () => {
    api.post.mockRejectedValue({
      response: { status: 401, data: { error: { message: "Incorrect email or password" } } },
    });
    renderLogin();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/incorrect email or password/i)).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
    expect(localStorage.getItem("pg_token")).toBeNull();
  });

  it("shows the rate-limit message after too many attempts", async () => {
    api.post.mockRejectedValue({
      response: {
        status: 429,
        data: { error: { message: "Too many failed login attempts. Please try again later." } },
      },
    });
    renderLogin();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/too many failed login attempts/i)).toBeInTheDocument();
  });

  it("explains an unreachable backend instead of failing silently", async () => {
    api.post.mockRejectedValue({ message: "Network Error" });  // no .response
    renderLogin();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText(/cannot reach the phishguard api/i)).toBeInTheDocument();
  });

  it("does not leave a stale error visible after a later success", async () => {
    api.post.mockRejectedValueOnce({
      response: { status: 401, data: { error: { message: "Incorrect email or password" } } },
    });
    renderLogin();
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/incorrect email or password/i)).toBeInTheDocument();

    api.post.mockResolvedValueOnce({
      data: {
        access_token: "t",
        user: { id: 2, email: "analyst@phishguard.local", role: "analyst", full_name: "Sam" },
      },
    });
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() =>
      expect(screen.queryByText(/incorrect email or password/i)).not.toBeInTheDocument()
    );
  });

  it("never renders a password in plain text", () => {
    renderLogin();
    expect(screen.getByLabelText(/password/i)).toHaveAttribute("type", "password");
  });
});
