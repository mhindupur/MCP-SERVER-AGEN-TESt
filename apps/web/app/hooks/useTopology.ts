"use client";

import { useCallback, useState } from "react";

import type { Topology } from "../lib/topology";
import { LS_AWS_REGION, LS_AWS_ROLE } from "../lib/topology";

export function useTopology(awsRoleArn: string, awsRegion: string) {
  const [topology, setTopology] = useState<Topology | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadTopology = useCallback(async () => {
    const role = awsRoleArn.trim();
    if (!role) {
      setError("AWS Role ARN is required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      localStorage.setItem(LS_AWS_ROLE, role);
      localStorage.setItem(LS_AWS_REGION, awsRegion);
    } catch {
      /* ignore */
    }
    try {
      const qs = new URLSearchParams({ aws_role_arn: role, aws_region: awsRegion });
      const r = await fetch(`/api/aws/infra/topology?${qs.toString()}`, { credentials: "include" });
      const text = await r.text();
      if (!r.ok) {
        let detail = text;
        try {
          const j = JSON.parse(text);
          detail = j.detail || text;
        } catch {
          /* raw */
        }
        setError(`Error (${r.status}): ${detail}`);
        setTopology(null);
        return;
      }
      setTopology(JSON.parse(text) as Topology);
    } catch (e) {
      setError(String(e));
      setTopology(null);
    } finally {
      setBusy(false);
    }
  }, [awsRoleArn, awsRegion]);

  return { topology, busy, error, loadTopology, setError };
}
