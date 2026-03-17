"use client";

import { useMemo, useState, type ReactNode } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getKnowledgeDocuments,
  uploadKnowledgeDocument,
  updateKnowledgeDocument,
  deleteKnowledgeDocument,
  getKnowledgeStats,
} from "@/lib/api";
import type {
  KnowledgeDocument,
  KnowledgeDocumentCategory,
  KnowledgeDocumentUpdate,
} from "@/lib/types";
import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/lib/auth";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowUpRight,
  BookMarked,
  Files,
  FileText,
  Upload,
  Trash2,
  BookOpen,
  Scale,
  FileCheck,
  AlertCircle,
  Loader2,
  PencilLine,
  Search,
  Link2,
} from "lucide-react";

const CATEGORY_LABELS: Record<KnowledgeDocumentCategory, string> = {
  LAW: "Law",
  CASE_LAW: "Case Law",
  REGULATION: "Regulation",
  GUIDELINE: "Guideline",
};

const CATEGORY_ICONS: Record<KnowledgeDocumentCategory, ReactNode> = {
  LAW: <Scale className="h-4 w-4" />,
  CASE_LAW: <BookOpen className="h-4 w-4" />,
  REGULATION: <FileCheck className="h-4 w-4" />,
  GUIDELINE: <FileText className="h-4 w-4" />,
};

const CATEGORY_OPTIONS: Array<{
  value: KnowledgeDocumentCategory;
  label: string;
  helper: string;
}> = [
  { value: "LAW", label: "Law", helper: "Acts of Parliament and statutes" },
  { value: "CASE_LAW", label: "Case Law", helper: "Court decisions and precedents" },
  { value: "REGULATION", label: "Regulation", helper: "PPADR, circulars, and compliance rules" },
  { value: "GUIDELINE", label: "Guideline", helper: "PPRA, EACC, and policy guidance" },
];

type DocumentFormState = {
  title: string;
  category: KnowledgeDocumentCategory;
  description: string;
  sourceUrl: string;
};

const EMPTY_DOCUMENT_FORM: DocumentFormState = {
  title: "",
  category: "LAW",
  description: "",
  sourceUrl: "",
};

function formatDocumentPayload(form: DocumentFormState): KnowledgeDocumentUpdate {
  return {
    title: form.title.trim(),
    category: form.category,
    description: form.description.trim() || null,
    source_url: form.sourceUrl.trim() || null,
  };
}

