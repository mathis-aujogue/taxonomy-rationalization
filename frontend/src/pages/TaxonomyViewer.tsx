import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getOurTaxonomy, getTargetIds } from '../api/client';
import type { TaxonomyNode } from '../api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ChevronRight, ChevronDown, Folder, FileText, FileDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { exportTaxonomyTree } from '../api/client';
import { useMutation } from '@tanstack/react-query';

function TreeNode({ node, level = 0 }: { node: TaxonomyNode; level?: number }) {
  const [open, setOpen] = useState(false);
  const label = node.l3 || `${node.l1 || ''} > ${node.l2 || ''}`;
  const hasChildren = node.children.length > 0;

  return (
    <div className="select-none">
      <div 
        className={cn(
            "flex items-center gap-2 py-1.5 px-2 rounded-md hover:bg-muted cursor-pointer text-sm bg-card",
            level === 0 && "font-semibold"
        )}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={() => setOpen(!open)}
      >
        <span className="text-muted-foreground w-4 h-4 flex items-center justify-center shrink-0">
            {hasChildren ? (
                open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
            ) : <div className="w-4" />}
        </span>
        
        {hasChildren ? <Folder className="w-4 h-4 text-blue-500/80 shrink-0" /> : <FileText className="w-4 h-4 text-slate-500/80 shrink-0" />}
        
        <span className="truncate">{label}</span>
      </div>
      
      {hasChildren && open && (
        <div>
          {node.children.map((child, idx) => (
            <TreeNode key={idx} node={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function TaxonomyViewer() {
  const [targetId, setTargetId] = useState('shq_hybrid');
  const [searchTerm, setSearchTerm] = useState('');

  const { data: targetIdsData } = useQuery({
    queryKey: ['target-ids'],
    queryFn: getTargetIds,
  });

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['taxonomy', targetId],
    queryFn: () => getOurTaxonomy(targetId),
    enabled: false, 
  });

  const exportMutation = useMutation({
    mutationFn: ({ format }: { format: 'csv' | 'excel' }) => {
      return exportTaxonomyTree(targetId, format);
    },
    onSuccess: (blob, variables) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const extension = variables.format === 'excel' ? 'xlsx' : 'csv';
      a.href = url;
      a.download = `taxonomy_${targetId}_${new Date().toISOString().split('T')[0]}.${extension}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  });

  const handleLoad = () => {
    if (targetId) {
      refetch();
    }
  };

  return (
    <div className="space-y-6 h-[calc(100vh-100px)] flex flex-col">
      <div className="flex items-center justify-between shrink-0">
        <h1 className="text-3xl font-bold tracking-tight">Taxonomy Viewer</h1>
      </div>

      <Card className="shrink-0">
        <CardContent className="pt-6">
            <div className="flex gap-4 items-end">
                <div className="grid gap-2 flex-1">
                    <Label htmlFor="targetId">Target ID</Label>
                    <div className="flex gap-2">
                        <Select value={targetId} onValueChange={setTargetId}>
                            <SelectTrigger id="targetId" className="flex-1">
                                <SelectValue placeholder="Select target ID" />
                            </SelectTrigger>
                            <SelectContent>
                                {targetIdsData?.target_ids?.map((target) => (
                                    <SelectItem key={target.target_id} value={target.target_id}>
                                        {target.target_id}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Button onClick={handleLoad} disabled={isLoading}>
                            {isLoading ? "Loading..." : "Load"}
                        </Button>
                    </div>
                </div>
                <div className="grid gap-2 flex-1">
                    <Label htmlFor="search">Search</Label>
                    <Input
                        id="search"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        placeholder="Filter categories..."
                    />
                </div>
            </div>
            {error && (
                <Alert variant="destructive" className="mt-4">
                    <AlertDescription>{String(error)}</AlertDescription>
                </Alert>
            )}
        </CardContent>
      </Card>

      {data && (
        <Card className="flex-1 overflow-hidden flex flex-col min-h-0">
            <CardHeader className="py-4 border-b shrink-0">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Taxonomy Tree ({data.nodes.length} root nodes)</CardTitle>
                    <div className="flex gap-2">
                        <Button
                            onClick={() => exportMutation.mutate({ format: 'csv' })}
                            disabled={exportMutation.isPending}
                            variant="outline"
                            size="sm"
                            className="gap-2"
                        >
                            <FileDown className="h-4 w-4" />
                            {exportMutation.isPending ? "Exporting..." : "Export CSV"}
                        </Button>
                        <Button
                            onClick={() => exportMutation.mutate({ format: 'excel' })}
                            disabled={exportMutation.isPending}
                            variant="outline"
                            size="sm"
                            className="gap-2"
                        >
                            <FileDown className="h-4 w-4" />
                            {exportMutation.isPending ? "Exporting..." : "Export Excel"}
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto p-2">
                <div className="space-y-0.5">
                    {data.nodes.map((node, idx) => (
                        <TreeNode key={idx} node={node} />
                    ))}
                </div>
            </CardContent>
        </Card>
      )}
    </div>
  );
}
