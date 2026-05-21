"use client";

import { useEffect, useMemo, useState } from "react";

import { InfraArchitectureDiagram } from "./InfraArchitectureDiagram";
import { useTopology } from "../hooks/useTopology";
import type { LayoutSpacing } from "../lib/topologyToFlow";
import type { Topology } from "../lib/topology";

type Props = {
  awsRoleArn: string;
  awsRegion: string;
  onAwsRoleArnChange?: (v: string) => void;
  onAwsRegionChange?: (v: string) => void;
  autoLoad?: boolean;
  compact?: boolean;
};

export function InfraDiagramPanel({
  awsRoleArn,
  awsRegion,
  onAwsRoleArnChange,
  onAwsRegionChange,
  autoLoad = false,
  compact
}: Props) {
  const { topology, busy, error, loadTopology } = useTopology(awsRoleArn, awsRegion);
  const [vpcFilter, setVpcFilter] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [spacing, setSpacing] = useState<LayoutSpacing>("wide");
  const [layoutVersion, setLayoutVersion] = useState(0);

  useEffect(() => {
    if (autoLoad && awsRoleArn.trim()) void loadTopology();
  }, [autoLoad, awsRoleArn, awsRegion, loadTopology]);

  const selectedInstance = useMemo(() => {
    if (!topology || !selectedId) return null;
    return topology.instances.find((i) => i.instance_id === selectedId) || null;
  }, [topology, selectedId]);

  const vpcOptions = topology?.vpcs ?? [];

  return (
    <div className={`infraDiagramPanel ${compact ? "infraDiagramPanelCompact" : ""}`}>
      <div className="infraDiagramToolbar pane">
        {onAwsRoleArnChange ? (
          <input
            className="infraInput infraDiagramRole"
            value={awsRoleArn}
            onChange={(e) => onAwsRoleArnChange(e.target.value)}
            placeholder="AWS Role ARN"
            aria-label="AWS Role ARN"
          />
        ) : null}
        {onAwsRegionChange ? (
          <input
            className="infraInput infraInputShort"
            value={awsRegion}
            onChange={(e) => onAwsRegionChange(e.target.value)}
            aria-label="AWS region"
          />
        ) : null}
        <button type="button" onClick={() => void loadTopology()} disabled={busy || !awsRoleArn.trim()}>
          {busy ? "Loading…" : "Refresh topology"}
        </button>
        <button
          type="button"
          onClick={() => setLayoutVersion((v) => v + 1)}
          disabled={!topology}
          title="Re-apply auto-layout spacing"
        >
          Reset layout
        </button>
        <label className="muted" style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          Spacing
          <select
            value={spacing}
            onChange={(e) => {
              setSpacing(e.target.value as LayoutSpacing);
              setLayoutVersion((v) => v + 1);
            }}
            className="infraDiagramVpcSelect"
            aria-label="Layout spacing"
          >
            <option value="compact">Compact</option>
            <option value="normal">Normal</option>
            <option value="wide">Wide</option>
          </select>
        </label>
        {topology ? (
          <select
            value={vpcFilter}
            onChange={(e) => setVpcFilter(e.target.value)}
            aria-label="VPC filter"
            className="infraDiagramVpcSelect"
          >
            <option value="">All VPCs</option>
            {vpcOptions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name || v.id}
              </option>
            ))}
          </select>
        ) : null}
        {topology ? (
          <span className="muted" style={{ fontSize: 12 }}>
            {topology.summary.instance_count} instances · {topology.summary.vpc_count} VPCs ·{" "}
            {new Date(topology.fetched_at).toLocaleString()}
          </span>
        ) : (
          <span className="muted" style={{ fontSize: 12 }}>
            Enter Role ARN and refresh to load the architecture diagram.
          </span>
        )}
        {error ? <div className="infraError">{error}</div> : null}
      </div>

      {topology ? (
        <div className="infraDiagramMain">
          <InfraArchitectureDiagram
            topology={topology}
            vpcFilter={vpcFilter}
            spacing={spacing}
            layoutVersion={layoutVersion}
            onSelectInstance={setSelectedId}
          />
          {selectedInstance ? (
            <div className="infraDiagramDrawer pane">
              <div className="paneHeaderTitle">Selected EC2</div>
              <div className="mono" style={{ fontSize: 12, marginTop: 8 }}>
                <div>
                  <strong>{selectedInstance.name || selectedInstance.instance_id}</strong>
                </div>
                <div>{selectedInstance.instance_id}</div>
                <div>State: {selectedInstance.state}</div>
                <div>Type: {selectedInstance.instance_type}</div>
                <div>VPC: {selectedInstance.vpc_id || "—"}</div>
                <div>Subnet: {selectedInstance.subnet_id || "—"}</div>
                <div>Private IP: {selectedInstance.private_ip || "—"}</div>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="pane muted infraDiagramEmpty">
          {!busy && !error ? "No topology loaded yet." : null}
        </div>
      )}
    </div>
  );
}
