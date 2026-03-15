"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAgentSettings,
  getLLMModelCatalog,
  updateAgentSettings,
  testLLMConnection,
} from "@/lib/api";
import type { AgentSettingsUpdate, LLMProviderCatalog } from "@/lib/types";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Bot,
  Key,
  Thermometer,
  Globe,
  Cpu,
} from "lucide-react";

function AgentSettingsContent() {
  const queryClient = useQueryClient();
  const { isAdmin } = useAuth();

  const [formData, setFormData] = useState<AgentSettingsUpdate>({});
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["agent-settings"],
    queryFn: getAgentSettings,
    enabled: isAdmin,
  });

  const { data: catalog, isLoading: isCatalogLoading } = useQuery({
    queryKey: ["llm-model-catalog"],
    queryFn: getLLMModelCatalog,
    enabled: isAdmin,
  });

  const updateMutation = useMutation({
    mutationFn: updateAgentSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-settings"] });
      setFormData({});
      setTestResult(null);
    },
  });

  const testMutation = useMutation({
    mutationFn: testLLMConnection,
    onSuccess: (result) => {
      setTestResult({
        success: result.success,
        message: result.success
          ? `Connected to ${result.provider}/${result.model}: "${result.response}"`
          : `Failed: ${result.error}`,
      });
    },
    onError: (error) => {
      setTestResult({
        success: false,
        message: `Error: ${(error as Error).message}`,
      });
    },
  });

  const getDefaultModelForProvider = (provider: LLMProviderCatalog | undefined) => {
    if (!provider) {
      return undefined;
    }

    return (
      provider.models.find((model) => model.recommended)?.value ?? provider.models[0]?.value
    );
  };

  const providers = catalog?.providers ?? [];
  const currentProvider =
    formData.llm_provider ?? settings?.llm_provider ?? providers[0]?.value ?? "openai";
  const selectedProvider = providers.find(
    (provider) => provider.value === currentProvider,
  );
  const currentModel =
    formData.llm_model ??
    settings?.llm_model ??
    getDefaultModelForProvider(selectedProvider) ??
    "";
  const currentTemp = formData.llm_temperature ?? settings?.llm_temperature ?? 0.7;
  const currentBaseUrl = formData.llm_base_url ?? settings?.llm_base_url ?? "";
  const providerModels = selectedProvider?.models ?? [];
  const selectedModel = providerModels.find((model) => model.value === currentModel);
  const supportsCustomModel = selectedProvider?.supports_custom_model ?? true;
  const hasPresetModel = providerModels.some((model) => model.value === currentModel);
  const showCustomModelInput = supportsCustomModel && (!currentModel || !hasPresetModel);
  const modelSelectValue = hasPresetModel
    ? currentModel
    : showCustomModelInput
      ? "__custom__"
      : undefined;

  const handleSave = () => {
    if (Object.keys(formData).length > 0) {
      updateMutation.mutate(formData);
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
              Only administrators can configure agent settings.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isCatalogLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6 space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Agent Settings</h1>
        <p className="text-muted-foreground">
          Configure the AI assistant for case analysis
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            LLM Configuration
          </CardTitle>
          <CardDescription>
            Configure the language model used for case analysis and chat
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Provider */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              Provider
            </Label>
            <Select
              value={currentProvider}
              onValueChange={(value) => {
                const nextProvider = providers.find(
                  (provider) => provider.value === value,
                );
                setFormData((prev) => ({
                  ...prev,
                  llm_provider: value,
                  llm_model: getDefaultModelForProvider(nextProvider) ?? "",
                }));
                setTestResult(null);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.value} value={provider.value}>
                    {provider.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {selectedProvider?.description ?? "Select which provider powers the agent runtime."}
            </p>
          </div>

          {/* Model */}
          <div className="space-y-2">
            <Label>Model</Label>
            {providerModels.length > 0 ? (
              <Select
                value={modelSelectValue}
                onValueChange={(value) => {
                  setFormData((prev) => ({
                    ...prev,
                    llm_model: value === "__custom__" ? "" : value,
                  }));
                  setTestResult(null);
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a model" />
                </SelectTrigger>
                <SelectContent>
                  {providerModels.map((model) => (
                    <SelectItem key={model.value} value={model.value}>
                      {model.label}
                    </SelectItem>
                  ))}
                  {supportsCustomModel && (
                    <SelectItem value="__custom__">Custom model</SelectItem>
                  )}
                </SelectContent>
              </Select>
            ) : (
              <Input
                value={currentModel}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, llm_model: e.target.value }));
                  setTestResult(null);
                }}
                placeholder="Enter model name"
              />
            )}
            {showCustomModelInput && providerModels.length > 0 && (
              <Input
                value={currentModel}
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, llm_model: e.target.value }));
                  setTestResult(null);
                }}
                placeholder="Enter custom model name"
              />
            )}
            <p className="text-xs text-muted-foreground">
              {selectedModel?.description ??
                (supportsCustomModel
                  ? "Choose a catalog model or enter any provider-supported model name."
                  : "Choose a supported model for this provider.")}
            </p>
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Key className="h-4 w-4" />
              API Key
            </Label>
            <div className="flex items-center gap-2">
              <Input
                type="password"
                placeholder={
                  settings?.llm_api_key_set
                    ? "••••••••••••••••"
                    : "Enter API key"
                }
                onChange={(e) => {
                  setFormData((prev) => ({ ...prev, llm_api_key: e.target.value }));
                  setTestResult(null);
                }}
              />
              {settings?.llm_api_key_set && (
                <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {selectedProvider?.requires_api_key === false
                ? "This provider does not require an API key for the default setup."
                : settings?.llm_api_key_set
                  ? "API key is configured. Enter a new value to update."
                  : "No API key configured."}
            </p>
          </div>

          {/* Base URL (for Ollama or custom endpoints) */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Globe className="h-4 w-4" />
              Base URL (optional)
            </Label>
            <Input
              value={currentBaseUrl}
              onChange={(e) => {
                setFormData((prev) => ({ ...prev, llm_base_url: e.target.value }));
                setTestResult(null);
              }}
              placeholder="https://api.example.com or http://localhost:11434"
            />
            <p className="text-xs text-muted-foreground">
              {selectedProvider?.supports_base_url
                ? "Use this for Ollama, proxies, or custom-compatible endpoints. Leave empty for the provider default."
                : "Leave empty to use the provider's default hosted endpoint."}
            </p>
          </div>

          {/* Temperature */}
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Thermometer className="h-4 w-4" />
              Temperature: {currentTemp}
            </Label>
            <Slider
              value={[currentTemp]}
              onValueChange={([v]) => {
                setFormData((prev) => ({ ...prev, llm_temperature: v }));
                setTestResult(null);
              }}
              min={0}
              max={1}
              step={0.1}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              Lower = more focused, higher = more creative
            </p>
          </div>

          {/* Test Result */}
          {testResult && (
            <div
              className={`p-3 rounded-md text-sm ${
                testResult.success
                  ? "bg-green-500/10 text-green-700 border border-green-500/30"
                  : "bg-red-500/10 text-red-700 border border-red-500/30"
              }`}
            >
              {testResult.message}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-4">
            <Button
              variant="outline"
              onClick={() => testMutation.mutate(formData)}
              disabled={testMutation.isPending || !currentModel.trim()}
            >
              {testMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Testing...
                </>
              ) : (
                "Test Connection"
              )}
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                Object.keys(formData).length === 0 || updateMutation.isPending
              }
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </div>

          {updateMutation.isError && (
            <p className="text-sm text-red-500">
              {(updateMutation.error as Error).message}
            </p>
          )}
          {updateMutation.isSuccess && (
            <p className="text-sm text-green-500">Settings saved successfully!</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AgentSettingsPage() {
  return (
    <AuthGuard>
      <AgentSettingsContent />
    </AuthGuard>
  );
}
