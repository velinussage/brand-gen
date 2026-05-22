// @brand-gen/core — shared data layer for brand-gen plugins

// MCP bridge
export { McpBridge, type McpToolDef } from "./mcp-bridge.js";
export { resolveMcpInvocation, type McpInvocation } from "./mcp-invocation.js";

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
} from "./types.js";
export {
  DEFAULT_HEARTBEAT_INTERVAL_MINUTES,
  DISCOVER_TIMEOUT_MS,
  GENERATE_TIMEOUT_MS,
  HEARTBEAT_CYCLE_TIMEOUT_MS,
  ORPHAN_MINUTES,
} from "./types.js";

// Goal catalog
export {
  GOAL_CATALOG,
  MATERIAL_TYPES,
  type MaterialType,
  getGoalById,
  getGoalsByAudience,
  getGoalsByStage,
} from "./goals.js";

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
} from "./memory.js";

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
} from "./workspace.js";

// Runtime status
export {
  buildRuntimeStatusMarker,
  readRuntimeStatusMarker,
  runtimeStatusDir,
  runtimeStatusPath,
  writeRuntimeStatusMarker,
} from "./runtime-status.js";

// Context building
export {
  buildBrandGenContext,
  callJsonTool,
  extractJsonFromMcpResult,
  isHeartbeatPrompt,
  summarizeContext,
  toToolResult,
} from "./context.js";

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
} from "./cycle.js";

// Canonical host-tool registry (Phase 3: replaces brand_search/brand_execute multiplexers)
export {
  CANONICAL_TOOLS,
  CANONICAL_TOOL_NAMES,
  canonicalToolDefinition,
  canonicalToolsByCategory,
  generateHostTools,
  type CanonicalTool,
  type HostToolDefinition,
  type ToolCategory,
} from "./tool-registry.js";
