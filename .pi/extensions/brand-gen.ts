/**
 * Brand-Gen Extension
 *
 * Registers bgen commands as native Pi tools for brand material generation.
 * The primary entry point is the brand-orchestrator agent which coordinates
 * the full 6-phase pipeline. Individual tools (prepare, validate, evolve,
 * iterate, critique, feedback) support each phase.
 */

import type { ExtensionAPI, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// ── Configuration ─────────────────────────────────────────────

function parseEnvFile(filePath: string): Record<string, string> {
	const values: Record<string, string> = {};
	if (!filePath || !existsSync(filePath)) return values;
	for (const rawLine of readFileSync(filePath, "utf8").split(/\r?\n/)) {
		const line = rawLine.trim();
		if (!line || line.startsWith("#") || !line.includes("=")) continue;
		const idx = line.indexOf("=");
		const key = line.slice(0, idx).trim();
		const value = line.slice(idx + 1).trim().replace(/^(["'])(.*)\1$/, "$2");
		if (key) values[key] = value;
	}
	return values;
}

function loadRepoEnv(): Record<string, string> {
	const seedRoot = process.env.BRAND_GEN_DIR || process.env.BRAND_GEN_REPO_ROOT || process.cwd();
	const candidates = [
		process.env.BRAND_GEN_ENV_FILE,
		`${seedRoot}/.env`,
		`${process.cwd()}/.env`,
	].filter((value): value is string => Boolean(value));
	const merged: Record<string, string> = {};
	for (const candidate of candidates) Object.assign(merged, parseEnvFile(resolve(candidate)));
	return merged;
}

const LOCAL_ENV = loadRepoEnv();

function envValue(key: string): string {
	return process.env[key] || LOCAL_ENV[key] || "";
}

function getBrandDir(): string {
	return envValue("BRAND_GEN_DIR") || envValue("BRAND_GEN_REPO_ROOT") || process.cwd();
}
const BRAND_DIR = getBrandDir();
const ACTIVATE = `cd "${BRAND_DIR}" && set -a && [ -f .env ] && source .env && set +a && source .venv/bin/activate`;

// ── Stage Tracking ────────────────────────────────────────────

type PipelineStage =
	| "idle" | "route" | "plan_draft" | "plan" | "critique"
	| "scratchpad" | "generate" | "quality_gate" | "done";

const STAGE_LABELS: Record<PipelineStage, string> = {
	idle: "",
	route: "⓵ Route",
	plan_draft: "⓶ Plan Draft",
	plan: "⓷ Plan",
	critique: "⓸ Critique",
	scratchpad: "⓹ Scratchpad",
	generate: "⓺ Generate",
	quality_gate: "⓻ Quality Gate",
	done: "✓ Done",
};

const STAGE_ORDER: PipelineStage[] = [
	"route", "plan_draft", "plan", "critique", "scratchpad", "generate", "quality_gate",
];

const STAGE_MAP: Record<string, PipelineStage> = {
	route: "route",
	plan_draft: "plan_draft",
	plan: "plan",
	critique: "critique",
	scratchpad: "scratchpad",
	generate: "generate",
	quality_gate: "quality_gate",
};

export default function brandGenExtension(pi: ExtensionAPI): void {
	let currentStage: PipelineStage = "idle";
	let lastVersionId = "";

	// ── Helpers ────────────────────────────────────────────────

	async function bgen(args: string): Promise<{ stdout: string; stderr: string; code: number }> {
		return pi.exec("bash", ["-c", `${ACTIVATE} && bgen ${args}`]);
	}

	function updateStageWidget(ctx: ExtensionContext): void {
		if (currentStage === "idle") {
			ctx.ui.setStatus("brand-gen", undefined);
			ctx.ui.setWidget("brand-pipeline", undefined);
			return;
		}
		const line = STAGE_ORDER
			.map((s) => {
				if (s === currentStage) return ctx.ui.theme.fg("accent", STAGE_LABELS[s]);
				if (STAGE_ORDER.indexOf(s) < STAGE_ORDER.indexOf(currentStage)) return ctx.ui.theme.fg("success", "✓");
				return ctx.ui.theme.fg("muted", STAGE_LABELS[s]);
			})
			.join("  ");
		ctx.ui.setWidget("brand-pipeline", [line]);
		ctx.ui.setStatus("brand-gen", ctx.ui.theme.fg("accent", `🎨 ${STAGE_LABELS[currentStage]}`));
	}

	function parseJsonSafe(text: string): Record<string, unknown> | null {
		try {
			return JSON.parse(text);
		} catch {
			return null;
		}
	}

	/** Extract the last pipeline stage reached from the JSON result's stopped_at field. */
	function extractStage(jsonResult: Record<string, unknown> | null): PipelineStage | null {
		if (!jsonResult) return null;
		const stoppedAt = jsonResult.stopped_at as string | undefined;
		if (!stoppedAt) return null;
		return STAGE_MAP[stoppedAt] ?? null;
	}

	// ── Commands ───────────────────────────────────────────────

	pi.registerCommand("brand", {
		description: "Show brand-gen workspace status",
		handler: async (_args, ctx) => {
			const { stdout } = await bgen("context-snapshot --format json");
			const snap = parseJsonSafe(stdout);
			if (!snap) {
				ctx.ui.notify("Could not read brand workspace", "warning");
				return;
			}
			const ws = snap.workspace as Record<string, unknown> | undefined;
			ctx.ui.notify(
				`Brand: ${ws?.active_brand ?? "none"}\nSession: ${ws?.active_session ?? "saved brand"}\nStage: ${currentStage}`,
				"info",
			);
		},
	});

	pi.registerCommand("brand:show", {
		description: "Show latest generated versions",
		handler: async (args, ctx) => {
			const n = parseInt(args || "5", 10) || 5;
			const { stdout } = await bgen(`show --format json --latest ${n}`);
			ctx.ui.notify(stdout.slice(0, 2000), "info");
		},
	});

	// ── Core Tools ────────────────────────────────────────────

	pi.registerTool({
		name: "brand_context",
		label: "Brand Context",
		description: "Get the current brand-gen workspace state including active brand, files, and agent guidance.",
		parameters: Type.Object({}),
		async execute(_id, _params, _signal, _onUpdate, _ctx) {
			const { stdout, stderr, code } = await bgen("context-snapshot --format json");
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}` }], isError: true };
			return { content: [{ type: "text", text: stdout }], details: parseJsonSafe(stdout) ?? {} };
		},
	});

	pi.registerTool({
		name: "brand_share_card",
		label: "Sage Artifact Share Card",
		description:
			"Generate an HTML share card ONLY for sharing a real Sage prompt or skill. " +
			"Use sage CLI first to find the artifact (sage search, sage library skill list). " +
			"Do NOT use for general brand materials — use the brand-orchestrator agent instead.",
		parameters: Type.Object({
			source_url: Type.String({ description: "Sage artifact URL (e.g. https://sageprotocol.io/skills/sage-codebase)" }),
			entity_type: Type.String({ description: "prompt or skill" }),
			headline: Type.Optional(Type.String({ description: "Override headline" })),
			subhead: Type.Optional(Type.String({ description: "Override subhead" })),
		}),
		async execute(_id, params, _signal, onUpdate, _ctx) {
			const flags = [
				"--material-type announcement-card",
				"--render-backend html",
				`--source-url "${params.source_url}"`,
				`--entity-type ${params.entity_type}`,
				"--format json",
				"--open",
			];
			if (params.headline) flags.push(`--headline "${params.headline.replace(/"/g, '\\"')}"`);
			if (params.subhead) flags.push(`--subhead "${params.subhead.replace(/"/g, '\\"')}"`);
			onUpdate?.({ content: [{ type: "text", text: `Generating share card for ${params.entity_type}...` }] });
			const { stdout, stderr, code } = await bgen(`pipeline ${flags.join(" ")}`);
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}\n${stdout}` }], isError: true };
			const result = parseJsonSafe(stdout);
			if (result?.version_id) lastVersionId = result.version_id as string;
			return { content: [{ type: "text", text: stdout }], details: result ?? {} };
		},
	});

	pi.registerTool({
		name: "brand_critique",
		label: "Brand Critique Rubric",
		description: "Get the critique rubric for a generated version. Returns image path and scoring schema.",
		parameters: Type.Object({
			version: Type.String({ description: "Version ID (e.g. v012)" }),
		}),
		async execute(_id, params, _signal, _onUpdate, _ctx) {
			const { stdout, stderr, code } = await bgen(`critique-rubric ${params.version} --format json`);
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}` }], isError: true };
			return { content: [{ type: "text", text: stdout }], details: parseJsonSafe(stdout) ?? {} };
		},
	});

	pi.registerTool({
		name: "brand_submit_critique",
		label: "Brand Submit Critique",
		description: "Submit a critique for a generated version with scores and findings.",
		parameters: Type.Object({
			version: Type.String({ description: "Version ID" }),
			critique_path: Type.String({ description: "Path to critique JSON file" }),
		}),
		async execute(_id, params, _signal, _onUpdate, _ctx) {
			const { stdout, stderr, code } = await bgen(
				`submit-critique ${params.version} --critique-json ${params.critique_path} --format json`,
			);
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}` }], isError: true };
			return { content: [{ type: "text", text: stdout }], details: parseJsonSafe(stdout) ?? {} };
		},
	});

	pi.registerTool({
		name: "brand_show",
		label: "Brand Show Versions",
		description: "Show recent generated versions with metadata, scores, and image paths.",
		parameters: Type.Object({
			latest: Type.Optional(Type.Number({ description: "Number of recent versions to show (default 5)" })),
			version: Type.Optional(Type.String({ description: "Specific version ID to show" })),
		}),
		async execute(_id, params, _signal, _onUpdate, _ctx) {
			const arg = params.version ? params.version : `--latest ${params.latest ?? 5}`;
			const { stdout, stderr, code } = await bgen(`show ${arg} --format json`);
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}` }], isError: true };
			return { content: [{ type: "text", text: stdout }], details: parseJsonSafe(stdout) ?? {} };
		},
	});

	pi.registerTool({
		name: "brand_feedback",
		label: "Brand Feedback",
		description: "Score and annotate a generated version for the learning loop.",
		parameters: Type.Object({
			version: Type.String({ description: "Version ID (e.g. v012)" }),
			score: Type.Number({ description: "Score 1-5 (5=near-ship, 1=reject)" }),
			notes: Type.Optional(Type.String({ description: "Feedback notes" })),
			status: Type.Optional(Type.String({ description: "favorite or rejected" })),
		}),
		async execute(_id, params, _signal, _onUpdate, _ctx) {
			const flags = [`${params.version}`, `--score ${params.score}`];
			if (params.notes) flags.push(`--notes "${params.notes.replace(/"/g, '\\"')}"`);
			if (params.status) flags.push(`--status ${params.status}`);
			const { stdout, stderr, code } = await bgen(`feedback ${flags.join(" ")}`);
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}` }], isError: true };
			return { content: [{ type: "text", text: stdout }] };
		},
	});

	// ── Refinement Tools ──────────────────────────────────────

	pi.registerTool({
		name: "brand_prepare",
		label: "Brand Prepare",
		description:
			"Run pre-generation preparation: extract inspiration, suggest role packs, suggest layouts, " +
			"and check learnings. Returns preparation context for better generation.",
		parameters: Type.Object({
			material_type: Type.String({ description: "Material type to prepare for" }),
			mode: Type.Optional(Type.String({ description: "Workflow mode: reference, inspiration, hybrid" })),
		}),
		async execute(_id, params, _signal, onUpdate, _ctx) {
			const results: Record<string, unknown> = {};

			// Step 1: Check learnings
			onUpdate?.({ content: [{ type: "text", text: "Checking learnings..." }] });
			const learnings = await bgen("show-iteration-memory --format json");
			if (learnings.code === 0) results.learnings = parseJsonSafe(learnings.stdout);

			// Step 2: Suggest role pack
			onUpdate?.({ content: [{ type: "text", text: "Suggesting role pack..." }] });
			const rolePack = await bgen(`suggest-role-pack --material-type ${params.material_type} --format json`);
			if (rolePack.code === 0) results.role_pack = parseJsonSafe(rolePack.stdout);

			// Step 3: Suggest layout
			onUpdate?.({ content: [{ type: "text", text: "Suggesting layout..." }] });
			const layout = await bgen(`suggest-layout --material-type ${params.material_type} --format json`);
			if (layout.code === 0) results.layout = parseJsonSafe(layout.stdout);

			// Step 4: Improvement questions
			onUpdate?.({ content: [{ type: "text", text: "Getting improvement questions..." }] });
			const questions = await bgen("improvement-questions --format json");
			if (questions.code === 0) results.questions = parseJsonSafe(questions.stdout);

			return { content: [{ type: "text", text: JSON.stringify(results, null, 2) }], details: results };
		},
	});

	pi.registerTool({
		name: "brand_validate",
		label: "Brand Validate",
		description: "Validate a plan or material against brand identity. Checks brand fit before generation.",
		parameters: Type.Object({
			plan_path: Type.Optional(Type.String({ description: "Path to plan JSON to validate" })),
			version: Type.Optional(Type.String({ description: "Version ID to validate post-generation" })),
		}),
		async execute(_id, params, _signal, _onUpdate, _ctx) {
			let cmd: string;
			if (params.plan_path) {
				cmd = `validate-brand-fit --plan "${params.plan_path}" --format json`;
			} else if (params.version) {
				cmd = `review-brand ${params.version} --format json`;
			} else {
				return { content: [{ type: "text", text: "Provide plan_path or version" }], isError: true };
			}
			const { stdout, stderr, code } = await bgen(cmd);
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}` }], isError: true };
			return { content: [{ type: "text", text: stdout }], details: parseJsonSafe(stdout) ?? {} };
		},
	});

	pi.registerTool({
		name: "brand_evolve",
		label: "Brand Evolve",
		description: "Analyze generation patterns and extract learnings for future improvement.",
		parameters: Type.Object({
			format: Type.Optional(Type.String({ description: "Output format: json or text" })),
		}),
		async execute(_id, params, _signal, _onUpdate, _ctx) {
			const fmt = params.format ?? "json";
			const { stdout, stderr, code } = await bgen(`evolve --format ${fmt}`);
			if (code !== 0) return { content: [{ type: "text", text: `Error: ${stderr}` }], isError: true };
			return { content: [{ type: "text", text: stdout }], details: parseJsonSafe(stdout) ?? {} };
		},
	});

	pi.registerTool({
		name: "brand_iterate",
		label: "Brand Iterate",
		description:
			"Iterate on a previous version using feedback and learnings. Regenerates with refined prompt.",
		parameters: Type.Object({
			version: Type.String({ description: "Version ID to iterate from (e.g. v043)" }),
			feedback: Type.Optional(Type.String({ description: "What to improve in this iteration" })),
			ban: Type.Optional(Type.Array(Type.String(), { description: "Things to ban in the iteration" })),
			max_iterations: Type.Optional(Type.Number({ description: "Max VLM critique loops (1-3)" })),
		}),
		async execute(_id, params, _signal, onUpdate, ctx) {
			// Step 1: Get version metadata to determine material_type
			const showResult = await bgen(`show ${params.version} --format json`);
			const versionData = parseJsonSafe(showResult.stdout);
			const materialType = (versionData as Record<string, unknown> | null)?.material_type as string | undefined;

			// Step 2: Build pipeline flags with source_version
			const flags: string[] = [
				`--material-type ${materialType ?? "social"}`,
				`--source-version ${params.version}`,
				`--max-iterations ${params.max_iterations ?? 2}`,
				"--format json",
				"--open",
			];
			if (params.feedback) flags.push(`--prompt-seed "${params.feedback.replace(/"/g, '\\"')}"`);
			if (params.ban) params.ban.forEach((b: string) => flags.push(`--ban "${b.replace(/"/g, '\\"')}"`));

			currentStage = "route";
			updateStageWidget(ctx as unknown as ExtensionContext);
			onUpdate?.({ content: [{ type: "text", text: `Iterating on ${params.version}...` }] });

			const { stdout, stderr, code } = await bgen(`pipeline ${flags.join(" ")}`);

			currentStage = "done";
			updateStageWidget(ctx as unknown as ExtensionContext);

			if (code !== 0) {
				currentStage = "idle";
				updateStageWidget(ctx as unknown as ExtensionContext);
				return { content: [{ type: "text", text: `Iteration failed:\n${stderr}\n${stdout}` }], isError: true };
			}

			const result = parseJsonSafe(stdout);
			if (result?.version_id) lastVersionId = result.version_id as string;

			setTimeout(() => {
				currentStage = "idle";
				updateStageWidget(ctx as unknown as ExtensionContext);
			}, 5000);

			return { content: [{ type: "text", text: stdout }], details: result ?? {} };
		},
	});

	// ── Lifecycle hooks ───────────────────────────────────────

	pi.on("session_start", async (_event, ctx) => {
		currentStage = "idle";
		updateStageWidget(ctx);
	});
}
