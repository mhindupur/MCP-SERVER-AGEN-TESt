import type { Edge, Node } from "@xyflow/react";

import type { Topology } from "./topology";

export type LayoutSpacing = "compact" | "normal" | "wide";

const SPACING_SCALE: Record<LayoutSpacing, number> = {
  compact: 0.9,
  normal: 1,
  wide: 1.4
};

function scale(n: number, spacing: LayoutSpacing) {
  return Math.round(n * SPACING_SCALE[spacing]);
}

/**
 * Lay out VPC with subnets on the left and security groups in a dedicated right lane
 * so stencils do not overlap.
 */
export function topologyToFlow(
  topology: Topology,
  vpcFilter: string,
  spacing: LayoutSpacing = "normal"
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];

  const PAD = scale(20, spacing);
  const TITLE_H = scale(36, spacing);
  const SUBNET_W = scale(240, spacing);
  const SUBNET_COL_GAP = scale(20, spacing);
  const SUBNET_ROW_GAP = scale(16, spacing);
  const SUBNET_BASE_H = scale(96, spacing);
  const EC2_H = scale(56, spacing);
  const EC2_GAP = scale(8, spacing);
  const SG_W = scale(180, spacing);
  const SG_H = scale(52, spacing);
  const SG_GAP = scale(12, spacing);
  const SG_LANE_GAP = scale(24, spacing);
  const SUBNET_COLS = 2;
  const SUBNET_ZONE_W = PAD * 2 + SUBNET_COLS * SUBNET_W + (SUBNET_COLS - 1) * SUBNET_COL_GAP;
  const SG_LANE_W = SG_W + PAD;
  const VPC_W = SUBNET_ZONE_W + SG_LANE_GAP + SG_LANE_W;
  const VPC_GAP = scale(48, spacing);
  const REGION_PAD = scale(28, spacing);

  const vpcs = topology.vpcs.filter((v) => v.id && (!vpcFilter || v.id === vpcFilter));
  if (vpcs.length === 0) {
    return { nodes, edges };
  }

  const regionId = `region/${topology.region}`;
  const sgLaneX = SUBNET_ZONE_W + SG_LANE_GAP;

  const vpcBlocks: Array<{
    vpc: (typeof vpcs)[0];
    subnets: Topology["subnets"];
    instances: Topology["instances"];
    sgs: Topology["security_groups"];
    height: number;
  }> = [];

  for (const vpc of vpcs) {
    const subnets = topology.subnets.filter((s) => s.vpc_id === vpc.id);
    const instances = topology.instances.filter((i) => i.vpc_id === vpc.id);
    const sgs = topology.security_groups.filter((sg) => sg.vpc_id === vpc.id);

    const rowHeights: number[] = [];

    subnets.forEach((sn, idx) => {
      if (!sn.id) return;
      const row = Math.floor(idx / SUBNET_COLS);
      const snInstances = instances.filter((i) => i.subnet_id === sn.id);
      const snH = Math.max(SUBNET_BASE_H, TITLE_H + 8 + snInstances.length * (EC2_H + EC2_GAP));
      rowHeights[row] = Math.max(rowHeights[row] || 0, snH);
    });

    let subnetStackH = TITLE_H;
    if (rowHeights.length > 0) {
      subnetStackH += rowHeights.reduce((a, h) => a + h, 0) + (rowHeights.length - 1) * SUBNET_ROW_GAP;
    } else {
      subnetStackH += SUBNET_BASE_H;
    }

    const sgStackH =
      sgs.length > 0
        ? TITLE_H + sgs.length * SG_H + (sgs.length - 1) * SG_GAP
        : 0;

    const height = PAD * 2 + Math.max(subnetStackH, sgStackH, SUBNET_BASE_H + TITLE_H);
    vpcBlocks.push({ vpc, subnets, instances, sgs, height });
  }

  const maxVpcHeight = Math.max(...vpcBlocks.map((b) => b.height), scale(320, spacing));
  const regionW = vpcBlocks.length * (VPC_W + VPC_GAP) + REGION_PAD * 2;
  const regionH = maxVpcHeight + REGION_PAD * 2 + TITLE_H;

  nodes.push({
    id: regionId,
    type: "regionGroup",
    position: { x: 0, y: 0 },
    data: { label: `Region ${topology.region}` },
    style: { width: regionW, height: regionH },
    draggable: true,
    selectable: true,
    zIndex: 0
  });

  let vpcOffsetX = REGION_PAD;
  for (const block of vpcBlocks) {
    const vpcNodeId = `vpc/${block.vpc.id}`;
    nodes.push({
      id: vpcNodeId,
      type: "vpcGroup",
      parentId: regionId,
      position: { x: vpcOffsetX, y: REGION_PAD },
      data: {
        label: block.vpc.name || block.vpc.id,
        cidr: block.vpc.cidr,
        isDefault: block.vpc.is_default
      },
      style: { width: VPC_W, height: block.height },
      draggable: true,
      selectable: true,
      dragHandle: ".arch-drag-handle",
      zIndex: 1
    });

    const rowHeights: number[] = [];
    block.subnets.forEach((sn, idx) => {
      if (!sn.id) return;
      const row = Math.floor(idx / SUBNET_COLS);
      const snInstances = block.instances.filter((i) => i.subnet_id === sn.id);
      const snH = Math.max(
        SUBNET_BASE_H,
        TITLE_H + 8 + snInstances.length * (EC2_H + EC2_GAP)
      );
      rowHeights[row] = Math.max(rowHeights[row] || 0, snH);
    });

    block.subnets.forEach((sn, idx) => {
      if (!sn.id) return;
      const col = idx % SUBNET_COLS;
      const row = Math.floor(idx / SUBNET_COLS);
      const snInstances = block.instances.filter((i) => i.subnet_id === sn.id);
      const snH = Math.max(
        SUBNET_BASE_H,
        TITLE_H + 8 + snInstances.length * (EC2_H + EC2_GAP)
      );
      const snNodeId = `subnet/${sn.id}`;

      let y = PAD + TITLE_H;
      for (let r = 0; r < row; r++) y += (rowHeights[r] || SUBNET_BASE_H) + SUBNET_ROW_GAP;

      nodes.push({
        id: snNodeId,
        type: "subnetGroup",
        parentId: vpcNodeId,
        position: {
          x: PAD + col * (SUBNET_W + SUBNET_COL_GAP),
          y
        },
        data: {
          label: sn.name || sn.id,
          cidr: sn.cidr,
          az: sn.az,
          isPublic: sn.public
        },
        style: { width: SUBNET_W, height: snH },
        draggable: true,
        selectable: true,
        dragHandle: ".arch-drag-handle",
        zIndex: 2
      });

      snInstances.forEach((inst, iIdx) => {
        nodes.push({
          id: `instance/${inst.instance_id}`,
          type: "ec2Node",
          parentId: snNodeId,
          position: { x: scale(10, spacing), y: TITLE_H + scale(6, spacing) + iIdx * (EC2_H + EC2_GAP) },
          data: {
            label: inst.name || inst.instance_id,
            instanceType: inst.instance_type,
            state: inst.state,
            privateIp: inst.private_ip,
            instanceId: inst.instance_id
          },
          style: { width: SUBNET_W - scale(20, spacing) },
          draggable: true,
          selectable: true,
          zIndex: 3
        });
      });
    });

    block.sgs.forEach((sg, idx) => {
      if (!sg.id) return;
      nodes.push({
        id: `sg/${sg.id}`,
        type: "sgNode",
        parentId: vpcNodeId,
        position: {
          x: sgLaneX,
          y: PAD + TITLE_H + idx * (SG_H + SG_GAP)
        },
        data: {
          label: sg.name || sg.id,
          usedBy: sg.used_by_instances ?? 0,
          sgId: sg.id
        },
        style: { width: SG_W, height: SG_H },
        draggable: true,
        selectable: true,
        zIndex: 2
      });
    });

    vpcOffsetX += VPC_W + VPC_GAP;
  }

  for (const e of topology.edges) {
    const isSg = e.type === "uses_sg";
    const source = e.from;
    const target = e.to;
    if (!nodes.some((n) => n.id === source) || !nodes.some((n) => n.id === target)) continue;
    edges.push({
      id: `e-${source}-${target}`,
      source,
      target,
      type: "smoothstep",
      animated: false,
      style: {
        stroke: isSg ? "var(--arch-edge-sg)" : "var(--arch-edge)",
        strokeWidth: isSg ? 1.5 : 2,
        ...(isSg ? { strokeDasharray: "6 4" } : {})
      },
      zIndex: 0
    });
  }

  return { nodes, edges };
}
