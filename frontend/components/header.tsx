import { Badge } from "@/components/ui/badge";

export function Header() {
  return (
    <header className="flex items-center justify-between border-b bg-background px-6 py-3">
      <div className="flex flex-col">
        <h1 className="text-lg font-semibold leading-tight">ArchEO-Agent</h1>
        <p className="text-xs text-muted-foreground">
          Archaeological Image Analysis
        </p>
      </div>
      <Badge variant="secondary">GPT-5.4 Vision</Badge>
    </header>
  );
}
