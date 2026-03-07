'use client';


// Dynamic imports for GSAP to avoid SSR issues
let _gsapInstance: any;
let _splitTextPlugin: any;
let _useGSAP: any;

if (typeof window !== 'undefined') {
  _gsapInstance = require('gsap').gsap;
  _splitTextPlugin = require('gsap/SplitText').SplitText;
  _useGSAP = require('@gsap/react').useGSAP;

  if (_gsapInstance && _splitTextPlugin) {
    _gsapInstance.registerPlugin(_splitTextPlugin);
  }
}