import { describe, expect, it } from "vitest";

import {
  ancestorsOf,
  CHILDREN_BY_PARENT,
  LINKS,
  NODES,
  NODE_BY_ID,
  ROOT_ID,
  STAGES,
  TIERS,
  TIER_BY_ID,
  TOUR,
  TREE_LINKS,
} from "@/lib/architecture-data";
import { ICONS } from "@/lib/node-icons";

/**
 * The architecture graph is demo content, and demo content rots silently: a
 * renamed node id breaks a tour step, a missing rationale field renders an empty
 * panel, and neither shows up until someone is recording.
 *
 * These tests are the guard. They are cheap and they fail loudly.
 */

describe("architecture graph integrity", () => {
  it("has unique node ids", () => {
    const ids = NODES.map((n) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every link connects two real nodes", () => {
    for (const link of LINKS) {
      expect(NODE_BY_ID.has(link.source), `unknown source: ${link.source}`).toBe(true);
      expect(NODE_BY_ID.has(link.target), `unknown target: ${link.target}`).toBe(true);
    }
  });

  it("every node belongs to a declared tier", () => {
    for (const node of NODES) {
      expect(TIER_BY_ID.has(node.tier), `${node.id} has tier ${node.tier}`).toBe(true);
    }
  });

  it("every tier is populated", () => {
    // An empty tier renders as a labelled gap in the graph, which reads as a
    // missing piece of the architecture rather than as a deliberate absence.
    for (const tier of TIERS) {
      expect(
        NODES.some((n) => n.tier === tier.id),
        `tier "${tier.id}" has no nodes`,
      ).toBe(true);
    }
  });

  it("no node is orphaned", () => {
    // Containment counts as connection: group nodes have no request-path edges,
    // they hold children. A node in neither set would render floating alone.
    const connected = new Set(
      [...LINKS, ...TREE_LINKS].flatMap((l) => [l.source, l.target]),
    );
    for (const node of NODES) {
      if (node.id === ROOT_ID) continue;
      expect(connected.has(node.id), `${node.id} is not connected to anything`).toBe(true);
    }
  });
});

describe("hierarchy", () => {
  it("every node reaches the root", () => {
    // An unreachable node can never be revealed by expanding, so it would be
    // invisible however much the client clicks.
    for (const node of NODES) {
      if (node.id === ROOT_ID) continue;
      const chain = ancestorsOf(node.id);
      expect(chain.length, `${node.id} has no ancestors`).toBeGreaterThan(0);
      expect(chain[chain.length - 1], `${node.id} does not reach the root`).toBe(ROOT_ID);
    }
  });

  it("has no parent cycles", () => {
    for (const node of NODES) {
      const chain = ancestorsOf(node.id);
      expect(new Set(chain).size, `cycle above ${node.id}`).toBe(chain.length);
    }
  });

  it("the first view is small enough to take in", () => {
    // The whole point of collapsing is that a client meets a handful of boxes
    // rather than the full system at once.
    const topLevel = CHILDREN_BY_PARENT.get(ROOT_ID) ?? [];
    expect(topLevel.length).toBeGreaterThan(3);
    expect(topLevel.length).toBeLessThanOrEqual(9);
  });

  // ----------------------------------------------------------------------
  // PROJECT-SPECIFIC — replace the ids and patterns below with this system's.
  //
  // These look trivial and are worth writing anyway: a renamed id silently
  // breaks a tour stop, and nobody notices until someone is recording.
  // ----------------------------------------------------------------------

  it("the stage carrying the commercial argument expands into its parts", () => {
    // This is the click the demo is built around.
    const STAGE = "stage-engine";
    const REQUIRED_CHILDREN: string[] = [
      "bid-splitter", // one email -> N records
      "po-extractor",
      "bid-matcher", // PO -> existing bid
      "revision-classifier", // the duplicate-safety requirement
      "confidence-gate",
      "auto-cancel", // the deliberate limitation
    ];

    expect(NODE_BY_ID.get(STAGE)?.parent).toBe(ROOT_ID);

    const children = (CHILDREN_BY_PARENT.get(STAGE) ?? []).map((n) => n.id);
    for (const child of REQUIRED_CHILDREN) {
      expect(children, `${STAGE} does not expand into ${child}`).toContain(child);
    }
  });

  it("anything not actually enabled says so", () => {
    // At least one node should describe a capability that is built but
    // deliberately switched off, with the reason. A claim against interest is
    // what makes every other number on the page credible.
    const honest = NODES.some((n) =>
      /not enabled|opt-in|by default|deliberate/i.test(
        `${n.clientBenefit} ${n.userBenefit} ${n.metric?.value ?? ""}`,
      ),
    );
    expect(honest, "no node describes a deliberate limitation").toBe(true);
  });
});

describe("the pipeline", () => {
  it("runs in the order a request travels", () => {
    // By tier rather than by node id, so a rename does not break this and a
    // genuine reordering does.
    expect(STAGES.map((s) => s.tier)).toEqual([
      "client",
      "ui",
      "gateway",
      "context",
      "engine",
      "data",
      "ops",
      "platform",
    ]);
  });

  it("gives every stage a distinct position on the flow axis", () => {
    const orders = STAGES.map((s) => s.flowOrder);
    expect(new Set(orders).size).toBe(orders.length);
  });

  it("only stages are pinned to the flow axis", () => {
    // Pinning a child would drag it out of its parent's cluster and break the
    // expansion layout.
    for (const node of NODES) {
      if (node.flowOrder === undefined) continue;
      expect(node.parent, `${node.id} is pinned but is not top level`).toBe(ROOT_ID);
    }
  });

  it("connects each stage to the next", () => {
    // Rolled up to stage level the request path must actually be a path — a gap
    // renders as a disconnected card.
    const stageOf = (nodeId: string): string | undefined => {
      for (const id of [nodeId, ...ancestorsOf(nodeId)]) {
        if (STAGES.some((s) => s.id === id)) return id;
      }
      return undefined;
    };

    const edges = new Set(
      LINKS.map((l) => {
        const s = stageOf(l.source);
        const t = stageOf(l.target);
        return s && t && s !== t ? `${s}->${t}` : null;
      }).filter(Boolean) as string[],
    );

    // The pipeline a bid request actually travels. A gap here renders as a
    // disconnected card, which reads as a missing piece of the system.
    const REQUIRED_PATH: string[] = [
      "pm->app",
      "app->stage-gateway",
      "stage-gateway->stage-context",
      "stage-context->stage-engine",
      "stage-engine->stage-data",
      "stage-data->stage-ops",
      "stage-ops->stage-platform",
    ];
    for (const step of REQUIRED_PATH) {
      expect(edges, `pipeline is broken at ${step}`).toContain(step);
    }
  });

  it("every group summarises itself", () => {
    // Someone may click a group and never open it, so the group's own copy has
    // to stand alone rather than deferring to its children.
    for (const [parentId] of CHILDREN_BY_PARENT) {
      if (parentId === ROOT_ID) continue;
      const parent = NODE_BY_ID.get(parentId);
      expect(parent, `${parentId} has children but is not a node`).toBeDefined();
      expect(parent!.clientBenefit.length).toBeGreaterThan(20);
      expect(parent!.userBenefit.length).toBeGreaterThan(20);
    }
  });

  it("the root is logical only — it has no node of its own", () => {
    // A rendered root becomes a hub every stage hangs off, which is exactly the
    // shape the pipeline is meant to replace.
    expect(NODE_BY_ID.has(ROOT_ID)).toBe(false);
  });

  it("tree links match the parent fields exactly", () => {
    expect(TREE_LINKS.length).toBe(NODES.filter((n) => n.parent).length);
    for (const link of TREE_LINKS) {
      expect(NODE_BY_ID.get(link.target)?.parent).toBe(link.source);
    }
  });
});

describe("the mandated component chain is complete", () => {
  // Checked by concept with a regex rather than by id, so a rename cannot
  // silently drop a required component.
  //
  // Every capability the client's brief asks for by name, checked by concept
  // rather than by id so a rename cannot silently drop one.
  const REQUIRED: [string, RegExp][] = [
    ["webhook signing", /webhook|hmac|sign/i],
    ["idempotency", /idempoten/i],
    ["the extraction engine", /engine|extract/i],
    ["multi-lot splitting", /split/i],
    ["PO-to-bid matching", /match/i],
    ["revision handling", /revision/i],
    ["the confidence gate", /confidence/i],
    ["human review", /review/i],
    ["audit log", /audit|run.?log/i],
    ["cost telemetry", /cost/i],
    ["the Joist boundary", /joist/i],
    ["the QuickBooks seam", /quickbook/i],
  ];

  it.each(REQUIRED)("includes %s", (_concept, pattern) => {
    const found = NODES.some((n) => pattern.test(n.id) || pattern.test(n.label));
    expect(found).toBe(true);
  });
});

describe("guided tour", () => {
  it("every stop points at a real node", () => {
    for (const stop of TOUR) {
      expect(NODE_BY_ID.has(stop.nodeId), `tour stop → ${stop.nodeId}`).toBe(true);
    }
  });

  it("has narration on every stop", () => {
    for (const stop of TOUR) {
      expect(stop.chapter.length).toBeGreaterThan(3);
      expect(stop.say.length).toBeGreaterThan(30);
    }
  });

  it("covers the components that carry the cost argument", () => {
    // A tour that skips these is a tour that does not explain why the system
    // costs what it costs.
    //
    // A tour that skips these does not explain why the system costs what it
    // costs, or what it deliberately refuses to do.
    const REQUIRED: string[] = [
      "stage-engine", // the ~$0.04/email argument
      "bid-splitter", // the highest-value operation
      "bid-matcher", // why the LLM is the last tier, not the first
      "revision-classifier", // the brief's hardest requirement
      "auto-cancel", // the claim against interest
      "joist-bridge", // the honest "no"
      "quickbooks-readback", // and the way around it
      "run-log", // where the cost figures are checkable
    ];

    const ids = TOUR.map((s) => s.nodeId);
    for (const required of REQUIRED) {
      expect(ids, `tour omits ${required}`).toContain(required);
    }
  });

  it("starts at the client and ends in operations", () => {
    // Asserted by tier rather than by node id: the tour should open on the
    // customer's side of the system and close on how it is run, and that should
    // stay true through a restructure without needing the test rewritten.
    expect(NODE_BY_ID.get(TOUR[0]!.nodeId)?.tier).toBe("client");
    const lastTier = NODE_BY_ID.get(TOUR[TOUR.length - 1]!.nodeId)?.tier;
    expect(["ops", "platform"]).toContain(lastTier);
  });

  it("follows the pipeline in order", () => {
    // The tour is the narrative spine of the demo. If a stop appears before the
    // stage it belongs to, the story doubles back and stops making sense.
    const order = new Map(STAGES.map((s, i) => [s.id, i]));
    const stageOf = (nodeId: string): number | undefined => {
      for (const id of [nodeId, ...ancestorsOf(nodeId)]) {
        const position = order.get(id);
        if (position !== undefined) return position;
      }
      return undefined;
    };

    const positions = TOUR.map((stop) => stageOf(stop.nodeId)).filter(
      (p): p is number => p !== undefined,
    );
    for (let i = 1; i < positions.length; i++) {
      expect(
        positions[i]! >= positions[i - 1]!,
        `tour goes backwards at "${TOUR[i]!.chapter}"`,
      ).toBe(true);
    }
  });
});
