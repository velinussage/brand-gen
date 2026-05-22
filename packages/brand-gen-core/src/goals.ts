import type { GoalEntry } from "./types.js";

/**
 * Material types supported by brand_pipeline.
 * Each maps to a visual format the pipeline can produce.
 */
export const MATERIAL_TYPES = [
  "social",
  "browser-illustration",
  "feature-illustration",
] as const;

export type MaterialType = (typeof MATERIAL_TYPES)[number];

/**
 * Expanded goal catalog with rich audience, funnel, and purpose tracking.
 *
 * Each goal provides a creative briefing that tells the generation pipeline
 * exactly WHO the material is for, WHAT it should accomplish, and HOW
 * to measure success. This solves the "aimless materials" problem.
 *
 * Goals are organized by funnel stage:
 *   awareness -> consideration -> conversion -> retention -> advocacy
 */
export const GOAL_CATALOG: readonly GoalEntry[] = [
  // -----------------------------------------------------------------------
  // AWARENESS — First exposure, brand recognition
  // -----------------------------------------------------------------------
  {
    id: "awareness-dev-explain",
    goal: "Explain what the product does in one visual for developers",
    purpose: "developer awareness",
    targetSurface: "X feed",
    preferredMaterial: "social",
    audience: "developers",
    funnelStage: "awareness",
    callToAction: "visit-site",
    emotion: "curiosity",
    briefing:
      "Create a clean, technical visual that explains the core value prop in terms a developer immediately understands. Lead with the problem, show the solution. Prioritize clarity over style. No marketing fluff.",
  },
  {
    id: "awareness-general-intro",
    goal: "Introduce the brand to someone who has never heard of it",
    purpose: "brand introduction",
    targetSurface: "X feed",
    preferredMaterial: "social",
    audience: "general",
    funnelStage: "awareness",
    callToAction: "learn-more",
    emotion: "clarity",
    briefing:
      "Design a visual that makes the brand instantly understandable to a stranger scrolling their feed. Lead with the problem it solves, not the solution. Zero jargon. The viewer should think 'oh, I get it' in under 3 seconds.",
  },
  {
    id: "awareness-hero",
    goal: "Create a hero visual that communicates credibility and vision",
    purpose: "website hero",
    targetSurface: "web hero",
    preferredMaterial: "browser-illustration",
    audience: "general",
    funnelStage: "awareness",
    callToAction: "learn-more",
    emotion: "trust",
    briefing:
      "A bold, premium hero image that makes the brand look established and trustworthy. Should work at 1200x630 for web and social share previews. This is the first thing a visitor sees — it must convey 'this is real, this is serious.'",
  },
  {
    id: "awareness-founder-pitch",
    goal: "Explain the market opportunity visually for founders and investors",
    purpose: "market positioning",
    targetSurface: "X feed",
    preferredMaterial: "social",
    audience: "founders",
    funnelStage: "awareness",
    callToAction: "learn-more",
    emotion: "excitement",
    briefing:
      "A visual that communicates the size of the opportunity and why now. Think market map, trend line, or gap visualization. Founders should see this and think 'I need to pay attention to this space.'",
  },

  // -----------------------------------------------------------------------
  // CONSIDERATION — Evaluating, comparing alternatives
  // -----------------------------------------------------------------------
  {
    id: "consideration-product-truth",
    goal: "Show the product in action with authentic UI or workflow",
    purpose: "product-led promotion",
    targetSurface: "product banner",
    preferredMaterial: "feature-illustration",
    audience: "developers",
    funnelStage: "consideration",
    callToAction: "try-product",
    emotion: "confidence",
    briefing:
      "Show real product interfaces or workflows — not a marketing render. This should feel authentic. Annotate key features subtly. The viewer should think 'I can see myself using this.'",
  },
  {
    id: "consideration-vs-status-quo",
    goal: "Visually contrast the old way vs the new way this product enables",
    purpose: "competitive positioning",
    targetSurface: "X feed",
    preferredMaterial: "social",
    audience: "founders",
    funnelStage: "consideration",
    callToAction: "learn-more",
    emotion: "confidence",
    briefing:
      "Create a before/after or old-way/new-way visual that positions the product as the obvious upgrade. Do not name competitors directly. Focus on the pain of the status quo vs the clarity of the new approach.",
  },
  {
    id: "consideration-social-proof",
    goal: "Showcase traction, usage stats, or community milestones visually",
    purpose: "social proof",
    targetSurface: "X feed",
    preferredMaterial: "social",
    audience: "founders",
    funnelStage: "consideration",
    callToAction: "sign-up",
    emotion: "trust",
    briefing:
      "Turn a real metric, community milestone, or user count into a shareable visual. Specificity beats vague claims — '2,847 active projects' is better than 'thousands of users'. Numbers should feel earned, not inflated.",
  },

  // -----------------------------------------------------------------------
  // CONVERSION — Ready to sign up / purchase
  // -----------------------------------------------------------------------
  {
    id: "conversion-cta-banner",
    goal: "Create a direct call-to-action banner that drives sign-ups",
    purpose: "conversion banner",
    targetSurface: "product banner",
    preferredMaterial: "feature-illustration",
    audience: "developers",
    funnelStage: "conversion",
    callToAction: "sign-up",
    emotion: "urgency",
    briefing:
      "A banner designed to convert. Clear CTA, minimal distraction, one strong value statement. Should work in both light and dark contexts. The viewer already knows what the product is — this pushes them to act.",
  },

  // -----------------------------------------------------------------------
  // RETENTION — Keep existing users engaged
  // -----------------------------------------------------------------------
  {
    id: "retention-feature-spotlight",
    goal: "Highlight a specific feature that existing users might not know about",
    purpose: "feature education",
    targetSurface: "X feed",
    preferredMaterial: "feature-illustration",
    audience: "community",
    funnelStage: "retention",
    callToAction: "try-product",
    emotion: "excitement",
    briefing:
      "Pick a specific underused feature and make it feel new and exciting. Show the feature in context of a real workflow — not an abstract diagram. The viewer should think 'wait, it can do that?'",
  },
  {
    id: "retention-release-visual",
    goal: "Create a visual changelog or release announcement",
    purpose: "release announcement",
    targetSurface: "X feed",
    preferredMaterial: "social",
    audience: "community",
    funnelStage: "retention",
    callToAction: "try-product",
    emotion: "excitement",
    briefing:
      "Turn a list of changes into a compelling visual. Lead with the most impactful change, not the longest list. Make it feel like progress — users should be excited to update.",
  },

  // -----------------------------------------------------------------------
  // ADVOCACY — Turn users into ambassadors
  // -----------------------------------------------------------------------
  {
    id: "advocacy-shareable",
    goal: "Create a shareable brand asset that users would proudly post",
    purpose: "community asset",
    targetSurface: "social promo",
    preferredMaterial: "social",
    audience: "community",
    funnelStage: "advocacy",
    callToAction: "share",
    emotion: "pride",
    briefing:
      "A visual so good that a user would willingly share it on their own feed. Think: 'I use this, and it makes me look smart/cool.' The brand should be present but not dominating — the user's identity comes first.",
  },
  {
    id: "advocacy-cultural",
    goal: "Create a culturally relevant reference that resonates with the target community",
    purpose: "cultural engagement",
    targetSurface: "X feed",
    preferredMaterial: "social",
    audience: "developers",
    funnelStage: "advocacy",
    callToAction: "share",
    emotion: "humor",
    briefing:
      "A brand-flavored meme or cultural reference that the target audience relates to. Must feel native to the community, not forced by marketing. If it feels like an ad, it failed.",
  },
] as const;

/**
 * Lookup a goal by its ID. Returns undefined if not found.
 */
export function getGoalById(id: string): GoalEntry | undefined {
  return GOAL_CATALOG.find((g) => g.id === id);
}

/**
 * Get goals filtered by funnel stage.
 */
export function getGoalsByStage(stage: GoalEntry["funnelStage"]): GoalEntry[] {
  return GOAL_CATALOG.filter((g) => g.funnelStage === stage);
}

/**
 * Get goals filtered by audience segment.
 */
export function getGoalsByAudience(audience: GoalEntry["audience"]): GoalEntry[] {
  return GOAL_CATALOG.filter((g) => g.audience === audience);
}
