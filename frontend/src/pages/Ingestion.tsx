import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import { uploadTaxonomy, ingestTaxonomy, augmentTaxonomy } from '../api/client';
import type { ColumnMapping } from '../api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Check, Upload, Database, Wand2, FileSpreadsheet } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Textarea } from '@/components/ui/textarea';

const steps = [
    { label: 'Upload', icon: Upload },
    { label: 'Ingest', icon: Database },
    { label: 'Augment', icon: Wand2 }
];

export default function Ingestion() {
  const [activeStep, setActiveStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [targetId, setTargetId] = useState('');
  const [columns, setColumns] = useState<string[]>([]);
  const [columnMapping, setColumnMapping] = useState<ColumnMapping>({
    l3: '',
  });
  const [promptTemplate, setPromptTemplate] = useState('');
  const [llmModel, setLlmModel] = useState('');

  const queryClient = useQueryClient();

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xlsx'],
    },
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        const file = acceptedFiles[0];
        setFile(file);
        const reader = new FileReader();
        reader.onload = (e) => {
          const text = e.target?.result as string;
          const firstLine = text.split('\n')[0];
          const headers = firstLine.split(',').map((h) => h.trim());
          setColumns(headers);
        };
        reader.readAsText(file);
      }
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => uploadTaxonomy(file!, targetId, columnMapping),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const ingestMutation = useMutation({
    mutationFn: () => ingestTaxonomy(targetId, false),
    onSuccess: () => {
      setActiveStep(2);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const augmentMutation = useMutation({
    mutationFn: () => augmentTaxonomy(targetId, promptTemplate || undefined, llmModel || undefined),
    onSuccess: () => {
      setActiveStep(3);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const handleNext = () => {
    if (activeStep === 0) {
      if (!columnMapping.l3) {
        alert('Please select L3 column');
        return;
      }
      uploadMutation.mutate();
    } else if (activeStep === 1) {
      ingestMutation.mutate();
    } else if (activeStep === 2) {
      augmentMutation.mutate();
    }
  };

  useEffect(() => {
    if (uploadMutation.isSuccess && activeStep === 0) {
      setActiveStep(1);
    }
  }, [uploadMutation.isSuccess, activeStep]);

  useEffect(() => {
    if (ingestMutation.isSuccess && activeStep === 1) {
      setActiveStep(2);
    }
  }, [ingestMutation.isSuccess, activeStep]);

  useEffect(() => {
    if (augmentMutation.isSuccess && activeStep === 2) {
      setActiveStep(3);
    }
  }, [augmentMutation.isSuccess, activeStep]);

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Taxonomy Ingestion</h1>
        <p className="text-muted-foreground mt-2">
            Upload, ingest, and augment your taxonomy data.
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center justify-between mb-8">
        {steps.map((step, index) => {
            const Icon = step.icon;
            const isCompleted = activeStep > index;
            const isCurrent = activeStep === index;
            
            return (
                <div key={step.label} className={cn("flex flex-col items-center gap-2 flex-1 relative", 
                    index !== steps.length - 1 && "after:content-[''] after:absolute after:top-5 after:left-1/2 after:w-full after:h-[2px] after:bg-border after:-z-10",
                    isCompleted && index !== steps.length - 1 && "after:bg-primary"
                )}>
                    <div className={cn("w-10 h-10 rounded-full flex items-center justify-center border-2 bg-background z-10 transition-colors",
                        isCompleted ? "border-primary bg-primary text-primary-foreground" : 
                        isCurrent ? "border-primary text-primary" : "border-muted-foreground/30 text-muted-foreground"
                    )}>
                        {isCompleted ? <Check className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
                    </div>
                    <span className={cn("text-sm font-medium", isCurrent ? "text-foreground" : "text-muted-foreground")}>
                        {step.label}
                    </span>
                </div>
            )
        })}
      </div>

      <Card>
        <CardHeader>
            <CardTitle>
                {activeStep === 0 && "Upload & Map"}
                {activeStep === 1 && "Ingest Embeddings"}
                {activeStep === 2 && "Augment Descriptions"}
                {activeStep === 3 && "Completed"}
            </CardTitle>
            <CardDescription>
                {activeStep === 0 && "Upload your taxonomy CSV file and map the columns to the schema."}
                {activeStep === 1 && "Generate embeddings for semantic search."}
                {activeStep === 2 && "Use LLM to generate descriptions for your categories."}
                {activeStep === 3 && "All steps completed successfully."}
            </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
            {activeStep === 0 && (
                <>
                    <div className="grid w-full items-center gap-1.5">
                        <Label htmlFor="targetId">Target ID</Label>
                        <Input 
                            id="targetId" 
                            placeholder="e.g., zalando_taxonomy" 
                            value={targetId}
                            onChange={(e) => setTargetId(e.target.value)}
                        />
                    </div>

                    <div {...getRootProps()} className={cn(
                        "border-2 border-dashed rounded-lg p-10 text-center cursor-pointer hover:bg-muted transition-colors bg-card",
                        isDragActive ? "border-primary bg-muted" : "border-muted-foreground/25"
                    )}>
                        <input {...getInputProps()} />
                        <div className="flex flex-col items-center gap-2">
                            <FileSpreadsheet className="w-10 h-10 text-muted-foreground" />
                            {file ? (
                                <span className="font-medium">{file.name}</span>
                            ) : (
                                <div className="space-y-1">
                                    <p className="font-medium">Drop your file here</p>
                                    <p className="text-sm text-muted-foreground">or click to browse</p>
                                </div>
                            )}
                        </div>
                    </div>

                    {columns.length > 0 && (
                        <div className="grid gap-4 sm:grid-cols-2">
                             <div className="grid gap-2">
                                <Label>L3 Column (Required)</Label>
                                <Select value={columnMapping.l3} onValueChange={(val) => setColumnMapping({ ...columnMapping, l3: val })}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select column" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {columns.map(col => <SelectItem key={col} value={col}>{col}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                             </div>
                             <div className="grid gap-2">
                                <Label>L2 Column</Label>
                                <Select value={columnMapping.l2 || "none"} onValueChange={(val) => setColumnMapping({ ...columnMapping, l2: val === "none" ? undefined : val })}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select column" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">None</SelectItem>
                                        {columns.map(col => <SelectItem key={col} value={col}>{col}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                             </div>
                             <div className="grid gap-2">
                                <Label>L1 Column</Label>
                                <Select value={columnMapping.l1 || "none"} onValueChange={(val) => setColumnMapping({ ...columnMapping, l1: val === "none" ? undefined : val })}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select column" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">None</SelectItem>
                                        {columns.map(col => <SelectItem key={col} value={col}>{col}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                             </div>
                             <div className="grid gap-2">
                                <Label>Definition Column</Label>
                                <Select value={columnMapping.definition || "none"} onValueChange={(val) => setColumnMapping({ ...columnMapping, definition: val === "none" ? undefined : val })}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select column" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">None</SelectItem>
                                        {columns.map(col => <SelectItem key={col} value={col}>{col}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                             </div>
                        </div>
                    )}
                    
                    <Button 
                        onClick={handleNext} 
                        disabled={!targetId || !columnMapping.l3 || uploadMutation.isPending}
                        className="w-full"
                    >
                        {uploadMutation.isPending ? "Uploading..." : "Upload & Continue"}
                    </Button>
                </>
            )}

            {activeStep === 1 && (
                <div className="space-y-4">
                    <Alert>
                        <AlertDescription>
                            Embeddings generation can take a few minutes depending on the taxonomy size.
                        </AlertDescription>
                    </Alert>
                    <Button 
                        onClick={handleNext} 
                        disabled={ingestMutation.isPending}
                        className="w-full"
                    >
                        {ingestMutation.isPending ? "Ingesting..." : "Ingest Embeddings"}
                    </Button>
                </div>
            )}

            {activeStep === 2 && (
                <div className="space-y-4">
                    <div className="grid w-full gap-1.5">
                        <Label htmlFor="prompt">Prompt Template (Optional)</Label>
                        <Textarea 
                            id="prompt"
                            placeholder="Use {l1}, {l2}, {l3}, {definition} as placeholders"
                            value={promptTemplate}
                            onChange={(e) => setPromptTemplate(e.target.value)}
                            rows={4}
                        />
                    </div>
                    <div className="grid w-full gap-1.5">
                        <Label htmlFor="model">LLM Model (Optional)</Label>
                        <Input
                            id="model"
                            value={llmModel}
                            onChange={(e) => setLlmModel(e.target.value)}
                        />
                    </div>
                    <Button 
                        onClick={handleNext} 
                        disabled={augmentMutation.isPending}
                        className="w-full"
                    >
                        {augmentMutation.isPending ? "Generating..." : "Generate Descriptions"}
                    </Button>
                </div>
            )}

            {activeStep === 3 && (
                <div className="flex flex-col items-center justify-center py-6 text-center space-y-4">
                    <div className="w-12 h-12 rounded-full bg-green-100 text-green-600 flex items-center justify-center">
                        <Check className="w-6 h-6" />
                    </div>
                    <h3 className="font-semibold text-lg">Taxonomy Ingestion Complete!</h3>
                    <p className="text-muted-foreground">Your taxonomy has been successfully processed and is ready for matching.</p>
                </div>
            )}

            {/* Error Messages */}
            {(uploadMutation.isError || ingestMutation.isError || augmentMutation.isError) && (
                <Alert variant="destructive">
                    <AlertDescription>
                        {String(uploadMutation.error || ingestMutation.error || augmentMutation.error)}
                    </AlertDescription>
                </Alert>
            )}
        </CardContent>
      </Card>
    </div>
  );
}
