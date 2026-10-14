import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// Joins class names, letting a later Tailwind class override an earlier one (shadcn/ui).
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
