// The stylesheet: rules ST1 to ST9 of docs/specs/public-pages.md, checked by
// reading frontend/src/site.css. Every expected value comes from that spec.

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";

const SRC = join(import.meta.dirname);
const RAW = readFileSync(join(SRC, "site.css"), "utf8");
const CSS = RAW.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\s+/g, " ");

// Every rule as [selector, declarations], with whitespace collapsed.
const RULES = [...CSS.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => [
  match[1].trim(),
  match[2].trim(),
]);

function declarationsOf(test) {
  return RULES.filter(([selector]) => test(selector)).map(([, body]) => body);
}

function hasDeclaration(selectorPart, declaration) {
  return RULES.some(
    ([selector, body]) =>
      selector.includes(selectorPart) && body.replace(/\s/g, "").includes(declaration.replace(/\s/g, "")),
  );
}

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

const ROOT = Object.fromEntries(
  [...(declarationsOf((selector) => selector === ":root")[0] ?? "").matchAll(/(--[\w-]+)\s*:\s*([^;]+)/g)].map(
    (match) => [match[1], match[2].trim()],
  ),
);

describe("ST1: one small plain stylesheet", () => {
  test("main.jsx imports it once, and nothing else in the app imports a stylesheet", () => {
    const main = readFileSync(join(SRC, "main.jsx"), "utf8");
    expect(main.match(/import "\.\/site\.css";/g)).toHaveLength(1);

    for (const file of readdirSync(SRC).filter((name) => /\.jsx?$/.test(name) && name !== "main.jsx" && !/\.test\.jsx?$/.test(name))) {
      expect(readFileSync(join(SRC, file), "utf8")).not.toMatch(/import [^;]*\.css["']/);
    }
  });

  test("it has at most 200 lines", () => {
    expect(RAW.split("\n").length).toBeLessThanOrEqual(200);
  });

  test("it loads nothing from anywhere", () => {
    expect(CSS).not.toMatch(/@import|url\(|https?:/);
  });

  test("the only class it selects is skip-link", () => {
    const classes = new Set(
      RULES.flatMap(([selector]) => [...selector.matchAll(/\.([A-Za-z][\w-]*)/g)].map((m) => m[1])),
    );
    expect([...classes]).toEqual(["skip-link"]);
  });
});

describe("ST2: base font, line height and colours", () => {
  test("the body uses the system sans-serif font with a line height of 1.5", () => {
    expect(hasDeclaration("body", "line-height: 1.5")).toBe(true);
    expect(declarationsOf((selector) => selector.split(",").map((s) => s.trim()).includes("body")).join(" ")).toMatch(
      /font-family:[^;]*system-ui[^;]*sans-serif/,
    );
  });

  test("the six colours are custom properties on :root", () => {
    for (const name of ["--background", "--text", "--muted", "--link", "--error", "--shade"]) {
      expect(ROOT[name]).toMatch(/^#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?$/);
    }
  });

  test.each(["--text", "--muted", "--link", "--error"])(
    "%s has a contrast of at least 4.5 to 1 on --background and on --shade",
    (name) => {
      expect(contrast(ROOT[name], ROOT["--background"])).toBeGreaterThanOrEqual(4.5);
      expect(contrast(ROOT[name], ROOT["--shade"])).toBeGreaterThanOrEqual(4.5);
    },
  );
});

describe("ST3 to ST5, ST8, ST9: layout", () => {
  test("ST3: content is at most 60rem wide, the admin page at most 80rem", () => {
    expect(CSS).toMatch(/max-width: ?60rem/);
    expect(CSS).toMatch(/max-width: ?80rem/);
  });

  test("ST4: the current page's link is bold", () => {
    expect(hasDeclaration('[aria-current="page"]', "font-weight: bold")).toBe(true);
  });

  test("ST5: the footer text is in --muted", () => {
    expect(hasDeclaration("footer", "color: var(--muted)")).toBe(true);
  });

  test("ST7: error messages are in --error", () => {
    expect(hasDeclaration('[role="alert"]', "color: var(--error)")).toBe(true);
  });

  test("ST8: the admin table's borders collapse, and headings sit on --shade", () => {
    expect(hasDeclaration("table", "border-collapse: collapse")).toBe(true);
    expect(hasDeclaration("th", "background: var(--shade)")).toBe(true);
  });

  test("ST9: pictures fit their container and keep their proportions", () => {
    expect(hasDeclaration("img", "max-width: 100%")).toBe(true);
    expect(hasDeclaration("img", "height: auto")).toBe(true);
  });

  test("ST9: the gallery is a grid of columns at least 16rem wide", () => {
    expect(CSS).toMatch(/grid-template-columns: ?repeat\(auto-fill, ?minmax\(16rem, ?1fr\)\)/);
  });
});

describe("ST6, ST7: nothing taken from the keyboard", () => {
  test("ST6: the skip link is never removed with display: none or visibility: hidden", () => {
    for (const body of declarationsOf((selector) => selector.includes(".skip-link"))) {
      expect(body).not.toMatch(/display: ?none|visibility: ?hidden/);
    }
  });

  test("ST6: the skip link has a rule for when it has focus", () => {
    expect(RULES.some(([selector]) => /\.skip-link:focus/.test(selector))).toBe(true);
  });

  test("ST7: the focus outline is never removed", () => {
    expect(CSS).not.toMatch(/outline: ?(none|0)\b/);
  });

  test("ST7: everything shows an outline when it has keyboard focus", () => {
    expect(RULES.some(([selector, body]) => selector.includes(":focus-visible") && /outline:/.test(body))).toBe(
      true,
    );
  });
});