function KnowledgeBaseContent() {
  const queryClient = useQueryClient();
  const { isAdmin } = useAuth();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [editingDocument, setEditingDocument] = useState<KnowledgeDocument | null>(null);

  const [uploadForm, setUploadForm] = useState({
    file: null as File | null,
    ...EMPTY_DOCUMENT_FORM,
  });
  const [editForm, setEditForm] = useState<DocumentFormState>(EMPTY_DOCUMENT_FORM);

  const { data: documents, isLoading: docsLoading } = useQuery({
    queryKey: ["knowledge-documents"],
    queryFn: getKnowledgeDocuments,
  });

  const { data: stats } = useQuery({
    queryKey: ["knowledge-stats"],
    queryFn: getKnowledgeStats,
  });

  const uploadMutation = useMutation({
    mutationFn: () =>
      uploadKnowledgeDocument(
        uploadForm.file!,
        uploadForm.title.trim(),
        uploadForm.category,
        uploadForm.description.trim() || undefined,
        uploadForm.sourceUrl.trim() || undefined,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-stats"] });
      setUploadOpen(false);
      setUploadForm({
        file: null,
        ...EMPTY_DOCUMENT_FORM,
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: KnowledgeDocumentUpdate }) =>
      updateKnowledgeDocument(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-stats"] });
      setEditingDocument(null);
      setEditForm(EMPTY_DOCUMENT_FORM);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteKnowledgeDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-stats"] });
      setDeleteId(null);
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadForm((prev) => ({
        ...prev,
        file,
        title: prev.title || file.name.replace(/\.pdf$/i, ""),
      }));
    }
  };

  const filteredDocuments = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return documents ?? [];
    }
    return (documents ?? []).filter((doc) => {
      const haystack = [
        doc.title,
        doc.description ?? "",
        CATEGORY_LABELS[doc.category],
        doc.file_name ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [documents, searchQuery]);

  const handleEditOpen = (doc: KnowledgeDocument) => {
    setEditingDocument(doc);
    setEditForm({
      title: doc.title,
      category: doc.category,
      description: doc.description ?? "",
      sourceUrl: doc.source_url ?? "",
    });
  };

  const handleEditSave = () => {
    if (!editingDocument) {
      return;
    }
    updateMutation.mutate({
      id: editingDocument.id,
      data: formatDocumentPayload(editForm),
    });
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Card className="w-96">
          <CardContent className="pt-6 text-center">
            <AlertCircle className="h-12 w-12 mx-auto text-amber-500 mb-4" />
            <p className="text-lg font-medium">Admin Access Required</p>
            <p className="text-sm text-muted-foreground mt-2">
              Only administrators can manage the knowledge base.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl space-y-8 px-4 py-8 sm:px-6 lg:px-8">
      {/* Header Section */}
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">Knowledge Base</h1>
            <Badge variant="secondary" className="rounded-md px-2 py-0.5 text-xs font-medium">
              Admin
            </Badge>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground sm:text-base leading-relaxed">
            Curate the legal and policy corpus that grounds Sentinel’s analysis, citations, and case reasoning.
          </p>
          
          {/* Compact Stats */}
          <div className="flex flex-wrap items-center gap-4 text-sm mt-2">
            <div className="flex items-center gap-2 text-muted-foreground">
              <BookMarked className="h-4 w-4 text-primary/70" />
              <span className="font-medium text-foreground">{stats?.total_documents ?? 0}</span>
              <span>Documents</span>
            </div>
            <div className="h-4 w-px bg-border/60" />
            <div className="flex items-center gap-2 text-muted-foreground">
              <Files className="h-4 w-4 text-primary/70" />
              <span className="font-medium text-foreground">{stats?.total_chunks ?? 0}</span>
              <span>Chunks</span>
            </div>
            <div className="h-4 w-px bg-border/60" />
            <div className="flex items-center gap-2 text-muted-foreground">
              <Scale className="h-4 w-4 text-primary/70" />
              <span className="font-medium text-foreground">{stats?.by_category?.LAW ?? 0}</span>
              <span>Laws</span>
            </div>
            <div className="h-4 w-px bg-border/60" />
            <div className="flex items-center gap-2 text-muted-foreground">
              <Link2 className="h-4 w-4 text-primary/70" />
              <span className="font-medium text-foreground">{stats?.by_category?.REGULATION ?? 0}</span>
              <span>Regulations</span>
            </div>
          </div>
        </div>

        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger asChild>
            <Button size="default" className="w-full sm:w-auto shadow-sm">
              <Upload className="h-4 w-4 mr-2" />
              Upload Document
            </Button>
          </DialogTrigger>
            <DialogContent className="sm:max-w-2xl">
              <DialogHeader>
                <DialogTitle>Upload legal document</DialogTitle>
                <DialogDescription>
                  Upload a PDF document and enrich its metadata before Sentinel chunks and embeds it for retrieval.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="file">PDF file</Label>
                  <Input
                    id="file"
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    value={uploadForm.title}
                    onChange={(e) =>
                      setUploadForm((prev) => ({ ...prev, title: e.target.value }))
                    }
                    placeholder="Public Procurement and Asset Disposal Act 2015"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="category">Category</Label>
                  <Select
                    value={uploadForm.category}
                    onValueChange={(value) =>
                      setUploadForm((prev) => ({
                        ...prev,
                        category: value as KnowledgeDocumentCategory,
                      }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORY_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sourceUrl">Source URL</Label>
                  <Input
                    id="sourceUrl"
                    value={uploadForm.sourceUrl}
                    onChange={(e) =>
                      setUploadForm((prev) => ({ ...prev, sourceUrl: e.target.value }))
                    }
                    placeholder="https://..."
                  />
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={uploadForm.description}
                    onChange={(e) =>
                      setUploadForm((prev) => ({ ...prev, description: e.target.value }))
                    }
                    placeholder="Explain what investigators should know about this document."
                    rows={4}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setUploadOpen(false)}
                  disabled={uploadMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => uploadMutation.mutate()}
                  disabled={!uploadForm.file || !uploadForm.title.trim() || uploadMutation.isPending}
                >
                  {uploadMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    "Upload"
                  )}
                </Button>
              </DialogFooter>
              {uploadMutation.isError && (
                <p className="text-sm text-red-500">
                  {(uploadMutation.error as Error).message}
                </p>
              )}
            </DialogContent>
          </Dialog>
      </div>

      {/* Documents Table */}
      <Card className="border-border/70 bg-card/80 shadow-sm overflow-hidden border-t-4 border-t-primary/20">
        <CardHeader className="gap-4 lg:flex-row lg:items-end lg:justify-between bg-muted/20 pb-4 border-b border-border/40">
          <div>
            <CardTitle className="text-xl">Document Corpus</CardTitle>
            <CardDescription className="mt-1">
              Review metadata, update titles and sources, and keep the RAG corpus clean and current.
            </CardDescription>
          </div>
          <div className="relative w-full lg:w-80">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents..."
              className="pl-9 bg-background/50 focus-visible:bg-background"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {docsLoading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-muted-foreground">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted/50 mb-2">
                <FileText className="h-8 w-8 text-muted-foreground/60" />
              </div>
              <div className="space-y-1">
                <p className="text-lg font-medium text-foreground">
                  {documents?.length ? "No documents match your search" : "No documents uploaded yet"}
                </p>
                <p className="text-sm max-w-sm mx-auto">
                  {documents?.length
                    ? "Try a different keyword or clear the search to see the full corpus."
                    : "Upload your first legal document to start grounding Sentinel’s answers."}
                </p>
              </div>
            </div>
          ) : (
            <div className="w-full">
              <Table>
                <TableHeader className="bg-muted/50">
                  <TableRow className="hover:bg-transparent border-border/40">
                    <TableHead className="px-6 h-11 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Document</TableHead>
                    <TableHead className="h-11 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Category</TableHead>
                    <TableHead className="h-11 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Chunks</TableHead>
                    <TableHead className="h-11 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Uploaded by</TableHead>
                    <TableHead className="h-11 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Created</TableHead>
                    <TableHead className="h-11 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Source</TableHead>
                    <TableHead className="px-6 h-11 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDocuments.map((doc) => (
                    <TableRow key={doc.id} className="group hover:bg-muted/20 border-border/40 transition-colors">
                      <TableCell className="px-6 py-4 align-top whitespace-normal w-[35%]">
                        <div className="flex items-start gap-3">
                          <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border/50 bg-background shadow-sm text-primary/80">
                            {CATEGORY_ICONS[doc.category]}
                          </span>
                          <div className="min-w-0 space-y-1.5">
                            <p className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">{doc.title}</p>
                            <p className="line-clamp-2 text-xs text-muted-foreground leading-relaxed">
                              {doc.description ?? "No description provided yet."}
                            </p>
                            <p className="truncate text-[11px] font-mono text-muted-foreground/60">
                              {doc.file_name ?? "Uploaded PDF"}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="py-4 align-top">
                        <Badge variant="secondary" className="text-[10px] font-medium tracking-wide">
                          {CATEGORY_LABELS[doc.category]}
                        </Badge>
                      </TableCell>
                      <TableCell className="py-4 align-top">
                        <div className="inline-flex items-center justify-center rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
                          {doc.chunk_count}
                        </div>
                      </TableCell>
                      <TableCell className="py-4 align-top text-xs text-muted-foreground whitespace-normal">
                        {doc.uploaded_by ?? "Unknown"}
                      </TableCell>
                      <TableCell className="py-4 align-top text-xs text-muted-foreground">
                        {new Date(doc.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                      </TableCell>
                      <TableCell className="py-4 align-top">
                        {doc.source_url ? (
                          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs hover:bg-primary/10 hover:text-primary" asChild>
                            <a href={doc.source_url} target="_blank" rel="noreferrer">
                              Open Link
                              <ArrowUpRight className="h-3 w-3 ml-1" />
                            </a>
                          </Button>
                        ) : (
                          <span className="text-xs text-muted-foreground italic">No source</span>
                        )}
                      </TableCell>
                      <TableCell className="px-6 py-4 align-top">
                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-primary" onClick={() => handleEditOpen(doc)}>
                            <PencilLine className="h-4 w-4" />
                            <span className="sr-only">Edit</span>
                          </Button>
                          <Dialog
                            open={deleteId === doc.id}
                            onOpenChange={(open) => !open && setDeleteId(null)}
                          >
                            <DialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                                onClick={() => setDeleteId(doc.id)}
                              >
                                <Trash2 className="h-4 w-4" />
                                <span className="sr-only">Delete</span>
                              </Button>
                            </DialogTrigger>
                            <DialogContent>
                              <DialogHeader>
                                <DialogTitle>Delete document</DialogTitle>
                                <DialogDescription>
                                  Are you sure you want to delete &quot;{doc.title}&quot;? This will also remove all {doc.chunk_count} chunks and cannot be undone.
                                </DialogDescription>
                              </DialogHeader>
                              <DialogFooter>
                                <Button variant="outline" onClick={() => setDeleteId(null)}>
                                  Cancel
                                </Button>
                                <Button
                                  variant="destructive"
                                  onClick={() => deleteMutation.mutate(doc.id)}
                                  disabled={deleteMutation.isPending}
                                >
                                  {deleteMutation.isPending ? "Deleting..." : "Delete"}
                                </Button>
                              </DialogFooter>
                            </DialogContent>
                          </Dialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={Boolean(editingDocument)}
        onOpenChange={(open) => {
          if (!open) {
            setEditingDocument(null);
            setEditForm(EMPTY_DOCUMENT_FORM);
          }
        }}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit document metadata</DialogTitle>
            <DialogDescription>
              Update the title, category, description, and source URL without reprocessing the PDF chunks.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="edit-title">Title</Label>
              <Input
                id="edit-title"
                value={editForm.title}
                onChange={(e) => setEditForm((prev) => ({ ...prev, title: e.target.value }))}
                placeholder="Document title"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-category">Category</Label>
              <Select
                value={editForm.category}
                onValueChange={(value) =>
                  setEditForm((prev) => ({
                    ...prev,
                    category: value as KnowledgeDocumentCategory,
                  }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-source-url">Source URL</Label>
              <Input
                id="edit-source-url"
                value={editForm.sourceUrl}
                onChange={(e) => setEditForm((prev) => ({ ...prev, sourceUrl: e.target.value }))}
                placeholder="https://..."
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={editForm.description}
                onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                placeholder="Summarize why this document matters for Sentinel investigators."
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setEditingDocument(null);
                setEditForm(EMPTY_DOCUMENT_FORM);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleEditSave}
              disabled={!editingDocument || !editForm.title.trim() || updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save changes"
              )}
            </Button>
          </DialogFooter>
          {updateMutation.isError && (
            <p className="text-sm text-red-500">
              {(updateMutation.error as Error).message}
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function KnowledgeBasePage() {
  return (
    <AuthGuard>
      <KnowledgeBaseContent />
    </AuthGuard>
  );
}
