"use client";

import { useEffect, useMemo, useState } from "react";

import { DisplayModeSwitch, type DisplayMode } from "../components/DisplayModeSwitch";
import { InfraDiagramPanel } from "../components/InfraDiagramPanel";
import { ViewModeSwitch } from "../components/ViewModeSwitch";
import { useTopology } from "../hooks/useTopology";
import type { Topology } from "../lib/topology";
import { LS_AWS_REGION, LS_AWS_ROLE, LS_INFRA_DISPLAY } from "../lib/topology";

type TabId = "overview" | "instances" | "network" | "security";

export default function InfraPage() {
  const [tab, setTab] = useState<TabId>("overview");
  const [displayMode, setDisplayMode] = useState<DisplayMode>("diagram");
  const [awsRoleArn, setAwsRoleArn] = useState("");
  const [awsRegion, setAwsRegion] = useState("ap-south-1");
  const { topology, busy, error, loadTopology } = useTopology(awsRoleArn, awsRegion);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [vpcFilter, setVpcFilter] = useState<string>("");

  useEffect(() => {
    try {
      const r = localStorage.getItem(LS_AWS_ROLE);
      const reg = localStorage.getItem(LS_AWS_REGION);
      const dm = localStorage.getItem(LS_INFRA_DISPLAY);
      if (r) setAwsRoleArn(r);
      if (reg) setAwsRegion(reg);
      if (dm === "diagram" || dm === "view") setDisplayMode(dm);
    } catch {
      /* ignore */
    }
  }, []);

  function onDisplayModeChange(mode: DisplayMode) {
    setDisplayMode(mode);
    try {
      localStorage.setItem(LS_INFRA_DISPLAY, mode);
    } catch {
      /* ignore */
    }
  }

  const vpcOptions = useMemo(() => {
    if (!topology) return [];
    return topology.vpcs;
  }, [topology]);

  const filteredInstances = useMemo(() => {
    if (!topology) return [];
    if (!vpcFilter) return topology.instances;
    return topology.instances.filter((i) => i.vpc_id === vpcFilter);
  }, [topology, vpcFilter]);

  const selectedInstance = useMemo(() => {
    if (!topology || !selectedId) return null;
    return topology.instances.find((i) => i.instance_id === selectedId) || null;
  }, [topology, selectedId]);

  const sgById = useMemo(() => {
    const m = new Map<string, Topology["security_groups"][0]>();
    topology?.security_groups.forEach((sg) => {
      if (sg.id) m.set(sg.id, sg);
    });
    return m;
  }, [topology]);

  function stateBadge(state?: string) {
    const s = (state || "unknown").toLowerCase();
    return <span className={`infraBadge infraBadge-${s}`}>{state || "unknown"}</span>;
  }

  return (
    <div className="infraShell">
      <div className="topBar">
        <div>
          <div className="topBarTitle">EC2 Infrastructure</div>
          <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
            VPC, subnets, security groups, and instances for the selected region.
          </div>
        </div>
        <div className="topBarActions">
          <DisplayModeSwitch mode={displayMode} onChange={onDisplayModeChange} />
          <ViewModeSwitch />
        </div>
      </div>

      {displayMode === "diagram" ? (
        <InfraDiagramPanel
          awsRoleArn={awsRoleArn}
          awsRegion={awsRegion}
          onAwsRoleArnChange={setAwsRoleArn}
          onAwsRegionChange={setAwsRegion}
          autoLoad={Boolean(awsRoleArn.trim())}
        />
      ) : null}

      {displayMode === "view" ? (
      <>
      <div className="infraToolbar pane">
        <div className="infraToolbarGrid">
          <label className="fieldLabel" htmlFor="infra-role">
            AWS Role ARN
          </label>
          <input
            id="infra-role"
            className="infraInput"
            value={awsRoleArn}
            onChange={(e) => setAwsRoleArn(e.target.value)}
            placeholder="arn:aws:iam::123456789012:role/YourRole"
          />
          <label className="fieldLabel" htmlFor="infra-region">
            Region
          </label>
          <input
            id="infra-region"
            className="infraInput infraInputShort"
            value={awsRegion}
            onChange={(e) => setAwsRegion(e.target.value)}
          />
          <div className="infraToolbarActions">
            <button type="button" onClick={() => void loadTopology()} disabled={busy}>
              {busy ? "Loading…" : "Refresh"}
            </button>
          </div>
        </div>
        {topology ? (
          <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
            Fetched {new Date(topology.fetched_at).toLocaleString()} · {topology.region}
          </div>
        ) : null}
        {error ? <div className="infraError">{error}</div> : null}
      </div>

      <div className="infraTabs">
        {(
          [
            ["overview", "Overview"],
            ["instances", "Instances"],
            ["network", "Network map"],
            ["security", "Security groups"]
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`infraTab ${tab === id ? "infraTabActive" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {!topology && !busy && !error ? (
        <div className="pane muted">Enter Role ARN and click Refresh to load infrastructure.</div>
      ) : null}

      {topology && tab === "overview" ? (
        <div className="infraOverviewGrid">
          <div className="infraStatCard pane">
            <div className="infraStatValue">{topology.summary.instance_count}</div>
            <div className="muted">EC2 instances</div>
            <div className="muted" style={{ marginTop: 4 }}>
              {topology.summary.running_count} running
            </div>
          </div>
          <div className="infraStatCard pane">
            <div className="infraStatValue">{topology.summary.vpc_count}</div>
            <div className="muted">VPCs</div>
          </div>
          <div className="infraStatCard pane">
            <div className="infraStatValue">{topology.summary.subnet_count}</div>
            <div className="muted">Subnets</div>
          </div>
          <div className="infraStatCard pane">
            <div className="infraStatValue">{topology.summary.security_group_count}</div>
            <div className="muted">Security groups</div>
            {topology.summary.open_inbound_0_0_0_0 > 0 ? (
              <div className="infraWarn" style={{ marginTop: 8 }}>
                {topology.summary.open_inbound_0_0_0_0} rule(s) open to 0.0.0.0/0
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {topology && tab === "instances" ? (
        <div className="infraSplit">
          <div className="pane infraTableWrap">
            <div className="paneHeader">
              <div className="paneHeaderTitle">Instances</div>
              <select value={vpcFilter} onChange={(e) => setVpcFilter(e.target.value)} aria-label="VPC filter">
                <option value="">All VPCs</option>
                {vpcOptions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name || v.id}
                  </option>
                ))}
              </select>
            </div>
            <table className="infraTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>State</th>
                  <th>Type</th>
                  <th>Private IP</th>
                  <th>VPC / Subnet</th>
                </tr>
              </thead>
              <tbody>
                {filteredInstances.map((inst) => (
                  <tr
                    key={inst.instance_id}
                    className={selectedId === inst.instance_id ? "infraRowSelected" : ""}
                    onClick={() => setSelectedId(inst.instance_id)}
                  >
                    <td>
                      <div>{inst.name || "—"}</div>
                      <div className="mono muted" style={{ fontSize: 11 }}>
                        {inst.instance_id}
                      </div>
                    </td>
                    <td>{stateBadge(inst.state)}</td>
                    <td className="mono">{inst.instance_type}</td>
                    <td className="mono">{inst.private_ip || "—"}</td>
                    <td className="mono" style={{ fontSize: 11 }}>
                      {inst.vpc_id || "—"}
                      <br />
                      {inst.subnet_id || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pane infraDetail">
            <div className="paneHeaderTitle">Instance detail</div>
            {selectedInstance ? (
              <div className="infraDetailBody mono">
                <p>
                  <strong>{selectedInstance.name || selectedInstance.instance_id}</strong>
                </p>
                <p>State: {selectedInstance.state}</p>
                <p>Type: {selectedInstance.instance_type}</p>
                <p>AZ: {selectedInstance.az || "—"}</p>
                <p>Private: {selectedInstance.private_ip || "—"}</p>
                <p>Public: {selectedInstance.public_ip || "—"}</p>
                <p>VPC: {selectedInstance.vpc_id || "—"}</p>
                <p>Subnet: {selectedInstance.subnet_id || "—"}</p>
                <p style={{ marginTop: 12 }}>Security groups:</p>
                <ul>
                  {(selectedInstance.security_group_ids || []).map((sgId) => {
                    const sg = sgById.get(sgId);
                    return (
                      <li key={sgId}>
                        {sg?.name || sgId}
                        {sg?.description ? ` — ${sg.description}` : ""}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : (
              <div className="muted">Select an instance row to see network details.</div>
            )}
          </div>
        </div>
      ) : null}

      {topology && tab === "network" ? (
        <div className="pane infraMapPane">
          <div className="paneHeader">
            <div className="paneHeaderTitle">Network map</div>
            <select value={vpcFilter} onChange={(e) => setVpcFilter(e.target.value)} aria-label="VPC filter map">
              <option value="">All VPCs</option>
              {vpcOptions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name || v.id}
                </option>
              ))}
            </select>
          </div>
          <div className="infraMapScroll">
            {topology.vpcs
              .filter((v) => !vpcFilter || v.id === vpcFilter)
              .map((vpc) => {
                const subnets = topology.subnets.filter((sn) => sn.vpc_id === vpc.id);
                const instances = topology.instances.filter((i) => i.vpc_id === vpc.id);
                return (
                  <div key={vpc.id} className="infraVpcBlock">
                    <div className="infraVpcTitle">
                      <span>VPC</span> {vpc.name || vpc.id}
                      <span className="mono muted"> {vpc.cidr}</span>
                      {vpc.is_default ? <span className="infraBadge">default</span> : null}
                    </div>
                    <div className="infraSubnetGrid">
                      {subnets.map((sn) => {
                        const snInstances = instances.filter((i) => i.subnet_id === sn.id);
                        return (
                          <div key={sn.id} className="infraSubnetCard">
                            <div className="infraSubnetTitle">
                              {sn.name || sn.id}
                              <span className="mono muted"> · {sn.cidr}</span>
                              {sn.public ? <span className="infraBadge infraBadge-running">public</span> : null}
                            </div>
                            <div className="muted" style={{ fontSize: 11 }}>
                              {sn.az}
                            </div>
                            <div className="infraInstanceList">
                              {snInstances.length === 0 ? (
                                <div className="muted">No instances</div>
                              ) : (
                                snInstances.map((inst) => (
                                  <div
                                    key={inst.instance_id}
                                    className="infraInstanceChip"
                                    onClick={() => {
                                      setSelectedId(inst.instance_id);
                                      setTab("instances");
                                    }}
                                  >
                                    <div>{inst.name || inst.instance_id}</div>
                                    <div className="mono muted" style={{ fontSize: 10 }}>
                                      {inst.instance_type} · {inst.private_ip || "no IP"}
                                    </div>
                                    {(inst.security_group_ids || []).slice(0, 2).map((sgId) => (
                                      <div key={sgId} className="infraSgTag mono">
                                        {sgById.get(sgId)?.name || sgId}
                                      </div>
                                    ))}
                                  </div>
                                ))
                              )}
                            </div>
                          </div>
                        );
                      })}
                      {subnets.length === 0 ? (
                        <div className="muted">No subnets in this VPC</div>
                      ) : null}
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      ) : null}

      {topology && tab === "security" ? (
        <div className="pane infraTableWrap">
          <div className="paneHeader">
            <div className="paneHeaderTitle">Security groups</div>
          </div>
          <table className="infraTable">
            <thead>
              <tr>
                <th>Name</th>
                <th>ID</th>
                <th>VPC</th>
                <th>Used by</th>
                <th>Inbound (sample)</th>
              </tr>
            </thead>
            <tbody>
              {topology.security_groups.map((sg) => (
                <tr key={sg.id}>
                  <td>{sg.name}</td>
                  <td className="mono">{sg.id}</td>
                  <td className="mono">{sg.vpc_id || "—"}</td>
                  <td>{sg.used_by_instances ?? 0} instance(s)</td>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {(sg.inbound || [])
                      .slice(0, 3)
                      .map((r, i) => (
                        <div key={i}>
                          {String(r.protocol)} {String(r.from_port ?? "*")}-{String(r.to_port ?? "*")}{" "}
                          {String(r.cidr || r.source_sg || "")}
                        </div>
                      ))}
                    {(sg.inbound || []).length > 3 ? <div>…</div> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      </>
      ) : null}
    </div>
  );
}
