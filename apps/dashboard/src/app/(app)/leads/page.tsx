import Link from "next/link";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge, statusVariant } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { truncate } from "@/lib/utils";
import type { LeadRead } from "@/types/api";

interface SearchParams {
  sector?: string;
  region?: string;
  builder?: string;
  status?: string;
  min_score?: string;
}

export default async function LeadsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const leads = await api
    .get<LeadRead[]>("/api/v1/leads", {
      searchParams: {
        sector: params.sector,
        region: params.region,
        builder: params.builder,
        status: params.status,
        min_score: params.min_score ?? "0",
        limit: 200,
      },
    })
    .catch(() => [] as LeadRead[]);

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Leads</h1>
        <span className="text-xs text-wcm-detail uppercase tracking-wider">
          {leads.length} resultado{leads.length === 1 ? "" : "s"}
        </span>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">ID</TableHead>
            <TableHead>URL</TableHead>
            <TableHead>Sector</TableHead>
            <TableHead>Región</TableHead>
            <TableHead>Builder</TableHead>
            <TableHead className="w-16 text-right">Conf</TableHead>
            <TableHead className="w-16 text-right">Score</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leads.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="py-8 text-center text-wcm-detail">
                Sin leads. Lanza una campaña desde /campaigns.
              </TableCell>
            </TableRow>
          ) : (
            leads.map((lead) => (
              <TableRow key={lead.id}>
                <TableCell className="tabular-nums text-wcm-detail">
                  {lead.id}
                </TableCell>
                <TableCell>
                  <Link
                    href={`/leads/${lead.id}`}
                    className="hover:text-wcm-accent"
                  >
                    {truncate(String(lead.url), 60)}
                  </Link>
                </TableCell>
                <TableCell className="text-wcm-detail">
                  {lead.sector ?? "—"}
                </TableCell>
                <TableCell className="text-wcm-detail">
                  {lead.region ?? "—"}
                </TableCell>
                <TableCell>
                  {lead.builder_detected ? (
                    <Badge variant="default">{lead.builder_detected}</Badge>
                  ) : (
                    <span className="text-wcm-detail">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {lead.builder_confidence?.toFixed(2) ?? "—"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {lead.score}
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant(lead.status)}>
                    {lead.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
