// shadcn/ui Textarea, copied into the repository (ADR 0005).
import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-24 w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-base shadow-xs transition-[color,box-shadow] placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 md:text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background aria-invalid:border-destructive",
        className,
      )}
      {...props}
    />
  );
}
