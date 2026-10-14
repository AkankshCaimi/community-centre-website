// Focus ring, field edges and the colour pairs in use: docs/specs/ui-theme.md,
// T6 to T8. Every expected value comes from that spec and from WCAG 2.2.

import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";

const SRC = join(import.meta.dirname);
const CSS = readFileSync(join(SRC, "site.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

// Every application source file, the copied components included; not the tests.
const SOURCES = readdirSync(SRC, { recursive: true })
  .filter((name) => /\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name))
  .map((name) => [name, readFileSync(join(SRC, name), "utf8")]);

function colours() {
  const root = CSS.match(/:root\s*\{([^}]*)\}/);
  return Object.fromEntries(
    [...(root ? root[1] : "").matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]),
  );
}

function rgb(hex) {
  const value = hex.replace("#", "");
  return [0, 2, 4].map((i) => parseInt(value.slice(i, i + 2), 16));
}

function luminance([r, g, b]) {
  const linear = (c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}

function contrast(a, b) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (light + 0.05) / (dark + 0.05);
}

// A colour at `alpha` over a background, as the browser paints it.
function over(hex, alpha, backgroundHex) {
  const [front, back] = [rgb(hex), rgb(backgroundHex)];
  return front.map((c, i) => Math.round(c * alpha + back[i] * (1 - alpha)));
}

function colour(name) {
  const value = colours()[name];
  expect(value, name).toMatch(/^#[0-9a-fA-F]{6}$/);
  return rgb(value);
}

describe("T6: the focus ring", () => {
  test.each(["--background", "--card", "--muted"])("--ring has at least 3:1 against %s", (background) => {
    expect(contrast(colour("--ring"), colour(background))).toBeGreaterThanOrEqual(3);
  });

  test("the ring is never faded with an opacity, anywhere", () => {
    expect(CSS).not.toMatch(/ring-ring\/\d+/);
    for (const [file, source] of SOURCES) {
      expect(source, file).not.toMatch(/ring-ring\/\d+/);
    }
  });

  test("site.css draws the ring for anything with keyboard focus, 2px wide with a 2px gap", () => {
    const rule = CSS.match(/:focus-visible\s*\{([^}]*)\}/);
    expect(rule).not.toBeNull();
    expect(rule[1]).toMatch(/\bring-2\b/);
    expect(rule[1]).toMatch(/\bring-ring\b/);
    expect(rule[1]).toMatch(/\bring-offset-2\b/);
    expect(rule[1]).toMatch(/\bring-offset-background\b/);
  });

  test("every class list that draws a focus ring draws it 2px wide, in --ring, with a 2px gap", () => {
    let seen = 0;
    for (const [file, source] of SOURCES) {
      for (const classes of source.match(/["`][^"`]*focus-visible:ring[^"`]*["`]/g) ?? []) {
        seen += 1;
        expect(classes, file).toMatch(/focus-visible:ring-2\b/);
        expect(classes, file).toMatch(/focus-visible:ring-ring\b/);
        expect(classes, file).toMatch(/focus-visible:ring-offset-2\b/);
        expect(classes, file).toMatch(/focus-visible:ring-offset-background\b/);
      }
    }
    expect(seen).toBeGreaterThan(0);
  });
});

describe("T7: field edges", () => {
  test.each(["--background", "--card"])("--input has at least 3:1 against %s", (background) => {
    expect(contrast(colour("--input"), colour(background))).toBeGreaterThanOrEqual(3);
  });

  test("text fields, text areas and lists are bordered in --input", () => {
    const input = SOURCES.find(([file]) => file.endsWith("ui/input.jsx"))[1];
    const textarea = SOURCES.find(([file]) => file.endsWith("ui/textarea.jsx"))[1];
    const admin = SOURCES.find(([file]) => file === "AdminPage.jsx")[1];
    expect(input).toMatch(/\bborder-input\b/);
    expect(textarea).toMatch(/\bborder-input\b/);
    expect(admin.match(/LIST_CLASSES =\s*"([^"]*)"/)?.[1]).toMatch(/\bborder-input\b/);
  });
});

describe("T8: the colour pairs in use", () => {
  test.each([
    ["--destructive-foreground", "--destructive"],
    ["--primary", "--muted"],
    ["--foreground", "--muted"],
  ])("%s on %s has at least 4.5:1", (text, background) => {
    expect(contrast(colour(text), colour(background))).toBeGreaterThanOrEqual(4.5);
  });

  test.each([
    ["--primary-foreground", "--primary"],
    ["--destructive-foreground", "--destructive"],
  ])("%s on %s at 90 percent over --background (hover) has at least 4.5:1", (text, button) => {
    const hover = over(colours()[button], 0.9, colours()["--background"]);
    expect(contrast(colour(text), hover)).toBeGreaterThanOrEqual(4.5);
  });

  test("no colour is written into a component directly", () => {
    for (const [file, source] of SOURCES) {
      expect(source, file).not.toMatch(/\b(text|bg|border)-(white|black)\b|#[0-9a-fA-F]{3,6}\b/);
    }
  });

  test("the red buttons use --destructive-foreground", () => {
    const button = SOURCES.find(([file]) => file.endsWith("ui/button.jsx"))[1];
    expect(button).toMatch(/bg-destructive text-destructive-foreground/);
  });
});
