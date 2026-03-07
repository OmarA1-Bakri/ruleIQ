'use client';

import React, { useRef, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, MeshDistortMaterial, Float } from '@react-three/drei';
import * as THREE from 'three';

// 3D DATA ORB - Morphing data visualization
function DataOrb({ data = 1 }) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.elapsedTime * 0.2;
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.3;
    }
  });

  return (
    <Float speed={2} rotationIntensity={1} floatIntensity={2}>
      <ambientLight intensity={0.25} />
      <directionalLight position={[0, 10, 5]} intensity={1} />
      <pointLight position={[10, 10, 10]} intensity={0.5} color="var(--purple-500)" />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="var(--silver-400)" />
      
      <Sphere ref={meshRef} args={[1, 100, 200]} scale={2.5}>
        <MeshDistortMaterial
          color="var(--purple-500)"
          attach="material"
          distort={0.5 * data}
          speed={2}
          roughness={0.2}
          metalness={0.8}
        />
      </Sphere>
    </Float>
  );
}

export const ThreeDDataOrb = () => {
  const [dataValue, setDataValue] = useState(0.5);
  useEffect(() => {
    const interval = setInterval(() => {
      setDataValue(Math.random());
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 rounded-2xl p-6 border border-purple-800/20 h-[400px]">
      <h3 className="text-xl font-semibold text-white mb-4">Quantum Data State</h3>
      <Canvas camera={{ position: [0, 0, 5], fov: 75 }}>
        <color attach="background" args={['var(--purple-400)A0B']} />
        <fog attach="fog" args={['var(--purple-400)A0B', 5, 15]} />
        <DataOrb data={dataValue} />
        <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={0.5} />
        <mesh rotation={[0, 0, 0]} position={[0, 0, -2]}>
          <planeGeometry args={[20, 20, 100, 100]} />
          <meshStandardMaterial 
            color="var(--black)a2e" 
            wireframe 
            transparent 
            opacity={0.1} 
          />
        </mesh>
      </Canvas>
      <div className="mt-4 flex justify-center">
        <div className="text-center">
          <p className="text-xs text-gray-400">Data Flux</p>
          <p className="text-2xl font-bold text-purple-400">{Math.round(dataValue * 100)}%</p>
        </div>
      </div>
    </div>
  );
};