import { getStatusSnapshot, type BridgeLike, type HeartbeatState, type PluginConfig } from '../core.ts';

export class BrandGenWidget {
  private visible = false;

  constructor(
    private readonly bridge: BridgeLike,
    private readonly config: PluginConfig,
    private readonly heartbeat: HeartbeatState,
  ) {}

  buildText(): string {
    const status = getStatusSnapshot(this.config, this.bridge as any, this.heartbeat);
    const lines = [
      `Brand: ${status.activeBrand ?? 'none'}`,
      `Session: ${status.activeSession ?? 'none'}`,
      `Health: ${status.healthStatus}`,
      `Pending reviews: ${status.pendingOutputReviews}`,
    ];
    if (status.journalStats) {
      lines.push(`Journal: ${status.journalStats.total} total / ${status.journalStats.failed} failed`);
    }
    return lines.join('\n');
  }

  async show(pi: any, sessionId?: string): Promise<void> {
    this.visible = true;
    const panel = {
      id: `brand-gen-widget${sessionId ? `-${sessionId}` : ''}`,
      title: 'Brand Gen',
      content: this.buildText(),
    };
    if (typeof pi?.registerWidget === 'function') {
      await pi.registerWidget(panel);
      return;
    }
    if (typeof pi?.addSidebarWidget === 'function') {
      await pi.addSidebarWidget(panel);
    }
  }

  async refresh(pi: any, sessionId?: string): Promise<void> {
    if (!this.visible) return;
    const payload = {
      id: `brand-gen-widget${sessionId ? `-${sessionId}` : ''}`,
      title: 'Brand Gen',
      content: this.buildText(),
    };
    if (typeof pi?.updateWidget === 'function') {
      await pi.updateWidget(payload.id, payload);
      return;
    }
    if (typeof pi?.refreshWidget === 'function') {
      await pi.refreshWidget(payload);
    }
  }

  async hide(pi: any, sessionId?: string): Promise<void> {
    this.visible = false;
    const id = `brand-gen-widget${sessionId ? `-${sessionId}` : ''}`;
    if (typeof pi?.removeWidget === 'function') {
      await pi.removeWidget(id);
      return;
    }
    if (typeof pi?.removeSidebarWidget === 'function') {
      await pi.removeSidebarWidget(id);
    }
  }
}
