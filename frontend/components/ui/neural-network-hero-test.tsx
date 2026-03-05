'use client';


// Dynamic imports for GSAP to avoid SSR issues
let gsap: any;
let SplitText: any;
let _useGSAP: any;

if (typeof window !== 'undefined') {
  gsap = require('gsap').gsap;
  SplitText = require('gsap/SplitText').SplitText;
  _useGSAP = require('@gsap/react').useGSAP;
  
  if (gsap && SplitText) {
    gsap.registerPlugin(SplitText);
  }
}