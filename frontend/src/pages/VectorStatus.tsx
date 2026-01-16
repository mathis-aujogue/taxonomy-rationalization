import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getVectorStatus, getTargetIds } from '../api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { RefreshCw, CheckCircle2, AlertTriangle, Database } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function VectorStatus() {
  const [targetIdFilter, setTargetIdFilter] = useState<string>('');

  const { data: targetIdsData } = useQuery({
    queryKey: ['target-ids'],
    queryFn: getTargetIds,
  });

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['vector-status', targetIdFilter || undefined],
    queryFn: () => getVectorStatus(targetIdFilter || undefined),
  });

  if (isLoading) {
    return <div className="p-4 text-muted-foreground">Loading...</div>;
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            Error loading vector status: {String(error)}
          </AlertDescription>
        </Alert>
        <Button onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!data) {
    return <div className="p-4">No data available</div>;
  }

  const targets = Object.entries(data.targets || {});

  // Sort targets: Not Ready first, then Ready
  const sortedTargets = [...targets].sort(([, a], [, b]) => {
    if (a.ready_for_hybrid_matching === b.ready_for_hybrid_matching) {
      return 0;
    }
    return a.ready_for_hybrid_matching ? 1 : -1;
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Vector Embeddings Status</h1>
        <Button onClick={() => refetch()} variant="outline" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <Card>
        <CardContent className="pt-6 flex items-center justify-between gap-4">
            <div className="flex items-center gap-4 flex-1">
                <Select value={targetIdFilter || undefined} onValueChange={(val) => setTargetIdFilter(val === 'all' ? '' : val)}>
                    <SelectTrigger className="max-w-sm">
                        <SelectValue placeholder="Filter by Target ID" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Targets</SelectItem>
                        {targetIdsData?.target_ids?.map((target) => (
                            <SelectItem key={target.target_id} value={target.target_id}>
                                {target.target_id}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <span className="text-sm text-muted-foreground">Table: {data.table_name}</span>
            </div>
            <Badge variant={data.has_target_id_column ? "default" : "secondary"}>
                {data.has_target_id_column ? 'Has target_id column' : 'Metadata only'}
            </Badge>
        </CardContent>
      </Card>

      {sortedTargets.length === 0 ? (
        <Alert>
            <AlertDescription>No embeddings found in the database.</AlertDescription>
        </Alert>
      ) : (
        <Accordion type="single" collapsible className="w-full space-y-4">
          {sortedTargets.map(([targetId, status]) => (
            <AccordionItem key={targetId} value={targetId} className="border rounded-lg px-4 bg-card">
              <AccordionTrigger className="hover:no-underline">
                <div className="flex items-center justify-between w-full pr-4">
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-muted-foreground" />
                    <span className="text-xl font-bold">{targetId || '(unknown)'}</span>
                  </div>
                  {status.ready_for_hybrid_matching ? (
                    <Badge className="bg-green-600 hover:bg-green-700">
                      <CheckCircle2 className="w-3 h-3 mr-1" />
                      Ready for Hybrid Matching
                    </Badge>
                  ) : (
                    <Badge variant="destructive">
                      <AlertTriangle className="w-3 h-3 mr-1" />
                      Not Ready
                    </Badge>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-4">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Total Records</p>
                    <p className="text-2xl font-bold">{status.total_records}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Categories</p>
                    <p className="text-2xl font-bold">{status.num_categories}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Completeness</p>
                    <p className="text-2xl font-bold">{(status.completeness_ratio * 100).toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Expected Records</p>
                    <p className="text-2xl font-bold">{status.num_categories * 5}</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium mb-2">Required Components</h4>
                    <div className="flex gap-2 flex-wrap">
                      {['l1', 'l2', 'l3', 'full', 'desc'].map((comp) => {
                        const isPresent = status.has_required_components[comp as keyof typeof status.has_required_components];
                        return (
                          <Badge 
                            key={comp} 
                            variant={isPresent ? "outline" : "destructive"}
                            className={cn(isPresent && "border-green-500 text-green-600 bg-green-50")}
                          >
                            {comp.toUpperCase()}: {status.components[comp] || 0}
                          </Badge>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      )}
    </div>
  );
}
