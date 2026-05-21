"use client";

import { Handle, NodeResizer, Position, type NodeProps } from "@xyflow/react";

type RegionData = { label: string };
type VpcData = { label: string; cidr?: string; isDefault?: boolean };
type SubnetData = { label: string; cidr?: string; az?: string; isPublic?: boolean };
type Ec2Data = {
  label: string;
  instanceType?: string;
  state?: string;
  privateIp?: string;
  instanceId?: string;
};
type SgData = { label: string; usedBy?: number; sgId?: string };

export function RegionGroupNode({ data, selected }: NodeProps) {
  const d = data as RegionData;
  return (
    <>
      <NodeResizer
        minWidth={480}
        minHeight={280}
        isVisible={Boolean(selected)}
        lineClassName="archResizerLine"
        handleClassName="archResizerHandle"
      />
      <div className="archNode archRegion">
        <div className="archNodeTitle arch-drag-handle" title="Drag to move region">
          <span className="archDragHint">⠿</span> {d.label}
        </div>
      </div>
    </>
  );
}

export function VpcGroupNode({ data, selected }: NodeProps) {
  const d = data as VpcData;
  return (
    <>
      <NodeResizer
        minWidth={420}
        minHeight={200}
        isVisible={Boolean(selected)}
        lineClassName="archResizerLine"
        handleClassName="archResizerHandle"
      />
      <div className="archNode archVpc">
        <div className="archNodeTitle archVpcTitle arch-drag-handle" title="Drag to move VPC">
          <span className="archDragHint">⠿</span>
          <span className="archAwsLabel">VPC</span> {d.label}
          {d.cidr ? <span className="archMeta mono"> {d.cidr}</span> : null}
          {d.isDefault ? <span className="archBadge">default</span> : null}
        </div>
        <div className="archLaneHint archLaneHintSubnet">Subnets</div>
        <div className="archLaneHint archLaneHintSg">Security groups</div>
      </div>
    </>
  );
}

export function SubnetGroupNode({ data, selected }: NodeProps) {
  const d = data as SubnetData;
  return (
    <>
      <NodeResizer
        minWidth={200}
        minHeight={120}
        isVisible={Boolean(selected)}
        lineClassName="archResizerLine"
        handleClassName="archResizerHandle"
      />
      <div className="archNode archSubnet">
        <div className="archNodeTitle archSubnetTitle arch-drag-handle" title="Drag to move subnet">
          <span className="archDragHint">⠿</span>
          <span className="archAwsLabel">Subnet</span> {d.label}
          {d.isPublic ? <span className="archBadge archBadgePublic">public</span> : null}
        </div>
        {d.cidr || d.az ? (
          <div className="archMeta mono">
            {d.cidr}
            {d.az ? ` · ${d.az}` : ""}
          </div>
        ) : null}
      </div>
    </>
  );
}

export function Ec2Node({ data, selected }: NodeProps) {
  const d = data as Ec2Data;
  const state = (d.state || "unknown").toLowerCase();
  return (
    <div className={`archNode archEc2 archEc2-${state} ${selected ? "archEc2Selected" : ""}`}>
      <Handle type="target" position={Position.Left} className="archHandle" />
      <Handle type="source" position={Position.Right} className="archHandle" />
      <div className="archEc2Icon" aria-hidden>
        EC2
      </div>
      <div className="archEc2Body">
        <div className="archEc2Name">{d.label}</div>
        <div className="archMeta mono">
          {d.instanceType}
          {d.privateIp ? ` · ${d.privateIp}` : ""}
        </div>
      </div>
      <span className={`infraBadge infraBadge-${state}`}>{d.state || "?"}</span>
    </div>
  );
}

export function SgNode({ data, selected }: NodeProps) {
  const d = data as SgData;
  return (
    <div className={`archNode archSg ${selected ? "archSgSelected" : ""}`}>
      <Handle type="target" position={Position.Left} className="archHandle" />
      <div className="archSgIcon" aria-hidden>
        SG
      </div>
      <div>
        <div className="archEc2Name">{d.label}</div>
        <div className="archMeta">{d.usedBy ?? 0} instance(s)</div>
      </div>
    </div>
  );
}

export const infraNodeTypes = {
  regionGroup: RegionGroupNode,
  vpcGroup: VpcGroupNode,
  subnetGroup: SubnetGroupNode,
  ec2Node: Ec2Node,
  sgNode: SgNode
};
