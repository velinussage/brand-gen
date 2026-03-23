import type { McpBridge } from "./mcp-bridge.ts";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export type PluginConfig = {
  brandGenDir: string;
  brandIterateMcpPath: string;
  logoIterateMcpPath: string;
  approvalMode: "all" | "output_only" | "none";
  logLevel: "debug" | "info" | "warn" | "error";
  heartbeatIntervalMinutes: number;
  autoHeartbeat: boolean;
};

export type WorkspaceKind = "session" | "saved_brand" | "unresolved";

export type BrandGenConfig = {
  active?: string | null;
  activeSession?: string | null;
  version?: number;
  inspirationMode?: boolean;
};

// ---------------------------------------------------------------------------
// Workspace
// ---------------------------------------------------------------------------

export type ActiveWorkspace = {
  brandGenDir: string;
  workspaceKind: WorkspaceKind;
  activeBrand: string | null;
  activeSession: string | null;
  workspaceDir: string | null;
  savedBrandDir: string | null;
  savedIdentityPath: string | null;
  workspaceIdentityPath: string | null;
};

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

export type BrandContext = {
  brandGenDir: string;
  workspaceKind: WorkspaceKind;
  activeBrand: string | null;
  activeSession: string | null;
  workspaceDir: string | null;
  workspaceIdentityPath: string | null;
  identity: Record<string, unknown> | null;
  blackboard: Record<string, unknown> | null;
  iterationMemory: Record<string, unknown> | null;
  learnings: BrandLearnings | null;
  recentJournal: JournalEntry[];
  availableTools: string[];
  contextSnapshot?: Record<string, unknown> | null;
  workspaceStatus?: Record<string, unknown> | null;
  capabilities?: Record<string, unknown> | null;
};

// ---------------------------------------------------------------------------
// Journal
// ---------------------------------------------------------------------------

export type JournalStatus = "in_progress" | "complete" | "failed";

export type JournalEntry = {
  id: string;
  brand: string;
  materialType?: string;
  goal?: string;
  goalId?: string;
  purpose?: string;
  targetSurface?: string;
  audience?: string;
  funnelStage?: string;
  callToAction?: string;
  briefing?: string;
  workflowRoute?: string;
  model?: string;
  prompt?: string;
  inspirationSources?: string[];
  referenceRoles?: Record<string, unknown>;
  outputPath?: string;
  versionId?: string;
  agentReviewPath?: string;
  visualReviewStatus?: string;
  status: JournalStatus;
  stoppedAt?: string;
  rating?: number | null;
  feedback?: string;
  critique?: Record<string, unknown> | null;
  createdAt?: string;
};

export type BrandLearnings = {
  brand: string;
  modelPreferences: string[];
  colorInsights: string[];
  compositionPatterns: string[];
  failurePatterns: string[];
  messagingInsights?: string[];
  audienceInsights?: string[];
  lastUpdated?: string;
};

export type PipelineResultLike = {
  workflow_id?: string;
  stopped_at?: string;
  stop_reason?: string;
  route?: { route_key?: string } | null;
  result?: {
    version_id?: string;
    image_paths?: string[];
    vlm_critique?: Record<string, unknown> | null;
    agent_review_path?: string;
    visual_review_status?: string;
  } | null;
  critique?: Record<string, unknown> | null;
};

export type RuntimeStatusMarker = {
  pluginName: string;
  brandGenDir: string;
  activeBrand: string | null;
  activeSession: string | null;
  workspaceKind: WorkspaceKind;
  workspaceDir: string | null;
  workspaceIdentityPath: string | null;
  journalPath: string | null;
  learningsPath: string | null;
  journalBackend: "workspace-jsonl" | "legacy-sqlite-bridge" | "unresolved";
  brandRootMode: "saved_brand" | "session" | "unresolved";
  timestamp: string;
  updatedAt: string;
  extra?: Record<string, unknown>;
};

// ---------------------------------------------------------------------------
// Heartbeat
// ---------------------------------------------------------------------------

export type HeartbeatState = {
  timer: NodeJS.Timeout | null;
  runPromise: Promise<Record<string, unknown>> | null;
  healthStatus: "ok" | "degraded";
  failures: number;
  lastResult: Record<string, unknown> | null;
};

// ---------------------------------------------------------------------------
// Bridge abstraction
// ---------------------------------------------------------------------------

export type BridgeLike = Pick<McpBridge, "isReady" | "callTool" | "listTools">;

export type LoggerLike = {
  info?: (msg: string) => void;
  warn?: (msg: string) => void;
  error?: (msg: string) => void;
  debug?: (msg: string) => void;
};

// ---------------------------------------------------------------------------
// Goal catalog types
// ---------------------------------------------------------------------------

export type AudienceSegment =
  | "developers"
  | "founders"
  | "investors"
  | "end-users"
  | "community"
  | "press"
  | "general";

export type FunnelStage =
  | "awareness"
  | "consideration"
  | "conversion"
  | "retention"
  | "advocacy";

export type CallToAction =
  | "visit-site"
  | "sign-up"
  | "follow"
  | "share"
  | "try-product"
  | "learn-more"
  | "join-community"
  | "none";

export type GoalEntry = {
  id: string;
  goal: string;
  purpose: string;
  targetSurface: string;
  preferredMaterial: string;
  audience: AudienceSegment;
  funnelStage: FunnelStage;
  callToAction: CallToAction;
  emotion: string;
  briefing: string;
};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const HEARTBEAT_CYCLE_TIMEOUT_MS = 15 * 60_000;
export const DISCOVER_TIMEOUT_MS = 5 * 60_000;
export const GENERATE_TIMEOUT_MS = 10 * 60_000;
export const ORPHAN_MINUTES = 10;
export const DEFAULT_HEARTBEAT_INTERVAL_MINUTES = 60;
