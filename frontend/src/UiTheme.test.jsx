// The UI theme: docs/specs/ui-theme.md (D1, D2, T1 to T5, H2, L1 to L8).
// Every expected value comes from that spec, and from package.json as it stood
// before the theme for the dependencies that were already there.

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import App from "./App.jsx";

const FRONTEND = join(import.meta.dirname, "..");
const SRC = join(FRONTEND, "src");
const read = (path) => readFileSync(join(FRONTEND, path), "utf8");
const CSS = () => read("src/site.css").replace(/\/\*[\s\S]*?\*\//g, "");

function openAt(path, fetchStub = vi.fn()) {
  window.history.pushState({}, "", path);
  vi.stubGlobal("fetch", fetchStub);
  render(<App />);
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

function classOf(element) {
  return element.getAttribute("class") ?? "";
}

// --- D1, D2: dependencies and setup

describe("D1: the dependencies", () => {
  const pkg = JSON.parse(read("package.json"));

  test("dependencies: React and the three the shadcn components need, nothing else", () => {
    expect(Object.keys(pkg.dependencies).sort()).toEqual(
      ["class-variance-authority", "clsx", "react", "react-dom", "tailwind-merge"].sort(),
    );
  });

  test("development dependencies: those before the theme, plus Tailwind and its Vite plugin", () => {
    expect(Object.keys(pkg.devDependencies).sort()).toEqual(
      [
        "@eslint/js",
        "@tailwindcss/vite",
        "@testing-library/jest-dom",
        "@testing-library/react",
        "@testing-library/user-event",
        "@vitejs/plugin-react",
        "eslint",
        "eslint-plugin-react-hooks",
        "eslint-plugin-react-refresh",
        "globals",
        "jsdom",
        "tailwindcss",
        "vite",
        "vitest",
      ].sort(),
    );
  });

  test("no Radix package, icon library or other component library", () => {
    const all = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies }).join(" ");
    expect(all).not.toMatch(/radix|lucide|@mui|bootstrap|tw-animate/);
  });
});

