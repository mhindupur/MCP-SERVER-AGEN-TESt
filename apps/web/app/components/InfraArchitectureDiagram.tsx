"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Node
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { topologyToFlow, type LayoutSpacing } from "../lib/topologyToFlow";
import type { Topology } from "../lib/topology";
import { infraNodeTypes } from "./flow/InfraFlowNodes";

type Props = {
  topology: Topology;
  vpcFilter?: string;
  spacing?: LayoutSpacing;
  layoutVersion?: number;
  onSelectInstance?: (instanceId: string) => void;
  className?: string;
};

function DiagramCanvas({
  topology,
  vpcFilter = "",
  spacing = "normal",
  layoutVersion = 0,
  onSelectInstance,
  className
}: Props) {
  const { fitView } = useReactFlow();
  const didFit = useRef(false);

  const layout = useMemo(
    () => topologyToFlow(topology, vpcFilter, spacing),
    [topology, vpcFilter, spacing, layoutVersion]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(layout.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layout.edges);

  useEffect(() => {
    setNodes(layout.nodes);
    setEdges(layout.edges);
    didFit.current = false;
  }, [layout.nodes, layout.edges, setNodes, setEdges]);

  useEffect(() => {
    if (!didFit.current && nodes.length > 0) {
      didFit.current = true;
      requestAnimationFrame(() => {
        void fitView({ padding: 0.25, duration: 200 });
      });
    }
  }, [nodes.length, fitView, layoutVersion]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (node.type === "ec2Node" && node.id.startsWith("instance/")) {
        const id = node.id.replace("instance/", "");
        onSelectInstance?.(id);
      }
    },
    [onSelectInstance]
  );

  return (
    <div className={`archDiagramWrap ${className || ""}`}>
      <div className="archDiagramHint muted">
        Drag nodes to rearrange. Select a VPC or subnet and drag corners to expand. Use controls to zoom.
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={infraNodeTypes}
        onNodeClick={onNodeClick}
        minZoom={0.08}
        maxZoom={2}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable
        panOnDrag
        selectionOnDrag={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={24} size={1} />
        <Controls showInteractive />
        <MiniMap nodeStrokeWidth={2} pannable zoomable className="archMinimap" />
      </ReactFlow>
    </div>
  );
}

export function InfraArchitectureDiagram(props: Props) {
  return (
    <ReactFlowProvider>
      <DiagramCanvas {...props} />
    </ReactFlowProvider>
  );
}
