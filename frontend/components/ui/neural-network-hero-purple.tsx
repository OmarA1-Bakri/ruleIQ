'use client';

import { useRef } from 'react';
import { Canvas, useFrame, extend } from '@react-three/fiber';
import { shaderMaterial } from '@react-three/drei';
import * as THREE from 'three';

import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { SplitText } from 'gsap/SplitText';

gsap.registerPlugin(SplitText, useGSAP);

// ===================== SHADER WITH PURPLE & SILVER =====================
const vertexShader = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = `
  #ifdef GL_ES
    precision lowp float;
  #endif
  uniform float iTime;
  uniform vec2 iResolution;
  varying vec2 vUv;
  
  vec4 buf[8];
  
  vec4 sigmoid(vec4 x) { return 1. / (1. + exp(-x)); }
  
  vec4 cppn_fn(vec2 coordinate, float in0, float in1, float in2) {    // layer 1 *********************************************************************
    buf[6] = vec4(coordinate.x, coordinate.y, 0.3948333106474662 + in0, 0.36 + in1);
    buf[7] = vec4(0.14 + in2, sqrt(coordinate.x * coordinate.x + coordinate.y * coordinate.y), 0., 0.);

    // layer 2 ********************************************************************
    buf[0] = mat4(vec4(6.5404263, -3.6126034, 0.7590882, -1.13613), vec4(2.4582713, 3.1660357, 1.2219609, 0.06276096), vec4(-5.478085, -6.159632, 1.8701609, -4.7742867), vec4(6.039214, -5.542865, -0.90925294, 3.251348))
    * buf[6]
    + mat4(vec4(0.8473259, -5.722911, 3.975766, 1.6522468), vec4(-0.24321538, 0.5839259, -1.7661959, -5.350116), vec4(0.0, 0.0, 0.0, 0.0), vec4(0.0, 0.0, 0.0, 0.0))
    * buf[7]
    + vec4(0.21808943, 1.1243913, -1.7969975, 5.0294676);
    
    buf[1] = mat4(vec4(-3.3522482, -6.0612736, 0.55641043, -4.4719114), vec4(0.8631464, 1.7432913, 5.643898, 1.6106541), vec4(2.4941394, -3.5012043, 1.7184316, 6.357333), vec4(3.310376, 8.209261, 1.1355612, -1.165539))
    * buf[6]
    + mat4(vec4(5.24046, -13.034365, 0.009859298, 15.870829), vec4(2.987511, 3.129433, -0.89023495, -1.6822904), vec4(0.0, 0.0, 0.0, 0.0), vec4(0.0, 0.0, 0.0, 0.0))
    * buf[7]
    + vec4(-5.9457836, -6.573602, -0.8812491, 1.5436668);

    buf[0] = sigmoid(buf[0]);
    buf[1] = sigmoid(buf[1]);

    // output layer
    vec4 output = buf[0] + buf[1];
    
    // Purple and silver theme
    vec3 color = mix(vec3(0.5, 0.3, 0.8), vec3(0.8, 0.8, 0.9), output.x);
    
    gl_FragColor = vec4(color, 0.8);
  }
`;

// Create shader material
const NeuralNetworkMaterial = shaderMaterial(
  {
    iTime: 0,
    iResolution: new THREE.Vector2(1, 1),
  },
  vertexShader,
  fragmentShader
);

extend({ NeuralNetworkMaterial });

// TypeScript module augmentation
declare module '@react-three/fiber' {
  interface ThreeElements {
    neuralNetworkMaterial: any;
  }
}

// Component
function AnimatedPlane() {
  const meshRef = useRef<THREE.Mesh>(null!);
  const materialRef = useRef<any>(null!);

  useFrame(({ clock }) => {
    if (materialRef.current) {
      materialRef.current.iTime = clock.getElapsedTime();
    }
  });

  return (
    <mesh ref={meshRef}>
      <planeGeometry args={[4, 4, 64, 64]} />
      <neuralNetworkMaterial ref={materialRef} />
    </mesh>
  );
}

export default function NeuralNetworkHeroPurple() {
  const containerRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    if (!containerRef.current) return;

    const splitText = new SplitText('.hero-title', { type: 'chars' });
    gsap.fromTo(
      splitText.chars,
      { y: 50, opacity: 0 },
      {
        y: 0,
        opacity: 1,
        duration: 1,
        stagger: 0.05,
        ease: 'power3.out',
      }
    );
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="relative w-full h-screen overflow-hidden bg-gradient-to-br from-purple-900 via-gray-900 to-black">
      <Canvas className="absolute inset-0">
        <ambientLight intensity={0.5} />
        <AnimatedPlane />
      </Canvas>
      
      <div className="absolute inset-0 flex items-center justify-center z-10">
        <h1 className="hero-title text-6xl font-bold text-white text-center max-w-4xl">
          Neural Network AI
        </h1>
      </div>
    </div>
  );
}
