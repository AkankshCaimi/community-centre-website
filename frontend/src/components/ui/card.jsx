// shadcn/ui Card, copied into the repository (ADR 0005).
import { cn } from "@/lib/utils";

export function Card({ className, ...props }) {
  return (
    <div
      data-slot="card"
      className={cn("flex flex-col gap-4 rounded-xl border bg-card p-6 text-card-foreground shadow-sm", className)}
      {...props}
    />
  );
}
