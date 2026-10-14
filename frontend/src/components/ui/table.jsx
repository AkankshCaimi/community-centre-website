// shadcn/ui Table, copied into the repository (ADR 0005). The table scrolls
// sideways inside its own box on a narrow screen (docs/specs/ui-theme.md, L7).
import { cn } from "@/lib/utils";

export function Table({ className, ...props }) {
  return (
    <div data-slot="table-container" className="relative w-full overflow-x-auto rounded-lg border">
      <table data-slot="table" className={cn("w-full caption-bottom text-sm", className)} {...props} />
    </div>
  );
}

export function TableHeader({ className, ...props }) {
  return <thead data-slot="table-header" className={cn("bg-muted [&_tr]:border-b", className)} {...props} />;
}

export function TableBody({ className, ...props }) {
  return <tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

export function TableRow({ className, ...props }) {
  return <tr data-slot="table-row" className={cn("border-b transition-colors hover:bg-muted/50", className)} {...props} />;
}

export function TableHead({ className, ...props }) {
  return (
    <th
      data-slot="table-head"
      className={cn("h-10 px-3 text-left align-middle font-medium whitespace-nowrap text-foreground", className)}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }) {
  return <td data-slot="table-cell" className={cn("p-3 align-top", className)} {...props} />;
}
