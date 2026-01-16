import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { matchTaxonomy, getTargetIds, createMatchSession, updateMatchSession, exportMatchSession, getOurTaxonomy } from '../api/client';
import type { MatchResult, CandidateMatch, TaxonomyNode } from '../api/client';
import { useMatcherContext } from '../contexts/MatcherContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Search, RefreshCw, Play, Check, ChevronUp, ChevronDown, ChevronsUpDown, ChevronRight, Download, CheckCircle2, Settings, FileDown } from 'lucide-react';
import { exportMatchResults } from '../api/client';

type SortField = 'target_l1' | 'target_l2' | 'target_l3' | 'matched_l1' | 'matched_l2' | 'matched_l3' | 'confidence' | 'status';

function getConfidenceVariant(score: number): 'confidence-high' | 'confidence-good' | 'confidence-medium' | 'confidence-low' {
  if (score >= 0.9) return 'confidence-high';
  if (score >= 0.75) return 'confidence-good';
  if (score >= 0.5) return 'confidence-medium';
  return 'confidence-low';
}

function getConfidenceBorderColor(score: number): string {
  if (score >= 0.9) return 'border-l-[hsl(var(--confidence-high))]';
  if (score >= 0.75) return 'border-l-[hsl(var(--confidence-good))]';
  if (score >= 0.5) return 'border-l-[hsl(var(--confidence-medium))]';
  return 'border-l-[hsl(var(--confidence-low))]';
}

function getConfidenceBgColor(score: number): string {
  if (score >= 0.9) return 'bg-[hsl(var(--confidence-high))]/5';
  if (score >= 0.75) return 'bg-[hsl(var(--confidence-good))]/5';
  if (score >= 0.5) return 'bg-[hsl(var(--confidence-medium))]/5';
  return 'bg-[hsl(var(--confidence-low))]/5';
}

function getConfidenceProgressColor(score: number): string {
  if (score >= 0.9) return 'bg-[hsl(var(--confidence-high))]';
  if (score >= 0.75) return 'bg-[hsl(var(--confidence-good))]';
  if (score >= 0.5) return 'bg-[hsl(var(--confidence-medium))]';
  return 'bg-[hsl(var(--confidence-low))]';
}

