import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { UploadedFile } from "@/lib/types";

interface FileMetadataProps {
  file: UploadedFile;
}

export function FileMetadata({ file }: FileMetadataProps) {
  const rows: { label: string; value: string }[] = [
    { label: "Name", value: file.name },
    { label: "Format", value: file.format },
    {
      label: "Dimensions",
      value:
        file.dimensions[0] && file.dimensions[1]
          ? `${file.dimensions[0]} × ${file.dimensions[1]} px`
          : "Unknown",
    },
    { label: "Bands", value: String(file.bands) },
    { label: "CRS", value: file.crs ?? "None" },
  ];

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Property</TableHead>
          <TableHead>Value</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.label}>
            <TableCell className="font-medium text-muted-foreground">
              {row.label}
            </TableCell>
            <TableCell className="font-mono text-xs">{row.value}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