describe("D2: the shadcn setup", () => {
  test("components.json, lib/utils.js and the components, in JavaScript", () => {
    expect(existsSync(join(FRONTEND, "components.json"))).toBe(true);
    expect(JSON.parse(read("components.json")).tsx).toBe(false);
    expect(read("src/lib/utils.js")).toMatch(/export function cn\(/);
    for (const name of ["button", "card", "input", "label", "table", "textarea"]) {
      expect(existsSync(join(SRC, "components", "ui", `${name}.jsx`))).toBe(true);
    }
  });

  test("Vite has the Tailwind plugin and the @ alias", () => {
    const config = read("vite.config.js");
    expect(config).toMatch(/from "@tailwindcss\/vite"/);
    expect(config).toMatch(/tailwindcss\(\)/);
    expect(config).toMatch(/"@"\s*:/);
  });
});

// --- T1 to T5: the theme

describe("T5: exactly one stylesheet loads", () => {
  test("main.jsx imports site.css, once, and no other stylesheet", () => {
    const imports = read("src/main.jsx").match(/import\s+["'][^"']+\.css["']/g) ?? [];
    expect(imports).toEqual(['import "./site.css"']);
  });

  test("no other source file imports a stylesheet", () => {
    const files = readdirSync(SRC, { recursive: true }).filter(
      (name) => /\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name) && name !== "main.jsx",
    );
    for (const file of files) {
      expect(readFileSync(join(SRC, file), "utf8")).not.toMatch(/import[^;]*\.css["']/);
    }
  });

  test('the only import in site.css is @import "tailwindcss"', () => {
    expect(CSS().match(/@import[^;]*;/g)).toEqual(['@import "tailwindcss";']);
  });

  test("index.html links no stylesheet", () => {
    expect(read("index.html")).not.toMatch(/<link[^>]*stylesheet|<style/);
  });
});

describe("T1: a light theme only", () => {
  test("no dark variant, no .dark class, no prefers-color-scheme", () => {
    expect(CSS()).not.toMatch(/\.dark|@custom-variant\s+dark|prefers-color-scheme/);
  });
});

// WCAG 2.2 relative luminance and contrast ratio.
function luminance(hex) {
  const value = hex.replace("#", "");
  const full = value.length === 3 ? [...value].map((c) => c + c).join("") : value;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
  const linear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

function rootColours() {
  const root = CSS().match(/:root\s*\{([^}]*)\}/);
  return Object.fromEntries(
    [...(root ? root[1] : "").matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]),
  );
}

describe("T2: the theme colours", () => {
  const PAIRS = [
    ["--foreground", "--background"],
    ["--card-foreground", "--card"],
    ["--primary-foreground", "--primary"],
    ["--primary", "--background"],
    ["--secondary-foreground", "--secondary"],
    ["--muted-foreground", "--background"],
    ["--muted-foreground", "--muted"],
    ["--accent-foreground", "--accent"],
    ["--destructive", "--background"],
  ];

  test("every colour of the theme is written in hex on :root", () => {
    const colours = rootColours();
    for (const name of new Set(PAIRS.flat())) {
      expect(colours[name], name).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  test.each(PAIRS)("%s on %s has a contrast of at least 4.5 to 1", (text, background) => {
    const colours = rootColours();
    expect(contrast(colours[text], colours[background])).toBeGreaterThanOrEqual(4.5);
  });
});

describe("T3: no font is loaded", () => {
  test("no @font-face and nothing fetched from anywhere", () => {
    expect(CSS()).not.toMatch(/@font-face|url\(|https?:/);
    expect(read("index.html")).not.toMatch(/fonts\.googleapis|fonts\.gstatic|\.woff/);
  });
});

describe("T4: the focus ring is never taken away", () => {
  test("site.css never removes an outline", () => {
    expect(CSS()).not.toMatch(/outline:\s*(none|0)\b/);
  });

  test("every class list in the components that removes the outline puts a ring in its place", () => {
    const folder = join(SRC, "components", "ui");
    for (const file of readdirSync(folder)) {
      const source = readFileSync(join(folder, file), "utf8");
      for (const classes of source.match(/"[^"]*outline-none[^"]*"/g) ?? []) {
        expect(classes, file).toMatch(/focus-visible:ring/);
      }
    }
  });
});

// --- H2: the shadcn components render the native elements

describe("H2: the components are the native elements, styled", () => {
  test.each([
    ["button", "Button", "BUTTON"],
    ["input", "Input", "INPUT"],
    ["textarea", "Textarea", "TEXTAREA"],
    ["label", "Label", "LABEL"],
  ])("%s.jsx renders a <%s>", async (file, name, tag) => {
    const module = await import(`./components/ui/${file}.jsx`);
    const Component = module[name];
    const { container } = render(<Component data-testid="it" />);
    expect(container.querySelector("[data-testid=it]").tagName).toBe(tag);
  });

  test("the booking form keeps native tick boxes, styled fields and a styled button", () => {
    openAt("/");

    expect(screen.getByLabelText("I agree to the terms and conditions")).toHaveAttribute("type", "checkbox");
    expect(screen.getByLabelText("Name").getAttribute("data-slot")).toBe("input");
    expect(screen.getByLabelText("Additional details").getAttribute("data-slot")).toBe("textarea");
    expect(screen.getByRole("button", { name: "Send booking request" }).getAttribute("data-slot")).toBe("button");
  });
});

// --- L1 to L8: layout

describe("L1 to L5, L8: the public pages", () => {
  test("L1: the navigation is a wrapping row; the current page is marked by more than colour", () => {
    openAt("/facilities");

    const list = within(screen.getByRole("navigation", { name: "Main" })).getByRole("list");
    expect(classOf(list)).toMatch(/\bflex\b/);
    expect(classOf(list)).toMatch(/\bflex-wrap\b/);
    expect(classOf(screen.getByRole("link", { name: "Facilities" }))).toMatch(
      /(^|\s)(aria-\[current=page\]:)?(font-semibold|font-bold|underline)\b/,
    );
  });

  test("L1, L2: the header and the footer are styled bands", () => {
    openAt("/");

    expect(classOf(document.querySelector("header"))).toMatch(/\bborder-b\b|\bbg-/);
    expect(classOf(screen.getByRole("contentinfo"))).toMatch(/\bborder-t\b|\bbg-/);
  });

  test("L3: the content is at most about 64rem wide", () => {
    openAt("/faq");

    expect(classOf(screen.getByRole("main"))).toMatch(/\bmax-w-(5xl|\[64rem\])\b/);
  });

  test.each(["/facilities", "/events"])("L4: %s shows its items as cards in a wrapping grid", (path) => {
    openAt(path);

    const items = within(screen.getByRole("main")).getAllByRole("listitem");
    expect(classOf(items[0].parentElement)).toMatch(/\bgrid\b/);
    for (const item of items) {
      expect(item.getAttribute("data-slot") ?? item.querySelector("[data-slot=card]")?.getAttribute("data-slot")).toBe(
        "card",
      );
    }
  });

  test("L5: the gallery is a grid of columns at least 16rem wide", () => {
    openAt("/gallery");

    const grid = screen.getAllByRole("figure")[0].parentElement;
    expect(classOf(grid)).toMatch(/\bgrid\b/);
    expect(classOf(grid)).toMatch(/grid-cols-\[repeat\(auto-fill,minmax\(16rem,1fr\)\)\]/);
  });

  test("L8: the skip link is hidden until it has keyboard focus", () => {
    openAt("/");

    const skip = screen.getByRole("link", { name: "Skip to main content" });
    expect(classOf(skip)).toMatch(/\bsr-only\b/);
    expect(classOf(skip)).toMatch(/\bfocus:not-sr-only\b/);
  });
});

describe("L6, L7: the admin page", () => {
  function json(status, body) {
    return { status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) };
  }

  test("L6: the login form sits in a card, with styled fields and button", async () => {
    openAt("/admin", vi.fn(() => Promise.resolve(json(401, { error: "not_authenticated" }))));

    const email = await screen.findByLabelText("Email");
    expect(email.closest("[data-slot=card]")).not.toBeNull();
    expect(email.getAttribute("data-slot")).toBe("input");
    expect(screen.getByRole("button", { name: "Log in" }).getAttribute("data-slot")).toBe("button");
  });

  test("L7: the bookings table scrolls sideways in its own box", async () => {
    const item = {
      id: 1,
      name: "Person 1",
      email: "person1@example.com",
      phone: "07700 900001",
      guest_count: 40,
      starts_at: "2026-11-20T10:00",
      ends_at: "2026-11-20T14:00",
      state: "submitted",
      submitted_at: "2026-10-14T09:00",
      details: "",
      erased: false,
    };
    const answer = (url) =>
      Promise.resolve(
        url.includes("/session")
          ? json(200, { email: "admin@centre.example" })
          : json(200, { items: [item], total: 1, page: 1, page_size: 50 }),
      );
    openAt("/admin", vi.fn((url) => answer(String(url))));

    await waitFor(() => expect(screen.getByRole("table")).toBeInTheDocument());
    const table = screen.getByRole("table");
    expect(table.getAttribute("data-slot")).toBe("table");
    expect(classOf(table.parentElement)).toMatch(/\boverflow-x-auto\b/);
  });
});
