// @brand-gen/core — shared data layer for brand-gen plugins

// MCP bridge
export { McpBridge, type McpToolDef } from "./mcp-bridge.ts";

// Types & constants
export type {
  ActiveWorkspace,
  AudienceSegment,
  BrandContext,
  BrandGenConfig,
  BrandLearnings,
  BridgeLike,
  CallToAction,
  FunnelStage,
  GoalEntry,
  HeartbeatState,
  JournalEntry,
  JournalStatus,
  LoggerLike,
  PipelineResultLike,
  PluginConfig,
  RuntimeStatusMarker,
  WorkspaceKind,
} from "./types.ts";
export {
  DEFAULT_HEARTBEAT_INTERVAL_MINUTES,
  DISCOVER_TIMEOUT_MS,
  GENERATE_TIMEOUT_MS,
  HEARTBEAT_CYCLE_TIMEOUT_MS,
  ORPHAN_MINUTES,
} from "./types.ts";

// Goal catalog
export {
  GOAL_CATALOG,
  MATERIAL_TYPES,
  type MaterialType,
  getGoalById,
  getGoalsByAudience,
  getGoalsByStage,
} from "./goals.ts";

// Memory (SQLite journal + learnings JSON)
export {
  appendJournal,
  completeJournal,
  defaultLearnings,
  failJournal,
  getInProgressEntries,
  getJournalStats,
  getOrphanedEntries,
  getRecentEntries,
  initMemory,
  journalPathForWorkspace,
  loadLearnings,
  learningsPathForWorkspace,
  patchLearnings,
  patchJournalEntry,
  rateJournalEntry,
  saveLearnings,
} from "./memory.ts";

// Workspace resolution
export {
  deriveBrandFromWorkspace,
  expandHome,
  loadBrandGenConfig,
  loadBrandIdentitySummary,
  normalizeWorkspaceRoot,
  parsePluginConfig,
  readJsonFile,
  resolveActiveWorkspace,
} from "./workspace.ts";

// Runtime status
export {
  buildRuntimeStatusMarker,
  readRuntimeStatusMarker,
  runtimeStatusDir,
  runtimeStatusPath,
  writeRuntimeStatusMarker,
} from "./runtime-status.ts";

// Context building
export {
  buildBrandGenContext,
  callJsonTool,
  extractJsonFromMcpResult,
  isHeartbeatPrompt,
  summarizeContext,
  toToolResult,
} from "./context.ts";

// Cycle & heartbeat
export {
  createHeartbeatState,
  deriveGenerationPolicy,
  executeAction,
  getPendingOutputReviews,
  getStatusSnapshot,
  isReviewableOutputEntry,
  mapGenerateParams,
  runDiscoverStep,
  runGenerateAction,
  runGenerateStep,
  runHeartbeatCycle,
  scheduleHeartbeat,
  stopHeartbeat,
  triggerHeartbeat,
  withTimeout,
} from "./cycle.ts";