export default function Matcher() {
  const { data: targetIdsData } = useQuery({
    queryKey: ['target-ids'],
    queryFn: getTargetIds,
  });

  const { state, setState, updateValidation } = useMatcherContext();
  const {
    ourTargetId,
    clientTargetId,
    threshold,
    results,
    expandedRow,
    sortField,
    sortDirection,
    statusFilter,
    confidenceMin,
    confidenceMax,
    validationStates,
  } = state;

  const [sessionId, setSessionId] = useState<number | null>(null);
  const [validationFilter, setValidationFilter] = useState<'all' | 'pending' | 'validated' | 'rejected'>('all');
  const [advancedSettingsOpen, setAdvancedSettingsOpen] = useState(false);
  const [manualSearch, setManualSearch] = useState('');

  const { data: ourTaxonomyData } = useQuery({
    queryKey: ['our-taxonomy', ourTargetId],
    queryFn: () => getOurTaxonomy(ourTargetId),
    enabled: !!ourTargetId,
  });

  const allOurCategories = useMemo(() => {
    if (!ourTaxonomyData?.nodes) return [];
    
    const flattened: any[] = [];
    const traverse = (node: TaxonomyNode, l1: string = '', l2: string = '') => {
      const currentL1 = node.l1 || l1;
      const currentL2 = node.l2 || l2;
      if (node.l3) {
        flattened.push({
          l1: currentL1,
          l2: currentL2,
          l3: node.l3,
          definition: node.definition,
        });
      }
      if (node.children) {
        node.children.forEach((child: TaxonomyNode) => traverse(child, currentL1, currentL2));
      }
    };
    ourTaxonomyData.nodes.forEach((node: TaxonomyNode) => traverse(node));
    return flattened;
  }, [ourTaxonomyData]);

  const manualSearchResults = useMemo(() => {
    if (!manualSearch || manualSearch.length < 2) return [];
    const search = manualSearch.toLowerCase();
    return allOurCategories.filter(cat => 
      cat.l3.toLowerCase().includes(search) || 
      cat.l2.toLowerCase().includes(search) || 
      (cat.l1 && cat.l1.toLowerCase().includes(search))
    ).slice(0, 10);
  }, [manualSearch, allOurCategories]);

  const matchMutation = useMutation({
    mutationFn: () => matchTaxonomy(ourTargetId, clientTargetId, threshold),
    onSuccess: async (data) => {
      setState({ results: data.results, expandedRow: null });
      // Create a match session
      try {
        const session = await createMatchSession({
          our_target_id: ourTargetId,
          client_target_id: clientTargetId,
          threshold,
          results: data.results,
        });
        setSessionId(session.id);
        // Initialize all as pending
        const initialStates: Record<string, 'pending' | 'validated' | 'rejected'> = {};
        data.results.forEach((r) => {
          initialStates[r.target_l3] = 'pending';
        });
        setState({ validationStates: initialStates });
      } catch (error) {
        console.error('Failed to create match session:', error);
      }
    },
  });

  const updateValidationMutation = useMutation({
    mutationFn: (states: Record<string, 'pending' | 'validated' | 'rejected'>) => {
      if (!sessionId) throw new Error('No session ID');
      return updateMatchSession(sessionId, { validation_states: states });
    },
    onSuccess: (data) => {
      setState({ validationStates: data.validation_states as Record<string, 'pending' | 'validated' | 'rejected'> });
    },
  });

  const exportMutation = useMutation({
    mutationFn: () => {
      if (!sessionId) throw new Error('No session ID');
      return exportMatchSession(sessionId);
    },
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `match_session_${sessionId}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  });

  const exportResultsMutation = useMutation({
    mutationFn: ({ format }: { format: 'csv' | 'excel' }) => {
      return exportMatchResults(filteredAndSortedResults, validationStates, format);
    },
    onSuccess: (blob, variables) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const extension = variables.format === 'excel' ? 'xlsx' : 'csv';
      a.href = url;
      a.download = `match_results_${new Date().toISOString().split('T')[0]}.${extension}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
  });

  const handleMatch = () => {
    if (!clientTargetId) {
      alert('Please enter a client target ID');
      return;
    }
    matchMutation.mutate();
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortDirection === 'desc') {
        setState({ sortDirection: 'asc' });
      } else if (sortDirection === 'asc') {
        setState({ sortField: 'confidence', sortDirection: 'desc' });
      }
    } else {
      setState({ sortField: field, sortDirection: 'desc' });
    }
  };

  const handleAcceptMatch = (result: MatchResult, candidate: CandidateMatch) => {
    const updatedResults = results.map((r) =>
      r.target_l3 === result.target_l3
        ? {
            ...r,
            matched_l1: candidate.l1,
            matched_l2: candidate.l2,
            matched_l3: candidate.l3,
            confidence: candidate.score,
            status: 'manual',
          }
        : r
    );
    setState({ results: updatedResults, expandedRow: null });
  };

  const handleAutoAccept = () => {
    const updatedResults = results.map((r) => {
      if (r.confidence >= threshold && r.status === 'review') {
        return { ...r, status: 'auto' };
      }
      return r;
    });
    setState({ results: updatedResults });
  };

  const handleValidate = (targetL3: string, status: 'validated' | 'rejected') => {
    const newStates = { ...validationStates, [targetL3]: status };
    updateValidation(targetL3, status);
    if (sessionId) {
      updateValidationMutation.mutate(newStates);
    }
  };

  const validatedCount = Object.values(validationStates).filter((v) => v === 'validated').length;
  const pendingCount = results.length - validatedCount;
  const allValidated = results.length > 0 && validatedCount === results.length;

  const filteredAndSortedResults = useMemo(() => {
    let filtered = results.filter((r) => {
      if (statusFilter !== 'all' && r.status !== statusFilter) return false;
      if (r.confidence < confidenceMin || r.confidence > confidenceMax) return false;
      if (validationFilter !== 'all') {
        const valStatus = validationStates[r.target_l3] || 'pending';
        if (validationFilter !== valStatus) return false;
      }
      return true;
    });

    if (sortDirection) {
      filtered = [...filtered].sort((a, b) => {
        let aVal: any = a[sortField];
        let bVal: any = b[sortField];
        
        if (typeof aVal === 'string') {
          aVal = aVal.toLowerCase();
          bVal = bVal.toLowerCase();
        }
        
        if (sortDirection === 'asc') {
          return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
        } else {
          return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
        }
      });
    }

    return filtered;
  }, [results, sortField, sortDirection, statusFilter, confidenceMin, confidenceMax, validationFilter, validationStates]);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <ChevronsUpDown className="h-4 w-4 ml-1 opacity-50" />;
    }
    if (sortDirection === 'asc') {
      return <ChevronUp className="h-4 w-4 ml-1" />;
    }
    if (sortDirection === 'desc') {
      return <ChevronDown className="h-4 w-4 ml-1" />;
    }
    return <ChevronsUpDown className="h-4 w-4 ml-1 opacity-50" />;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">Hybrid Matcher</h1>
      </div>

      <Card>
        <CardContent className="pt-6">
            <div className="grid gap-4 md:grid-cols-2 items-end">
                <div className="grid gap-2">
                    <Label htmlFor="ourTargetId">Our Target ID</Label>
                    <Select value={ourTargetId} onValueChange={(val) => setState({ ourTargetId: val })}>
                        <SelectTrigger id="ourTargetId">
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
                </div>
                <div className="grid gap-2">
                    <Label htmlFor="clientTargetId">Client Target ID</Label>
                    <Select value={clientTargetId} onValueChange={(val) => setState({ clientTargetId: val })}>
                        <SelectTrigger id="clientTargetId">
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
                </div>
            </div>
            
            <Collapsible open={advancedSettingsOpen} onOpenChange={setAdvancedSettingsOpen} className="mt-4">
                <CollapsibleTrigger asChild>
                    <Button variant="outline" className="w-full justify-between">
                        <span className="flex items-center gap-2">
                            <Settings className="h-4 w-4" />
                            Advanced Settings (Thresholds & Filters)
                        </span>
                        <ChevronDown className={`h-4 w-4 transition-transform ${advancedSettingsOpen ? 'rotate-180' : ''}`} />
                    </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-4 space-y-4 border-t pt-4">
                    <div className="grid gap-4 md:grid-cols-3">
                        <div className="grid gap-2">
                            <Label htmlFor="threshold">Confidence Threshold ({threshold})</Label>
                            <Input
                                id="threshold"
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                value={threshold}
                                onChange={(e) => setState({ threshold: parseFloat(e.target.value) })}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label>Min Confidence</Label>
                            <Input
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                value={confidenceMin}
                                onChange={(e) => setState({ confidenceMin: parseFloat(e.target.value) || 0 })}
                            />
                        </div>
                        <div className="grid gap-2">
                            <Label>Max Confidence</Label>
                            <Input
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                value={confidenceMax}
                                onChange={(e) => setState({ confidenceMax: parseFloat(e.target.value) || 1 })}
                            />
                        </div>
                    </div>
                </CollapsibleContent>
            </Collapsible>
            <div className="flex gap-2 mt-4">
                <Button 
                    onClick={handleMatch} 
                    disabled={matchMutation.isPending}
                    className="gap-2"
                >
                    {matchMutation.isPending ? <RefreshCw className="animate-spin h-4 w-4" /> : <Play className="h-4 w-4" />}
                    Run Matching
                </Button>
                <Button variant="outline" onClick={handleAutoAccept} className="gap-2">
                    <Check className="h-4 w-4" />
                    Auto-Accept High Confidence
                </Button>
            </div>

            {matchMutation.isError && (
                <Alert variant="destructive" className="mt-4">
                    <AlertDescription>{String(matchMutation.error)}</AlertDescription>
                </Alert>
            )}

            {results.length > 0 && (
                <div className="mt-4 space-y-2">
                    <Alert className="bg-primary/10 border-primary/20 text-primary-foreground">
                        <AlertDescription className="text-foreground">
                            Matched: {results.filter((r) => r.matched_l3).length} / {results.length} | Avg Confidence:{' '}
                            {(results.reduce((sum, r) => sum + r.confidence, 0) / results.length).toFixed(3)}
                        </AlertDescription>
                    </Alert>
                    <Alert className="bg-muted border">
                        <AlertDescription className="flex items-center justify-between flex-wrap gap-2">
                            <span>
                                <strong>Validation Progress:</strong> {validatedCount} validated, {pendingCount} pending
                            </span>
                            <div className="flex gap-2">
                                <Button
                                    onClick={() => exportResultsMutation.mutate({ format: 'csv' })}
                                    disabled={exportResultsMutation.isPending}
                                    variant="outline"
                                    className="gap-2"
                                >
                                    <FileDown className="h-4 w-4" />
                                    {exportResultsMutation.isPending ? "Exporting..." : "Export CSV"}
                                </Button>
                                <Button
                                    onClick={() => exportResultsMutation.mutate({ format: 'excel' })}
                                    disabled={exportResultsMutation.isPending}
                                    variant="outline"
                                    className="gap-2"
                                >
                                    <FileDown className="h-4 w-4" />
                                    {exportResultsMutation.isPending ? "Exporting..." : "Export Excel"}
                                </Button>
                                <Button
                                    onClick={() => exportMutation.mutate()}
                                    disabled={!allValidated || exportMutation.isPending}
                                    className="gap-2"
                                    variant={allValidated ? "default" : "outline"}
                                >
                                    <Download className="h-4 w-4" />
                                    {exportMutation.isPending ? "Exporting..." : "Export Validated"}
                                </Button>
                            </div>
                        </AlertDescription>
                    </Alert>
                </div>
            )}
        </CardContent>
      </Card>

      {results.length > 0 && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Filters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-2">
                  <Label>Validation Status</Label>
                  <Select value={validationFilter} onValueChange={(val: any) => setValidationFilter(val)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="validated">Validated</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>Match Status</Label>
                  <Select value={statusFilter} onValueChange={(val) => setState({ statusFilter: val })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All</SelectItem>
                      <SelectItem value="auto">Auto</SelectItem>
                      <SelectItem value="manual">Manual</SelectItem>
                      <SelectItem value="review">Review</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Matching Results ({filteredAndSortedResults.length})</CardTitle>
                <div className="flex gap-2">
                  <Button
                    onClick={() => exportResultsMutation.mutate({ format: 'csv' })}
                    disabled={exportResultsMutation.isPending}
                    variant="outline"
                    size="sm"
                    className="gap-2"
                  >
                    <FileDown className="h-4 w-4" />
                    CSV
                  </Button>
                  <Button
                    onClick={() => exportResultsMutation.mutate({ format: 'excel' })}
                    disabled={exportResultsMutation.isPending}
                    variant="outline"
                    size="sm"
                    className="gap-2"
                  >
                    <FileDown className="h-4 w-4" />
                    Excel
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
                <Table className="text-xs table-fixed w-full">
                    <TableHeader>
                    <TableRow>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none transition-colors w-[10%] level-l1-bg"
                          onClick={() => handleSort('target_l1')}
                        >
                          <div className="flex items-center truncate">
                            Client L1
                            <SortIcon field="target_l1" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none bg-card w-[10%] level-l2-bg"
                          onClick={() => handleSort('target_l2')}
                        >
                          <div className="flex items-center truncate">
                            Client L2
                            <SortIcon field="target_l2" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none bg-card w-[12%] level-l3-bg"
                          onClick={() => handleSort('target_l3')}
                        >
                          <div className="flex items-center truncate">
                            Client L3
                            <SortIcon field="target_l3" />
                          </div>
                        </TableHead>
                        <TableHead className="w-[2%] bg-muted border-l-2 border-r-2 border-border"></TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none bg-card w-[10%] level-l1-bg"
                          onClick={() => handleSort('matched_l1')}
                        >
                          <div className="flex items-center truncate">
                            Matched L1
                            <SortIcon field="matched_l1" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none bg-card w-[10%] level-l2-bg"
                          onClick={() => handleSort('matched_l2')}
                        >
                          <div className="flex items-center truncate">
                            Matched L2
                            <SortIcon field="matched_l2" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none bg-card w-[12%] level-l3-bg"
                          onClick={() => handleSort('matched_l3')}
                        >
                          <div className="flex items-center truncate">
                            Matched L3
                            <SortIcon field="matched_l3" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none bg-card w-[8%]"
                          onClick={() => handleSort('confidence')}
                        >
                          <div className="flex items-center">
                            Conf.
                            <SortIcon field="confidence" />
                          </div>
                        </TableHead>
                        <TableHead 
                          className="cursor-pointer hover:bg-muted select-none bg-card w-[8%]"
                          onClick={() => handleSort('status')}
                        >
                          <div className="flex items-center">
                            Status
                            <SortIcon field="status" />
                          </div>
                        </TableHead>
                        <TableHead className="w-[9%]">Validation</TableHead>
                        <TableHead className="w-8"></TableHead>
                    </TableRow>
                    </TableHeader>
                    <TableBody>
                    {filteredAndSortedResults.map((result, idx) => {
                      const isExpanded = expandedRow === idx;
                      const confidenceVariant = getConfidenceVariant(result.confidence);
                      const borderColor = getConfidenceBorderColor(result.confidence);
                      const bgColor = getConfidenceBgColor(result.confidence);
                      
                      return (
                        <>
                          <TableRow
                            key={idx}
                            className={`cursor-pointer hover:bg-muted transition-all border-l-4 ${borderColor} ${bgColor} hover:shadow-sm`}
                            onClick={() => {
                              setState({ expandedRow: isExpanded ? null : idx });
                              setManualSearch('');
                            }}
                          >
                            <TableCell className="p-2 truncate level-l1-bg" title={result.target_l1}>{result.target_l1}</TableCell>
                            <TableCell className="p-2 truncate level-l2-bg" title={result.target_l2}>{result.target_l2}</TableCell>
                            <TableCell className="font-medium p-2 truncate level-l3-bg" title={result.target_l3}>{result.target_l3}</TableCell>
                            <TableCell className="p-2 bg-muted border-l-2 border-r-2 border-border"></TableCell>
                            <TableCell className="p-2 truncate level-l1-bg" title={result.matched_l1}>{result.matched_l1}</TableCell>
                            <TableCell className="p-2 truncate level-l2-bg" title={result.matched_l2}>{result.matched_l2}</TableCell>
                            <TableCell className="p-2 truncate level-l3-bg" title={result.matched_l3}>{result.matched_l3}</TableCell>
                            <TableCell className="p-2">
                                <Badge variant={confidenceVariant} className="text-[10px] px-1 h-5">
                                    {result.confidence.toFixed(3)}
                                </Badge>
                            </TableCell>
                            <TableCell className="p-2">
                                <Badge variant={result.status === 'auto' ? 'default' : result.status === 'manual' ? 'outline' : 'secondary'} className="text-[10px] px-1 h-5">
                                    {result.status}
                                </Badge>
                            </TableCell>
                            <TableCell className="p-2">
                              <div className="flex gap-1">
                                {validationStates[result.target_l3] === 'validated' ? (
                                  <Badge variant="default" className="bg-green-600 text-[10px] px-1 h-5">
                                    <CheckCircle2 className="w-2 h-2 mr-1" />
                                    OK
                                  </Badge>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="default"
                                    className="h-6 px-2 text-[10px] bg-green-600 hover:bg-green-700"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleValidate(result.target_l3, 'validated');
                                    }}
                                  >
                                    <Check className="w-2 h-2 mr-1" />
                                    Valid
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="p-2 text-right">
                              <ChevronRight 
                                className={`h-3 w-3 inline-block transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                              />
                            </TableCell>
                          </TableRow>
                          {isExpanded && (
                            <TableRow key={`${idx}-expanded`} className="bg-muted">
                              <TableCell colSpan={10} className="p-0 bg-muted">
                                <div className="p-6 bg-muted border-t">
                                  <div className="grid md:grid-cols-2 gap-6 mb-6">
                                    <div className="space-y-3">
                                      <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">Client Taxonomy</h4>
                                      <div className="space-y-2 p-4 bg-background rounded-md border">
                                        <div className="p-2 rounded level-l1-bg">
                                          <span className="text-xs text-muted-foreground">L1:</span>
                                          <p className="font-medium">{result.target_l1 || <span className="text-muted-foreground italic">N/A</span>}</p>
                                        </div>
                                        <div className="p-2 rounded level-l2-bg">
                                          <span className="text-xs text-muted-foreground">L2:</span>
                                          <p className="font-medium">{result.target_l2}</p>
                                        </div>
                                        <div className="p-2 rounded level-l3-bg">
                                          <span className="text-xs text-muted-foreground">L3:</span>
                                          <p className="font-medium text-lg">{result.target_l3}</p>
                                        </div>
                                      </div>
                                    </div>
                                    <div className="space-y-3">
                                      <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">Matched Taxonomy</h4>
                                      <div className="space-y-2 p-4 bg-background rounded-md border">
                                        <div className="p-2 rounded level-l1-bg">
                                          <span className="text-xs text-muted-foreground">L1:</span>
                                          <p className="font-medium">{result.matched_l1 || <span className="text-muted-foreground italic">N/A</span>}</p>
                                        </div>
                                        <div className="p-2 rounded level-l2-bg">
                                          <span className="text-xs text-muted-foreground">L2:</span>
                                          <p className="font-medium">{result.matched_l2}</p>
                                        </div>
                                        <div className="p-2 rounded level-l3-bg">
                                          <span className="text-xs text-muted-foreground">L3:</span>
                                          <p className="font-medium text-lg">{result.matched_l3}</p>
                                        </div>
                                        {result.reasoning && (
                                          <div className="mt-3 pt-3 border-t">
                                            <span className="text-xs text-muted-foreground">Reasoning:</span>
                                            <p className="text-sm mt-1">{result.reasoning}</p>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                  
                                  <div className="space-y-3">
                                    <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">Top Candidates</h4>
                                    <div className="space-y-2">
                                      {result.top_3_candidates.map((candidate, candidateIdx) => {
                                        const isCurrentMatch = 
                                          candidate.l1 === result.matched_l1 &&
                                          candidate.l2 === result.matched_l2 &&
                                          candidate.l3 === result.matched_l3;
                                        const candidateVariant = getConfidenceVariant(candidate.score);
                                        
                                        return (
                                          <div
                                            key={candidateIdx}
                                            className={`p-4 border-2 rounded-lg transition-all cursor-pointer bg-card hover:shadow-md ${
                                              isCurrentMatch 
                                                ? 'border-primary bg-primary/10 ring-2 ring-primary/20' 
                                                : 'border-border hover:border-primary/50 hover:bg-muted'
                                            }`}
                                            onClick={() => handleAcceptMatch(result, candidate)}
                                          >
                                            <div className="flex justify-between items-start gap-4">
                                              <div className="flex-1 space-y-2">
                                                <div className="flex items-center gap-2">
                                                  {candidate.l1 && (
                                                    <span className="text-xs text-muted-foreground">{candidate.l1}</span>
                                                  )}
                                                  <span className="font-medium">{candidate.l2}</span>
                                                  <span className="text-muted-foreground">&gt;</span>
                                                  <span className="font-semibold">{candidate.l3}</span>
                                                  {isCurrentMatch && (
                                                    <Badge variant="outline" className="ml-2">Current</Badge>
                                                  )}
                                                </div>
                                                {candidate.definition && (
                                                  <p className="text-sm text-muted-foreground line-clamp-2">{candidate.definition}</p>
                                                )}
                                                <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                                                  <div 
                                                    className={`h-full transition-all ${getConfidenceProgressColor(candidate.score)}`}
                                                    style={{ width: `${candidate.score * 100}%` }}
                                                  />
                                                </div>
                                              </div>
                                              <Badge variant={candidateVariant} className="shrink-0">
                                                {candidate.score.toFixed(3)}
                                              </Badge>
                                            </div>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>

                                  <div className="space-y-3 mt-6 pt-6 border-t">
                                    <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">Manual Selection</h4>
                                    <div className="space-y-4">
                                      <div className="relative">
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                        <Input
                                          placeholder={`Search in all categories of ${ourTargetId}...`}
                                          className="pl-9"
                                          value={manualSearch}
                                          onChange={(e) => setManualSearch(e.target.value)}
                                        />
                                      </div>
                                      
                                      {manualSearchResults.length > 0 && (
                                        <div className="grid gap-2 max-h-[300px] overflow-y-auto p-1">
                                          {manualSearchResults.map((candidate, candidateIdx) => (
                                            <div
                                              key={`manual-${candidateIdx}`}
                                              className="p-3 border rounded-md hover:bg-accent hover:text-accent-foreground cursor-pointer transition-colors shadow-sm"
                                              onClick={() => {
                                                handleAcceptMatch(result, {
                                                  l1: candidate.l1,
                                                  l2: candidate.l2,
                                                  l3: candidate.l3,
                                                  score: 1.0,
                                                  definition: candidate.definition
                                                });
                                                setManualSearch('');
                                              }}
                                            >
                                              <div className="flex items-center gap-2 text-sm">
                                                {candidate.l1 && (
                                                  <span className="text-muted-foreground">{candidate.l1} &gt;</span>
                                                )}
                                                <span className="font-medium">{candidate.l2} &gt;</span>
                                                <span className="font-bold text-primary">{candidate.l3}</span>
                                              </div>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                      
                                      {manualSearch.length >= 2 && manualSearchResults.length === 0 && (
                                        <p className="text-sm text-muted-foreground text-center py-4">
                                          No matching categories found in {ourTargetId}
                                        </p>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </>
                      );
                    })}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
        </>
      )}
    </div>
  );
}
