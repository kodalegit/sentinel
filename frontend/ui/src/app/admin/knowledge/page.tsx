"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getKnowledgeDocuments,
  uploadKnowledgeDocument,
  deleteKnowledgeDocument,
  getKnowledgeStats,
} from "@/lib/api";
import type { KnowledgeDocument, KnowledgeDocumentCategory } from "@/lib/types";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  Upload,
  Trash2,
  BookOpen,
  Scale,
  FileCheck,
  AlertCircle,
  Loader2,
} from "lucide-react";

const CATEGORY_LABELS: Record<KnowledgeDocumentCategory, string> = {
  LAW: "Law",
  CASE_LAW: "Case Law",
  REGULATION: "Regulation",
  GUIDELINE: "Guideline",
};

const CATEGORY_ICONS: Record<KnowledgeDocumentCategory, React.ReactNode> = {
  LAW: <Scale className="h-4 w-4" />,
  CASE_LAW: <BookOpen className="h-4 w-4" />,
  REGULATION: <FileCheck className="h-4 w-4" />,
  GUIDELINE: <FileText className="h-4 w-4" />,
};

function KnowledgeBaseContent() {
  const queryClient = useQueryClient();
  const { isAdmin } = useAuth();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [uploadForm, setUploadForm] = useState({
    file: null as File | null,
    title: "",
    category: "LAW" as KnowledgeDocumentCategory,
    description: "",
    sourceUrl: "",
  });

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
        uploadForm.title,
        uploadForm.category,
        uploadForm.description || undefined,
        uploadForm.sourceUrl || undefined
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-documents"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-stats"] });
      setUploadOpen(false);
      setUploadForm({
        file: null,
        title: "",
        category: "LAW",
        description: "",
        sourceUrl: "",
      });
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
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Knowledge Base</h1>
          <p className="text-muted-foreground">
            Manage Kenyan legal documents for AI-powered analysis
          </p>
        </div>
        <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
          <DialogTrigger asChild>
            <Button>
              <Upload className="h-4 w-4 mr-2" />
              Upload Document
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Upload Legal Document</DialogTitle>
              <DialogDescription>
                Upload a PDF document to add to the knowledge base. The document
                will be chunked and embedded for RAG retrieval.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="file">PDF File</Label>
                <Input
                  id="file"
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={uploadForm.title}
                  onChange={(e) =>
                    setUploadForm((prev) => ({ ...prev, title: e.target.value }))
                  }
                  placeholder="e.g., Public Procurement and Asset Disposal Act 2015"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="category">Category</Label>
                <Select
                  value={uploadForm.category}
                  onValueChange={(v) =>
                    setUploadForm((prev) => ({
                      ...prev,
                      category: v as KnowledgeDocumentCategory,
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="LAW">Law (Acts of Parliament)</SelectItem>
                    <SelectItem value="CASE_LAW">Case Law (Court Decisions)</SelectItem>
                    <SelectItem value="REGULATION">Regulation (PPADR, Circulars)</SelectItem>
                    <SelectItem value="GUIDELINE">Guideline (PPRA/EACC)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Input
                  id="description"
                  value={uploadForm.description}
                  onChange={(e) =>
                    setUploadForm((prev) => ({
                      ...prev,
                      description: e.target.value,
                    }))
                  }
                  placeholder="Brief description of the document"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sourceUrl">Source URL (optional)</Label>
                <Input
                  id="sourceUrl"
                  value={uploadForm.sourceUrl}
                  onChange={(e) =>
                    setUploadForm((prev) => ({
                      ...prev,
                      sourceUrl: e.target.value,
                    }))
                  }
                  placeholder="https://..."
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
                disabled={!uploadForm.file || !uploadForm.title || uploadMutation.isPending}
              >
                {uploadMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  "Upload"
                )}
              </Button>
            </DialogFooter>
            {uploadMutation.isError && (
              <p className="text-sm text-red-500 mt-2">
                {(uploadMutation.error as Error).message}
              </p>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Documents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats?.total_documents ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Chunks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats?.total_chunks ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Laws
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats?.by_category?.LAW ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Regulations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {stats?.by_category?.REGULATION ?? 0}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Documents Table */}
      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
          <CardDescription>
            All legal documents in the knowledge base
          </CardDescription>
        </CardHeader>
        <CardContent>
          {docsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : documents?.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No documents uploaded yet.</p>
              <p className="text-sm">Upload your first document to get started.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Chunks</TableHead>
                  <TableHead>Uploaded By</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents?.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {CATEGORY_ICONS[doc.category]}
                        <div>
                          <p className="font-medium">{doc.title}</p>
                          {doc.description && (
                            <p className="text-sm text-muted-foreground truncate max-w-md">
                              {doc.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">
                        {CATEGORY_LABELS[doc.category]}
                      </Badge>
                    </TableCell>
                    <TableCell>{doc.chunk_count}</TableCell>
                    <TableCell>{doc.uploaded_by ?? "Unknown"}</TableCell>
                    <TableCell>
                      {new Date(doc.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Dialog
                        open={deleteId === doc.id}
                        onOpenChange={(open) => !open && setDeleteId(null)}
                      >
                        <DialogTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteId(doc.id)}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Delete Document</DialogTitle>
                            <DialogDescription>
                              Are you sure you want to delete &quot;{doc.title}&quot;?
                              This will also delete all {doc.chunk_count} chunks.
                              This action cannot be undone.
                            </DialogDescription>
                          </DialogHeader>
                          <DialogFooter>
                            <Button
                              variant="outline"
                              onClick={() => setDeleteId(null)}
                            >
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
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
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
