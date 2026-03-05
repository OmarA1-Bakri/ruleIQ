'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

// Only import sigma dependencies on client side
let Graph: any;
let Sigma: any;
let forceAtlas2: any;

if (typeof window !== 'undefined') {
  try {
    Graph = require('graphology');
    Sigma = require('sigma').default;
    forceAtlas2 = require('graphology-layout-forceatlas2').default;
  } catch (error) {
    console.warn('Graph libraries not available:', error);
  }
}

export const SigmaNetworkGraph = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [graphData, setGraphData] = useState<any>(null);
  const sigmaRef = useRef<any>(null);

  useEffect(() => {
    fetchGraphData();
  }, []);

  const fetchGraphData = async () => {
    try {
      const response = await fetch('http://localhost:8000/graph?nodes=80&clusters=6');
      const data = await response.json();
      setGraphData(data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching graph data:', error);
      // Generate fallback data
      const fallbackData = generateFallbackGraph();
      setGraphData(fallbackData);
      setLoading(false);
    }
  };

  const generateFallbackGraph = () => {
    const nodes = [];
    const edges = [];
    const nodeCount = 50;
    
    for (let i = 0; i < nodeCount; i++) {
      nodes.push({
        id: `node_${i}`,
        label: `Node ${i}`,
        x: Math.random() * 100 - 50,
        y: Math.random() * 100 - 50,
        size: Math.random() * 10 + 5,
        color: ['var(--purple-500)', 'var(--purple-500)', 'var(--purple-400)'][Math.floor(Math.random() * 3)]
      });
    }
    
    for (let i = 0; i < nodeCount * 2; i++) {
      const source = `node_${Math.floor(Math.random() * nodeCount)}`;
      const target = `node_${Math.floor(Math.random() * nodeCount)}`;      if (source !== target) {
        edges.push({
          id: `edge_${i}`,
          source,
          target,
          color: 'var(--purple-500)40'
        });
      }
    }
    
    return { nodes, edges };
  };

  useEffect(() => {
    if (!containerRef.current || !graphData || loading || typeof window === 'undefined' || !Graph || !Sigma || !forceAtlas2) return;

    // Create a new graph instance
    const graph = new Graph();

    // Add nodes
    graphData.nodes.forEach((node: any) => {
      graph.addNode(node.id, {
        label: node.label,
        x: node.x,
        y: node.y,
        size: node.size,
        color: node.color
      });
    });

    // Add edges
    graphData.edges.forEach((edge: any) => {
      try {
        graph.addEdge(edge.source, edge.target, {
          color: edge.color || 'var(--purple-500)40',
          size: edge.weight || 1
        });
      } catch (_e) {
        // Ignore duplicate edges or missing nodes
      }
    });

    // Apply force layout
    const positions = forceAtlas2(graph, {
      iterations: 100,
      settings: {
        gravity: 1,
        scalingRatio: 10,
        barnesHutOptimize: true,
        strongGravityMode: false
      }
    });

    // Update node positions
    graph.updateEachNodeAttributes((node: any, attr: any) => ({
      ...attr,
      ...positions[node]
    }));
    // Initialize Sigma
    if (sigmaRef.current) {
      sigmaRef.current.kill();
    }

    sigmaRef.current = new Sigma(graph, containerRef.current, {
      renderEdgeLabels: false,
      defaultNodeColor: 'var(--purple-500)',
      defaultEdgeColor: 'var(--purple-500)40',
      nodeReducer: (node: any, data: any) => {
        const res = { ...data };
        if (data.highlighted) {
          res.color = 'var(--purple-600)';
        }
        return res;
      },
      edgeReducer: (edge: any, data: any) => {
        const res = { ...data };
        if (data.highlighted) {
          res.color = 'var(--purple-600)';
        }
        return res;
      }
    });

    // Add hover effects
    let hoveredNode: string | null = null;
    
    sigmaRef.current.on('enterNode', ({ node }: { node: any }) => {
      hoveredNode = node;
      graph.setNodeAttribute(node, 'highlighted', true);
      graph.neighbors(node).forEach((neighbor: any) => {
        graph.setNodeAttribute(neighbor, 'highlighted', true);
      });
      graph.edges(node).forEach((edge: any) => {
        graph.setEdgeAttribute(edge, 'highlighted', true);
      });
      sigmaRef.current?.refresh();
    });

    sigmaRef.current.on('leaveNode', () => {
      if (hoveredNode) {
        graph.setNodeAttribute(hoveredNode, 'highlighted', false);
        graph.neighbors(hoveredNode).forEach((neighbor: any) => {
          graph.setNodeAttribute(neighbor, 'highlighted', false);
        });
        graph.edges(hoveredNode).forEach((edge: any) => {
          graph.setEdgeAttribute(edge, 'highlighted', false);
        });
        hoveredNode = null;
        sigmaRef.current?.refresh();
      }
    });

    return () => {
      if (sigmaRef.current) {
        sigmaRef.current.kill();
        sigmaRef.current = null;
      }
    };
  }, [graphData, loading]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5 }}
      className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20"
    >
      <h3 className="text-xl font-semibold text-white mb-4">Network Topology</h3>
      {loading ? (
        <div className="h-[500px] flex items-center justify-center">
          <div className="text-purple-400">Loading network graph...</div>
        </div>
      ) : (
        <div 
          ref={containerRef} 
          className="w-full h-[500px] bg-gray-950/50 rounded-lg"
        />
      )}
      {graphData && (
        <div className="mt-4 grid grid-cols-4 gap-2">
          <div className="text-center">
            <p className="text-xs text-gray-400">Nodes</p>
            <p className="text-lg font-bold text-purple-400">{graphData.metadata?.node_count || 0}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-400">Edges</p>
            <p className="text-lg font-bold text-purple-400">{graphData.metadata?.edge_count || 0}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-400">Clusters</p>
            <p className="text-lg font-bold text-purple-400">{graphData.metadata?.clusters || 0}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-gray-400">Density</p>
            <p className="text-lg font-bold text-purple-400">
              {((graphData.metadata?.density || 0) * 100).toFixed(1)}%
            </p>
          </div>
        </div>
      )}
    </motion.div>
  );
};