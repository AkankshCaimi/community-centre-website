// shadcn/ui Label, copied into the repository (ADR 0005) as a plain <label>,
// without the Radix part (docs/specs/ui-theme.md, D1).
import { cn } from "@/lib/utils";

export function Label({ className, ...props }) {
  return (
    <label
      data-slot="label"
      className={cn("text-sm leading-none font-medium select-none", className)}
      {...props}
    />
  );
}
